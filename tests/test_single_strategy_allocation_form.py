from __future__ import annotations

import io
import json
from pathlib import Path

from src.dividend_bot.paper_capital_allocation import (
    parse_allocation_form,
    render_allocation_html,
)
from src.dividend_bot.paper_capital_allocation_server import (
    create_wsgi_app,
    render_allocation_page,
)


PLUGIN = {
    "strategy_id": "dividend",
    "display_name": "Dividend Income Strategy",
    "status": "READY",
    "health": "HEALTHY",
    "enabled": True,
    "paper_trade_mode": True,
    "strategy_plugin": True,
}


def _call_app(app, method: str, path: str, body: bytes = b"") -> tuple[str, str]:
    response: dict[str, str] = {}

    def start_response(status: str, headers) -> None:
        response["status"] = status

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
    }
    payload = b"".join(app(environ, start_response)).decode("utf-8")
    return response["status"], payload


def test_single_selected_strategy_automatically_receives_requested_cash() -> None:
    requested, allocations = parse_allocation_form(
        b"requested_cash=5000&strategy=dividend"
    )

    assert requested == 5000
    assert allocations == {"dividend": 5000}


def test_explicit_single_strategy_amount_remains_supported() -> None:
    requested, allocations = parse_allocation_form(
        b"requested_cash=5000&strategy=dividend&amount_dividend=5000"
    )

    assert requested == 5000
    assert allocations == {"dividend": 5000}


def test_core_single_strategy_html_has_no_duplicate_amount_input() -> None:
    page = render_allocation_html(
        available_cash=10000,
        strategy_plugins=[PLUGIN],
    )

    assert 'name="strategy" value="dividend"' in page
    assert 'name="amount_dividend"' not in page
    assert "100% of request" in page
    assert "Automatically assigned from the total above" in page


def test_dashboard_single_strategy_shows_current_allocation_as_read_only() -> None:
    page = render_allocation_page(
        10000,
        [PLUGIN],
        allocated_cash=1250,
    )

    assert 'name="amount_dividend"' not in page
    assert "Currently allocated" in page
    assert "$1,250.00" in page
    assert "The total entered above will be assigned automatically." in page


def test_wsgi_single_strategy_request_requires_only_top_amount(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    cash = tmp_path / "cash.json"
    request_log = tmp_path / "requests.jsonl"
    registry.write_text(json.dumps({"strategy_plugins": [PLUGIN]}), encoding="utf-8")
    cash.write_text(
        json.dumps({"available_cash": 10000, "allocated_cash": 0}),
        encoding="utf-8",
    )
    app = create_wsgi_app(
        registry_path=registry,
        cash_path=cash,
        request_log=request_log,
    )

    status, page = _call_app(
        app,
        "POST",
        "/allocation/request",
        b"requested_cash=5000&strategy=dividend",
    )

    assert status == "201 Created"
    assert "PENDING_GOVERNANCE_REVIEW" in page
    recorded = json.loads(request_log.read_text(encoding="utf-8").strip())
    assert recorded["requested_cash"] == 5000
    assert recorded["allocations"] == [
        {
            "amount": 5000.0,
            "percentage_of_request": 100.0,
            "strategy_id": "dividend",
            "strategy_name": "Dividend Income Strategy",
        }
    ]


def test_multiple_strategy_form_still_supports_manual_split() -> None:
    second = {
        **PLUGIN,
        "strategy_id": "income-secondary",
        "display_name": "Secondary Income Strategy",
    }
    page = render_allocation_page(10000, [PLUGIN, second])

    assert 'name="amount_dividend"' in page
    assert 'name="amount_income-secondary"' in page
    assert "divide the total amount among them" in page
