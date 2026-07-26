import io
import json
from pathlib import Path

import pytest

from src.dividend_bot.paper_cash_account import (
    PAPER_PROVIDER,
    ROBINHOOD_PROVIDER,
    apply_paper_deposit,
    build_cash_account,
    build_paper_deposit,
    require_investor_live_authorization,
    resolve_cash_provider,
    write_cash_account,
)
from src.dividend_bot.paper_capital_allocation_server import create_wsgi_app, render_cash_account_html


def _call(app, method, path, body=b""):
    result = {}
    def start_response(status, headers):
        result["status"] = status
        result["headers"] = headers
    payload = b"".join(app({"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body)}, start_response))
    return result["status"], payload.decode("utf-8")


def test_default_cash_provider_is_paper():
    assert resolve_cash_provider({}) == PAPER_PROVIDER


def test_future_robinhood_provider_requires_investor_approval():
    with pytest.raises(PermissionError):
        require_investor_live_authorization(investor_approved=False, provider=ROBINHOOD_PROVIDER)
    require_investor_live_authorization(investor_approved=True, provider=ROBINHOOD_PROVIDER)


def test_build_paper_deposit_increases_available_and_starting_cash():
    updated, transaction = build_paper_deposit(account=build_cash_account(1000), amount=250, created_at_utc="2026-07-25T00:00:00Z")
    assert updated["starting_cash"] == 1250.0
    assert updated["available_cash"] == 1250.0
    assert transaction["balance_before"] == 1000.0
    assert transaction["balance_after"] == 1250.0
    assert transaction["status"] == "CONFIRMED_BY_INVESTOR"


def test_apply_paper_deposit_updates_account_and_appends_audit_record(tmp_path: Path):
    account_path = tmp_path / "state" / "paper_cash_account.json"
    transaction_path = tmp_path / "state" / "paper_cash_transactions.jsonl"
    write_cash_account(build_cash_account(5000), account_path)
    transaction = apply_paper_deposit(account_path=account_path, transaction_path=transaction_path, amount=1000, created_at_utc="2026-07-25T00:00:00Z")
    account = json.loads(account_path.read_text())
    assert account["available_cash"] == 6000.0
    assert transaction["amount"] == 1000.0
    assert len(transaction_path.read_text().splitlines()) == 1


def test_cash_page_uses_ai_cio_dashboard_template():
    page = render_cash_account_html(build_cash_account(125000))
    assert "Enterprise AI CIO" in page
    assert "Starting Paper Cash" in page
    assert "Available Cash" in page
    assert "Add Simulated Capital" in page
    assert "Only the investor can authorize future live mode" in page
    assert "/allocation" in page


def test_wsgi_cash_deposit_then_allocation_page_reads_new_balance(tmp_path: Path):
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"strategy_plugins": [{"strategy_id": "dividend-income", "display_name": "Dividend Income", "strategy_plugin": True, "status": "ONLINE", "paper_trade_mode": True}]}))
    cash = tmp_path / "cash.json"
    write_cash_account(build_cash_account(1000), cash)
    app = create_wsgi_app(registry_path=registry, cash_path=cash, request_log=tmp_path / "requests.jsonl", transaction_log=tmp_path / "transactions.jsonl")
    status, _ = _call(app, "POST", "/cash/deposit", b"amount=500&reason=ADDITIONAL_PAPER_DEPOSIT&investor_confirmed=yes")
    assert status.startswith("201")
    status, page = _call(app, "GET", "/allocation")
    assert status.startswith("200")
    assert "$1,500.00" in page
    assert "Dividend Income" in page


def test_cash_deposit_requires_investor_confirmation(tmp_path: Path):
    cash = tmp_path / "cash.json"
    write_cash_account(build_cash_account(1000), cash)
    app = create_wsgi_app(registry_path=tmp_path / "missing.json", cash_path=cash, request_log=tmp_path / "requests.jsonl", transaction_log=tmp_path / "transactions.jsonl")
    status, body = _call(app, "POST", "/cash/deposit", b"amount=500")
    assert status.startswith("400")
    assert "investor confirmation is required" in body
