"""WSGI extension for SWING-001 manual strategy and user-only promotion actions."""
from __future__ import annotations

import html
import os
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from . import paper_capital_allocation_server as base
from .enterprise_manual_strategy_post import submit_manual_strategy_form
from .enterprise_shadow_strategy_promotion_transport import promote_shadow_strategy_in_swing

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
AUTO_PROMOTION_ENABLED = False
MANUAL_STRATEGY_PATH = "/strategy/manual-entry"
SHADOW_PROMOTION_PATH = "/strategy/shadow-promote"


def _response_page(title: str, message: str) -> bytes:
    body = (
        "<section class='panel'>"
        f"<h2>{html.escape(title)}</h2>"
        f"<div class='commentary'>{html.escape(message)}</div>"
        "<p><a href='/executive-dashboard'>Return to Strategy Workspace →</a></p>"
        "</section>"
    )
    return base._layout(title, body, "Executive Dashboard").encode("utf-8")


def _read_form(environ: Mapping[str, Any], *, label: str) -> bytes:
    content_type = str(environ.get("CONTENT_TYPE") or "")
    if content_type and not content_type.lower().startswith("application/x-www-form-urlencoded"):
        raise ValueError(f"{label} requires application/x-www-form-urlencoded")
    length = int(environ.get("CONTENT_LENGTH") or 0)
    if length <= 0 or length > 65536:
        raise ValueError(f"{label} body is missing or too large")
    stream = environ.get("wsgi.input")
    if stream is None:
        raise ValueError(f"{label} request body is unavailable")
    return stream.read(length)


def _manual_strategy_response(environ: Mapping[str, Any]) -> tuple[bytes, str]:
    body = _read_form(environ, label="manual strategy form")
    response = submit_manual_strategy_form(body)
    result = response.get("result") if isinstance(response.get("result"), Mapping) else {}
    strategy_id = str(result.get("strategy_id") or "manual strategy")
    underlying = str(result.get("underlying_symbol") or "underlying")
    mode = str(result.get("assignment_mode") or "DIRECT")
    return (
        _response_page(
            "Manual Strategy Saved",
            f"{strategy_id} was validated and saved by SWING-001 for {underlying} as {mode}. "
            "The host did not write Swing storage directly. Paper-only mode remains enforced.",
        ),
        "200 OK",
    )


def _shadow_promotion_response(environ: Mapping[str, Any]) -> tuple[bytes, str]:
    body = _read_form(environ, label="shadow promotion form")
    values = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    symbol = (values.get("underlying_symbol") or [""])[0].strip().upper()
    strategy_id = (values.get("strategy_id") or [""])[0].strip().upper()
    confirmed = (values.get("user_confirmed") or [""])[0].strip().lower() == "yes"
    if not symbol or not strategy_id:
        raise ValueError("underlying_symbol and strategy_id are required")
    if not confirmed:
        raise PermissionError("explicit user confirmation is required for promotion")
    response = promote_shadow_strategy_in_swing(
        {
            "underlying_symbol": symbol,
            "strategy_id": strategy_id,
            "user_confirmed": True,
        }
    )
    result = response.get("result") if isinstance(response.get("result"), Mapping) else {}
    previous = str(result.get("previous_direct_strategy_id") or "none")
    return (
        _response_page(
            "Shadow Strategy Promoted",
            f"{strategy_id} is now the Direct strategy for {symbol}. Previous Direct strategy: {previous}. "
            "The previous Direct is retained as Shadow. This change occurred only because the user explicitly confirmed promotion.",
        ),
        "200 OK",
    )


