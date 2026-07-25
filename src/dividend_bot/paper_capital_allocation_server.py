"""Minimal read/write HTTP portal for governed paper allocation requests.

Run behind authenticated HTTPS/Nginx on DigitalOcean. The server only records
paper allocation requests; it cannot contact a broker or move capital.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional
from wsgiref.simple_server import make_server

from .paper_capital_allocation import (
    BROKER_EXECUTION_ENABLED,
    CAPITAL_MOVEMENT_ENABLED,
    LIVE_TRADING_ENABLED,
    PAPER_TRADE_MODE,
    append_allocation_request,
    build_allocation_request,
    discover_strategy_plugins,
    parse_allocation_form,
    render_allocation_html,
)
from .paper_cash_account import initialize_cash_account, read_cash_account

DEFAULT_REGISTRY_PATH = Path("results/enterprise_dividend_service_registry.json")
DEFAULT_CASH_PATH = Path("state/paper_cash_account.json")
DEFAULT_REQUEST_LOG = Path("state/paper_allocation_requests.jsonl")


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def available_cash_from_state(state: Mapping[str, Any]) -> float:
    for key in ("available_cash", "cash_available", "unallocated_cash", "cash_balance", "balance"):
        value = state.get(key)
        if isinstance(value, (int, float)):
            return round(float(value), 2)
    summary = state.get("summary")
    if isinstance(summary, Mapping):
        return available_cash_from_state(summary)
    return 0.0


def confirmation_html(request: Mapping[str, Any], *, recorded: bool) -> str:
    rows = "".join(
        f"<tr><td>{item['strategy_name']}</td><td>${float(item['amount']):,.2f}</td><td>{float(item['percentage_of_request']):.2f}%</td></tr>"
        for item in request.get("allocations", [])
    )
    result = "Recorded" if recorded else "Already recorded"
    return f"""<!doctype html><html lang='en'><meta charset='utf-8'><title>Allocation request</title>
<body style='font-family:Arial;background:#f5f7fb;padding:30px'><main style='max-width:850px;margin:auto;background:white;padding:28px;border-radius:16px'>
<h1>Paper allocation request {result}</h1><p><strong>Request:</strong> {request['request_id']}</p><p><strong>Status:</strong> {request['status']}</p>
<p><strong>Total requested:</strong> ${float(request['requested_cash']):,.2f}</p><table border='1' cellpadding='9' cellspacing='0'><tr><th>Strategy</th><th>Amount</th><th>Share</th></tr>{rows}</table>
<p><strong>PAPER ONLY:</strong> No cash was transferred and no order was placed. Governance review is still required.</p><p><a href='/allocation'>Return to allocation page</a></p></main></body></html>"""


def create_wsgi_app(
    *,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    cash_path: str | Path = DEFAULT_CASH_PATH,
    request_log: str | Path = DEFAULT_REQUEST_LOG,
    investor_id: str = "default-investor",
    initial_paper_cash: Optional[float] = None,
) -> Callable:
    registry_file = Path(registry_path)
    cash_file = Path(cash_path)
    log_file = Path(request_log)
    if not cash_file.is_file() and initial_paper_cash is not None:
        initialize_cash_account(
            path=cash_file,
            investor_money=initial_paper_cash,
            investor_id=investor_id,
        )

    def app(environ: Mapping[str, Any], start_response: Callable) -> Iterable[bytes]:
        path = str(environ.get("PATH_INFO") or "/")
        method = str(environ.get("REQUEST_METHOD") or "GET").upper()
        registry = _load_mapping(registry_file)
        plugins = discover_strategy_plugins(registry)
        cash_state = read_cash_account(cash_file) if cash_file.is_file() else {}
        available_cash = available_cash_from_state(cash_state)
        try:
            if method == "GET" and path in {"/", "/allocation"}:
                payload = render_allocation_html(available_cash=available_cash, strategy_plugins=plugins).encode("utf-8")
                start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(payload)))])
                return [payload]
            if method == "POST" and path == "/allocation/request":
                length = int(environ.get("CONTENT_LENGTH") or 0)
                body = environ["wsgi.input"].read(length)
                requested, allocations = parse_allocation_form(body)
                request = build_allocation_request(
                    available_cash=available_cash,
                    requested_cash=requested,
                    allocations=allocations,
                    strategy_plugins=plugins,
                    investor_id=investor_id,
                )
                recorded = append_allocation_request(request, log_file)
                payload = confirmation_html(request, recorded=recorded).encode("utf-8")
                start_response("201 Created" if recorded else "200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(payload)))])
                return [payload]
            payload = b"Not found"
            start_response("404 Not Found", [("Content-Type", "text/plain"), ("Content-Length", str(len(payload)))])
            return [payload]
        except (ValueError, json.JSONDecodeError) as exc:
            payload = ("Invalid paper allocation request: " + str(exc)).encode("utf-8")
            start_response("400 Bad Request", [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(payload)))])
            return [payload]

    return app


def main() -> int:
    host = os.environ.get("DIVIDEND_ALLOCATION_HOST", "127.0.0.1")
    port = int(os.environ.get("DIVIDEND_ALLOCATION_PORT", "8091"))
    initial_cash_text = os.environ.get("DIVIDEND_INITIAL_PAPER_CASH")
    initial_cash = float(initial_cash_text) if initial_cash_text and initial_cash_text.strip() else None
    app = create_wsgi_app(
        registry_path=os.environ.get("DIVIDEND_STRATEGY_REGISTRY", str(DEFAULT_REGISTRY_PATH)),
        cash_path=os.environ.get("DIVIDEND_PAPER_CASH_STATE", str(DEFAULT_CASH_PATH)),
        request_log=os.environ.get("DIVIDEND_ALLOCATION_REQUEST_LOG", str(DEFAULT_REQUEST_LOG)),
        investor_id=os.environ.get("DIVIDEND_INVESTOR_ID", "default-investor"),
        initial_paper_cash=initial_cash,
    )
    print(f"Paper allocation portal listening on http://{host}:{port}/allocation")
    with make_server(host, port, app) as server:
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
