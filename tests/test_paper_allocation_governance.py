from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from src.dividend_bot.paper_allocation_governance import (
    APPROVED_STATUS,
    approve_allocation_request,
    build_approved_allocation,
    latest_governance_decision,
)
from src.dividend_bot.paper_capital_allocation import build_allocation_request
from src.dividend_bot.paper_capital_allocation_server import create_wsgi_app
from src.dividend_bot.paper_cash_account import build_cash_account, read_cash_account, write_cash_account


def _plugin() -> dict:
    return {
        "strategy_id": "dividend",
        "display_name": "Dividend Income Strategy",
        "status": "READY",
        "health": "HEALTHY",
        "paper_trade_mode": True,
    }


def _request() -> dict:
    return build_allocation_request(
        available_cash=10000,
        requested_cash=5000,
        allocations={"dividend": 5000},
        strategy_plugins=[_plugin()],
        investor_id="default-investor",
        created_at_utc="2026-07-30T18:00:00Z",
    )


def _write_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")


def _call(app, method: str, path: str, body: str = "") -> tuple[str, str]:
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = headers

    encoded = body.encode("utf-8")
    result = app(
        {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "CONTENT_LENGTH": str(len(encoded)),
            "wsgi.input": io.BytesIO(encoded),
        },
        start_response,
    )
    return captured["status"], b"".join(result).decode("utf-8")


def test_build_approved_allocation_moves_only_paper_balances():
    updated, decision, transaction = build_approved_allocation(
        request=_request(),
        account=build_cash_account(10000, generated_at_utc="2026-07-30T17:00:00Z"),
        investor_id="default-investor",
        investor_confirmed=True,
        decided_at_utc="2026-07-30T18:05:00Z",
    )

    assert updated["available_cash"] == 5000
    assert updated["allocated_cash"] == 5000
    assert updated["strategy_allocations"] == {"dividend": 5000}
    assert decision["status"] == APPROVED_STATUS
    assert decision["paper_trade_mode"] is True
    assert decision["live_trading_enabled"] is False
    assert decision["broker_execution_enabled"] is False
    assert decision["capital_movement_enabled"] is False
    assert transaction["status"] == "APPLIED_TO_PAPER_ACCOUNT"


def test_approval_requires_explicit_investor_confirmation():
    with pytest.raises(ValueError, match="investor approval confirmation"):
        build_approved_allocation(
            request=_request(),
            account=build_cash_account(10000),
            investor_id="default-investor",
            investor_confirmed=False,
        )


def test_approval_rejects_insufficient_available_cash():
    with pytest.raises(ValueError, match="exceeds available paper cash"):
        build_approved_allocation(
            request=_request(),
            account=build_cash_account(4000),
            investor_id="default-investor",
            investor_confirmed=True,
        )


def test_approval_rejects_investor_mismatch():
    with pytest.raises(PermissionError, match="does not match"):
        build_approved_allocation(
            request=_request(),
            account=build_cash_account(10000),
            investor_id="another-investor",
            investor_confirmed=True,
        )


def test_approve_allocation_request_is_idempotent(tmp_path: Path):
    request_log = tmp_path / "requests.jsonl"
    account_path = tmp_path / "cash.json"
    approval_log = tmp_path / "approvals.jsonl"
    transaction_log = tmp_path / "transactions.jsonl"
    _write_jsonl(request_log, _request())
    write_cash_account(build_cash_account(10000), account_path)

    first = approve_allocation_request(
        request_id=_request()["request_id"],
        request_log=request_log,
        account_path=account_path,
        approval_log=approval_log,
        transaction_log=transaction_log,
        investor_confirmed=True,
    )
    second = approve_allocation_request(
        request_id=_request()["request_id"],
        request_log=request_log,
        account_path=account_path,
        approval_log=approval_log,
        transaction_log=transaction_log,
        investor_confirmed=True,
    )

    assert first == second
    assert read_cash_account(account_path)["allocated_cash"] == 5000
    assert len(approval_log.read_text(encoding="utf-8").splitlines()) == 1
    assert len(transaction_log.read_text(encoding="utf-8").splitlines()) == 1
    assert latest_governance_decision(_request()["request_id"], approval_log)["status"] == APPROVED_STATUS