def create_wsgi_app(**kwargs: Any) -> Callable:
    """Wrap the established portal with Swing-owned manual strategy governance routes."""
    base_app = base.create_wsgi_app(**kwargs)

    def app(environ: Mapping[str, Any], start_response: Callable) -> Iterable[bytes]:
        path = str(environ.get("PATH_INFO") or "/")
        method = str(environ.get("REQUEST_METHOD") or "GET").upper()
        if method != "POST" or path not in {MANUAL_STRATEGY_PATH, SHADOW_PROMOTION_PATH}:
            return base_app(environ, start_response)
        try:
            if path == MANUAL_STRATEGY_PATH:
                payload, status = _manual_strategy_response(environ)
            else:
                payload, status = _shadow_promotion_response(environ)
        except (ValueError, RuntimeError, PermissionError, TypeError, UnicodeDecodeError) as exc:
            title = "Manual Strategy Not Saved" if path == MANUAL_STRATEGY_PATH else "Shadow Strategy Not Promoted"
            payload = _response_page(title, f"Swing rejected the user-controlled request: {exc}")
            status = "400 Bad Request"
        start_response(
            status,
            [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(payload))),
                ("Cache-Control", "no-store"),
            ],
        )
        return [payload]

    return app


def main() -> int:
    host = os.environ.get("DIVIDEND_ALLOCATION_HOST", "127.0.0.1")
    port = int(os.environ.get("DIVIDEND_ALLOCATION_PORT", "8091"))
    raw = os.environ.get("DIVIDEND_INITIAL_PAPER_CASH")
    initial = float(raw) if raw and raw.strip() else None
    app = create_wsgi_app(
        registry_path=os.environ.get("DIVIDEND_STRATEGY_REGISTRY", str(base.DEFAULT_REGISTRY_PATH)),
        cash_path=os.environ.get("DIVIDEND_PAPER_CASH_STATE", str(base.DEFAULT_CASH_PATH)),
        request_log=os.environ.get("DIVIDEND_ALLOCATION_REQUEST_LOG", str(base.DEFAULT_REQUEST_LOG)),
        transaction_log=os.environ.get("DIVIDEND_CASH_TRANSACTION_LOG", str(base.DEFAULT_CASH_TRANSACTION_PATH)),
        approval_log=os.environ.get("DIVIDEND_ALLOCATION_APPROVAL_LOG", str(base.DEFAULT_APPROVAL_LOG)),
        allocation_transaction_log=os.environ.get("DIVIDEND_ALLOCATION_TRANSACTION_LOG", str(base.DEFAULT_ALLOCATION_TRANSACTION_LOG)),
        executive_dashboard_html=os.environ.get("DIVIDEND_EXECUTIVE_DASHBOARD_HTML", str(base.DEFAULT_EXECUTIVE_DASHBOARD_HTML)),
        executive_dashboard_json=os.environ.get("DIVIDEND_EXECUTIVE_DASHBOARD_JSON", str(base.DEFAULT_EXECUTIVE_DASHBOARD_JSON)),
        investor_dashboard_json=os.environ.get("DIVIDEND_INVESTOR_DASHBOARD_JSON", str(base.DEFAULT_INVESTOR_DASHBOARD_JSON)),
        promotion_requests_path=os.environ.get("DIVIDEND_STRATEGY_PROMOTION_REQUESTS", str(base.DEFAULT_PROMOTION_REQUESTS_PATH)),
        strategy_assignments_path=os.environ.get("DIVIDEND_PAIR_STRATEGY_ASSIGNMENTS", str(base.DEFAULT_ASSIGNMENTS_PATH)),
        strategy_performance_path=os.environ.get("DIVIDEND_STRATEGY_SHADOW_PERFORMANCE", str(base.DEFAULT_STRATEGY_PERFORMANCE_PATH)),
        paper_state_path=os.environ.get("DIVIDEND_PAPER_STATE", str(base.DEFAULT_PAPER_STATE_PATH)),
        promotion_journal_path=os.environ.get("DIVIDEND_STRATEGY_PROMOTION_JOURNAL", str(base.DEFAULT_PROMOTION_JOURNAL_PATH)),
        owner_review_csrf_secret=os.environ.get(base.DEFAULT_OWNER_REVIEW_CSRF_SECRET_ENV),
        investor_id=os.environ.get("DIVIDEND_INVESTOR_ID", "default-investor"),
        initial_paper_cash=initial,
    )
    print(
        f"Investor-controlled paper capital portal listening on http://{host}:{port}/cash "
        f"with Swing manual intake at {MANUAL_STRATEGY_PATH} and user promotion at {SHADOW_PROMOTION_PATH}"
    )
    with make_server(host, port, app) as server:
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
