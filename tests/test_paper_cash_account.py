import json
from pathlib import Path

import pytest

from src.dividend_bot.paper_cash_account import (
    BROKER_EXECUTION_ENABLED,
    CAPITAL_MOVEMENT_ENABLED,
    LIVE_TRADING_ENABLED,
    PAPER_TRADE_MODE,
    available_cash,
    build_cash_account,
    initialize_cash_account,
    read_cash_account,
    validate_cash_account,
    write_cash_account,
)
from src.dividend_bot.paper_capital_allocation_server import create_wsgi_app


def test_safety_constants_are_locked():
    assert PAPER_TRADE_MODE is True
    assert LIVE_TRADING_ENABLED is False
    assert BROKER_EXECUTION_ENABLED is False
    assert CAPITAL_MOVEMENT_ENABLED is False


def test_build_cash_account_uses_investor_money():
    account = build_cash_account(125000, generated_at_utc="2026-07-25T00:00:00Z")
    assert account["starting_cash"] == 125000.0
    assert account["available_cash"] == 125000.0
    assert account["currency"] == "USD"
    assert account["source"] == "INVESTOR_SUPPLIED_PAPER_CAPITAL"


def test_negative_investor_money_is_rejected():
    with pytest.raises(ValueError):
        build_cash_account(-1)


def test_write_and_read_cash_account(tmp_path: Path):
    path = tmp_path / "state" / "paper_cash_account.json"
    write_cash_account(build_cash_account(50000), path)
    loaded = read_cash_account(path)
    assert loaded["available_cash"] == 50000.0
    assert available_cash(loaded) == 50000.0


def test_initialize_from_environment(tmp_path: Path):
    path = tmp_path / "paper_cash_account.json"
    account = initialize_cash_account(
        path=path,
        environment={"DIVIDEND_INITIAL_PAPER_CASH": "75000.50"},
    )
    assert account["available_cash"] == 75000.50
    assert json.loads(path.read_text())["starting_cash"] == 75000.50


def test_existing_account_is_not_overwritten_by_default(tmp_path: Path):
    path = tmp_path / "paper_cash_account.json"
    initialize_cash_account(path=path, investor_money=10000)
    account = initialize_cash_account(path=path, investor_money=90000)
    assert account["available_cash"] == 10000.0


def test_overwrite_requires_explicit_flag(tmp_path: Path):
    path = tmp_path / "paper_cash_account.json"
    initialize_cash_account(path=path, investor_money=10000)
    account = initialize_cash_account(path=path, investor_money=90000, overwrite=True)
    assert account["available_cash"] == 90000.0


def test_missing_initial_amount_is_rejected(tmp_path: Path):
    with pytest.raises(RuntimeError):
        initialize_cash_account(path=tmp_path / "cash.json", environment={})


def test_validation_rejects_balance_over_starting_cash():
    account = build_cash_account(1000)
    account["allocated_cash"] = 100.0
    with pytest.raises(ValueError):
        validate_cash_account(account)


def test_allocation_server_initializes_cash_state(tmp_path: Path):
    cash_path = tmp_path / "state" / "paper_cash_account.json"
    registry_path = tmp_path / "registry.json"
    registry_path.write_text('{"strategy_plugins": []}', encoding="utf-8")
    create_wsgi_app(
        registry_path=registry_path,
        cash_path=cash_path,
        request_log=tmp_path / "requests.jsonl",
        initial_paper_cash=25000,
    )
    assert read_cash_account(cash_path)["available_cash"] == 25000.0