def test_request_confirmation_exposes_governed_approval_action(tmp_path: Path):
    registry_path = tmp_path / "registry.json"
    cash_path = tmp_path / "cash.json"
    request_log = tmp_path / "requests.jsonl"
    registry_path.write_text(json.dumps({"strategy_plugins": [_plugin()]}), encoding="utf-8")
    write_cash_account(build_cash_account(10000), cash_path)
    app = create_wsgi_app(registry_path=registry_path, cash_path=cash_path, request_log=request_log)

    status, payload = _call(app, "POST", "/allocation/request", "requested_cash=5000&strategy=dividend")

    assert status == "201 Created"
    assert "PENDING_GOVERNANCE_REVIEW" in payload
    assert "Approve and Apply Paper Allocation" in payload
    assert "/allocation/approve" in payload
    assert "No cash has been transferred" in payload
    assert read_cash_account(cash_path)["available_cash"] == 10000


def test_wsgi_approval_applies_paper_allocation(tmp_path: Path):
    registry_path = tmp_path / "registry.json"
    cash_path = tmp_path / "cash.json"
    request_log = tmp_path / "requests.jsonl"
    approval_log = tmp_path / "approvals.jsonl"
    allocation_transaction_log = tmp_path / "allocation_transactions.jsonl"
    registry_path.write_text(json.dumps({"strategy_plugins": [_plugin()]}), encoding="utf-8")
    write_cash_account(build_cash_account(10000), cash_path)
    request = _request()
    _write_jsonl(request_log, request)
    app = create_wsgi_app(
        registry_path=registry_path,
        cash_path=cash_path,
        request_log=request_log,
        approval_log=approval_log,
        allocation_transaction_log=allocation_transaction_log,
    )

    status, payload = _call(
        app,
        "POST",
        "/allocation/approve",
        f"request_id={request['request_id']}&investor_confirmed=yes",
    )

    account = read_cash_account(cash_path)
    assert status == "200 OK"
    assert "Paper Allocation Applied" in payload
    assert "Available cash: $5,000.00" in payload
    assert "Allocated cash: $5,000.00" in payload
    assert "No order was placed" in payload
    assert account["available_cash"] == 5000
    assert account["allocated_cash"] == 5000
    assert account["strategy_allocations"] == {"dividend": 5000}


def test_wsgi_approval_requires_checkbox(tmp_path: Path):
    registry_path = tmp_path / "registry.json"
    cash_path = tmp_path / "cash.json"
    request_log = tmp_path / "requests.jsonl"
    registry_path.write_text(json.dumps({"strategy_plugins": [_plugin()]}), encoding="utf-8")
    write_cash_account(build_cash_account(10000), cash_path)
    request = _request()
    _write_jsonl(request_log, request)
    app = create_wsgi_app(registry_path=registry_path, cash_path=cash_path, request_log=request_log)

    status, payload = _call(app, "POST", "/allocation/approve", f"request_id={request['request_id']}")

    assert status == "400 Bad Request"
    assert "investor approval confirmation is required" in payload
    assert read_cash_account(cash_path)["available_cash"] == 10000


def test_allocation_page_shows_strategy_specific_current_allocation(tmp_path: Path):
    registry_path = tmp_path / "registry.json"
    cash_path = tmp_path / "cash.json"
    registry_path.write_text(json.dumps({"strategy_plugins": [_plugin()]}), encoding="utf-8")
    account = build_cash_account(10000)
    account["available_cash"] = 5000
    account["allocated_cash"] = 5000
    account["strategy_allocations"] = {"dividend": 5000}
    write_cash_account(account, cash_path)
    app = create_wsgi_app(registry_path=registry_path, cash_path=cash_path)

    status, payload = _call(app, "GET", "/allocation")

    assert status == "200 OK"
    assert "Currently allocated" in payload
    assert "$5,000.00" in payload
