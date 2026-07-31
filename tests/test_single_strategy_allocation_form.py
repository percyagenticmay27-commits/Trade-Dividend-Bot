from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from src.dividend_bot.paper_capital_allocation import (
    build_allocation_request,
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
SWING_PLUGIN = {
    **PLUGIN,
    "strategy_id": "SWING-001",
    "display_name": "Trade Swing Bot",
    "status": "AVAILABLE",
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
        b"requested_cash=5000&strategy=SWING-001"
    )

    assert requested == 5000
    assert allocations == {"SWING-001": 5000}


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


def test_dashboard_strategy_rows_show_current_allocation_as_read_only() -> None:
    page = render_allocation_page(
        10000,
        [PLUGIN, SWING_PLUGIN],
        strategy_allocations={"dividend": 1250, "SWING-001": 750},
    )

    assert "Currently allocated: $1,250.00" in page
    assert "Currently allocated: $750.00" in page
    assert 'name="amount_dividend"' in page
    assert 'name="amount_SWING-001"' in page
    assert "data-allocation-amount disabled" in page


def test_dashboard_contains_single_selection_auto_assignment_controls() -> None:
    page = render_allocation_page(10000, [PLUGIN, SWING_PLUGIN])

    assert "Proposed allocation: 100% of requested cash" in page
    assert "selected.length===1" in page
    assert "assigned=total" in page
    assert "amount.disabled=!manual" in page
    assert "amount.required=manual" in page


def test_dashboard_always_displays_live_allocation_summary() -> None:
    page = render_allocation_page(10000, [PLUGIN, SWING_PLUGIN])

    assert "Total requested" in page
    assert "Total assigned" in page
    assert "Remaining unassigned" in page
    assert "summary-requested" in page
    assert "summary-assigned" in page
    assert "summary-remaining" in page


def test_wsgi_single_strategy_request_requires_only_top_amount(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    cash = tmp_path / "cash.json"
    request_log = tmp_path / "requests.jsonl"
    registry.write_text(json.dumps({"strategy_plugins": [PLUGIN, SWING_PLUGIN]}), encoding="utf-8")
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
        b"requested_cash=5000&strategy=SWING-001",
    )

    assert status == "201 Created"
    assert "PENDING_GOVERNANCE_REVIEW" in page
    assert "Approve and Apply Paper Allocation" in page
    recorded = json.loads(request_log.read_text(encoding="utf-8").strip())
    assert recorded["requested_cash"] == 5000
    assert recorded["allocations"] == [
        {
            "amount": 5000.0,
            "percentage_of_request": 100.0,
            "strategy_id": "SWING-001",
            "strategy_name": "Trade Swing Bot",
        }
    ]


def test_multiple_strategy_form_still_supports_manual_split() -> None:
    requested, allocations = parse_allocation_form(
        b"requested_cash=5000&strategy=dividend&strategy=SWING-001&amount_dividend=1500&amount_SWING-001=3500"
    )
    request = build_allocation_request(
        available_cash=10000,
        requested_cash=requested,
        allocations=allocations,
        strategy_plugins=[PLUGIN, SWING_PLUGIN],
    )

    assert request["requested_cash"] == 5000
    assert request["allocations"] == [
        {
            "strategy_id": "SWING-001",
            "strategy_name": "Trade Swing Bot",
            "amount": 3500.0,
            "percentage_of_request": 70.0,
        },
        {
            "strategy_id": "dividend",
            "strategy_name": "Dividend Income Strategy",
            "amount": 1500.0,
            "percentage_of_request": 30.0,
        },
    ]


def test_multiple_selected_strategies_require_exact_split() -> None:
    requested, allocations = parse_allocation_form(
        b"requested_cash=5000&strategy=dividend&strategy=SWING-001&amount_dividend=1000&amount_SWING-001=3000"
    )

    with pytest.raises(ValueError, match="strategy allocations must equal requested_cash"):
        build_allocation_request(
            available_cash=10000,
            requested_cash=requested,
            allocations=allocations,
            strategy_plugins=[PLUGIN, SWING_PLUGIN],
        )


def test_zero_selected_strategy_allocation_is_rejected() -> None:
    requested, allocations = parse_allocation_form(b"requested_cash=5000")

    with pytest.raises(ValueError, match="at least one strategy allocation is required"):
        build_allocation_request(
            available_cash=10000,
            requested_cash=requested,
            allocations=allocations,
            strategy_plugins=[PLUGIN, SWING_PLUGIN],
        )


def test_unselected_strategy_amount_is_ignored() -> None:
    requested, allocations = parse_allocation_form(
        b"requested_cash=5000&strategy=SWING-001&amount_dividend=2500"
    )

    assert requested == 5000
    assert allocations == {"SWING-001": 5000}
