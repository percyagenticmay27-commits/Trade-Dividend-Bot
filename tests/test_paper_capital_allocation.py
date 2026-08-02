from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from src.dividend_bot.paper_capital_allocation import (
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
from src.dividend_bot.paper_capital_allocation_server import (available_cash_from_state, create_wsgi_app, render_allocation_page)


REGISTRY = {
    "strategy_plugins": [
        {"strategy_id": "dividend-income", "display_name": "Dividend Income", "status": "ONLINE", "enabled": True, "paper_trade_mode": True, "health": "HEALTHY"},
        {"strategy_id": "swing", "display_name": "Swing Trading", "status": "DISABLED", "enabled": False, "paper_trade_mode": True},
        {"strategy_id": "options", "display_name": "Options", "status": "ONLINE", "enabled": True, "paper_trade_mode": False},
    ]
}


def plugins():
    return discover_strategy_plugins(REGISTRY)


def test_safety_constants_locked():
    assert PAPER_TRADE_MODE is True
    assert LIVE_TRADING_ENABLED is False
    assert BROKER_EXECUTION_ENABLED is False
    assert CAPITAL_MOVEMENT_ENABLED is False


def test_discovers_only_enabled_paper_plugins():
    assert [item["strategy_id"] for item in plugins()] == ["dividend-income"]


def test_service_registry_shape_is_supported():
    result = discover_strategy_plugins({"services": [{"service_id": "dividend-strategy", "service_type": "STRATEGY", "status": "READY"}]})
    assert result[0]["strategy_id"] == "dividend-strategy"


def test_request_is_deterministic_with_fixed_timestamp():
    kwargs = dict(available_cash=1000, requested_cash=250, allocations={"dividend-income": 250}, strategy_plugins=plugins(), created_at_utc="2026-07-25T20:00:00Z")
    assert build_allocation_request(**kwargs)["request_id"] == build_allocation_request(**kwargs)["request_id"]


def test_request_records_governance_and_remaining_cash():
    request = build_allocation_request(available_cash=1000, requested_cash=250, allocations={"dividend-income": 250}, strategy_plugins=plugins(), created_at_utc="2026-07-25T20:00:00Z")
    assert request["status"] == "PENDING_GOVERNANCE_REVIEW"
    assert request["unassigned_cash_after_request"] == 750
    assert request["governance"]["automatic_activation_allowed"] is False


@pytest.mark.parametrize("requested", [0, -1, 1001])
def test_invalid_requested_cash_is_rejected(requested):
    with pytest.raises(ValueError):
        build_allocation_request(available_cash=1000, requested_cash=requested, allocations={"dividend-income": requested}, strategy_plugins=plugins())


def test_unregistered_strategy_is_rejected():
    with pytest.raises(ValueError, match="not registered"):
        build_allocation_request(available_cash=1000, requested_cash=100, allocations={"swing": 100}, strategy_plugins=plugins())


def test_allocations_must_equal_requested_cash():
    with pytest.raises(ValueError, match="must equal"):
        build_allocation_request(available_cash=1000, requested_cash=100, allocations={"dividend-income": 50}, strategy_plugins=plugins())


def test_append_only_log_prevents_duplicate(tmp_path: Path):
    request = build_allocation_request(available_cash=1000, requested_cash=100, allocations={"dividend-income": 100}, strategy_plugins=plugins(), created_at_utc="2026-07-25T20:00:00Z")
    path = tmp_path / "requests.jsonl"
    assert append_allocation_request(request, path) is True
    assert append_allocation_request(request, path) is False
    assert len(path.read_text().splitlines()) == 1


def test_html_contains_cash_registered_strategy_and_safety_text():
    page = render_allocation_html(available_cash=1250.5, strategy_plugins=plugins())
    assert "$1,250.50" in page
    assert "Dividend Income" in page
    assert "PAPER ONLY" in page
    assert "Swing Trading" not in page



def test_allocation_page_resolves_canonical_dividend_balance_for_legacy_registry_id():
    page = render_allocation_page(
        500,
        [{"strategy_id": "DIVIDEND", "display_name": "Dividend Income Strategy", "status": "READY", "health": "HEALTHY"}],
        {"DIVIDEND-001": 5000.0, "SWING-001": 4500.0},
    )
    assert "Currently allocated: $5,000.00" in page


def test_allocation_page_preserves_exact_swing_balance():
    page = render_allocation_page(
        500,
        [{"strategy_id": "SWING-001", "display_name": "Trade Swing Bot", "status": "AVAILABLE", "health": "HEALTHY"}],
        {"DIVIDEND-001": 5000.0, "SWING-001": 4500.0},
    )
    assert "Currently allocated: $4,500.00" in page

def test_form_parser_reads_selected_allocations():
    requested, allocations = parse_allocation_form(b"requested_cash=200&strategy=dividend-income&amount_dividend-income=200")
    assert requested == 200
    assert allocations == {"dividend-income": 200}


def test_available_cash_flexible_shapes():
    assert available_cash_from_state({"available_cash": 500}) == 500
    assert available_cash_from_state({"summary": {"unallocated_cash": 725.25}}) == 725.25
    assert available_cash_from_state({}) == 0


def _call_app(app, method, path, body=b""):
    status = {}
    def start_response(value, headers):
        status["value"] = value
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body)}
    payload = b"".join(app(environ, start_response)).decode()
    return status["value"], payload


def test_wsgi_get_and_post_record_request(tmp_path: Path):
    registry = tmp_path / "registry.json"
    cash = tmp_path / "cash.json"
    log = tmp_path / "requests.jsonl"
    registry.write_text(json.dumps(REGISTRY))
    cash.write_text(json.dumps({"available_cash": 500}))
    app = create_wsgi_app(registry_path=registry, cash_path=cash, request_log=log)
    status, page = _call_app(app, "GET", "/allocation")
    assert status == "200 OK" and "Dividend Income" in page
    status, page = _call_app(app, "POST", "/allocation/request", b"requested_cash=200&strategy=dividend-income&amount_dividend-income=200")
    assert status == "201 Created"
    assert "No cash has been transferred" in page
    assert "Approve and Apply Paper Allocation" in page
    assert log.exists()


def test_wsgi_rejects_excess_cash(tmp_path: Path):
    registry = tmp_path / "registry.json"
    cash = tmp_path / "cash.json"
    registry.write_text(json.dumps(REGISTRY))
    cash.write_text(json.dumps({"available_cash": 100}))
    app = create_wsgi_app(registry_path=registry, cash_path=cash, request_log=tmp_path / "log.jsonl")
    status, _ = _call_app(app, "POST", "/allocation/request", b"requested_cash=200&strategy=dividend-income&amount_dividend-income=200")
    assert status == "400 Bad Request"
