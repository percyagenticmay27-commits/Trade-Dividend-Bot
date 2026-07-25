"""Persistent paper-only cash account for investor-supplied simulated capital."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

MODULE_NAME = "paper_cash_account"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False

DEFAULT_CASH_ACCOUNT_PATH = Path("state/paper_cash_account.json")
DEFAULT_INITIAL_CASH_ENV = "DIVIDEND_INITIAL_PAPER_CASH"


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_cash_account(
    investor_money: float,
    *,
    investor_id: str = "default-investor",
    currency: str = "USD",
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Build the canonical paper cash account state."""
    amount = round(float(investor_money), 2)
    if amount < 0:
        raise ValueError("investor_money cannot be negative")
    generated = generated_at_utc or _now_utc()
    return {
        "schema_version": SCHEMA_VERSION,
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "generated_at_utc": generated,
        "investor_id": investor_id,
        "currency": currency,
        "starting_cash": amount,
        "available_cash": amount,
        "reserved_cash": 0.0,
        "allocated_cash": 0.0,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "source": "INVESTOR_SUPPLIED_PAPER_CAPITAL",
    }


def validate_cash_account(account: Mapping[str, Any]) -> None:
    required = (
        "investor_id",
        "currency",
        "starting_cash",
        "available_cash",
        "reserved_cash",
        "allocated_cash",
    )
    missing = [name for name in required if name not in account]
    if missing:
        raise ValueError("missing cash account fields: " + ", ".join(missing))
    amounts = {name: round(float(account[name]), 2) for name in ("starting_cash", "available_cash", "reserved_cash", "allocated_cash")}
    if any(value < 0 for value in amounts.values()):
        raise ValueError("cash account amounts cannot be negative")
    if round(amounts["available_cash"] + amounts["reserved_cash"] + amounts["allocated_cash"], 2) > amounts["starting_cash"]:
        raise ValueError("cash account balances cannot exceed starting_cash")
    if account.get("paper_trade_mode") is not True:
        raise ValueError("paper_trade_mode must remain true")
    if account.get("live_trading_enabled") is not False or account.get("broker_execution_enabled") is not False:
        raise ValueError("live trading and broker execution must remain disabled")


def write_cash_account(account: Mapping[str, Any], path: str | Path = DEFAULT_CASH_ACCOUNT_PATH) -> Path:
    validate_cash_account(account)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(dict(account), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return destination


def read_cash_account(path: str | Path = DEFAULT_CASH_ACCOUNT_PATH) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        return {}
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("paper cash account must be a JSON object")
    validate_cash_account(value)
    return value


def initialize_cash_account(
    *,
    path: str | Path = DEFAULT_CASH_ACCOUNT_PATH,
    investor_money: Optional[float] = None,
    investor_id: str = "default-investor",
    environment: Optional[Mapping[str, str]] = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create the account once from an explicit value or environment variable."""
    destination = Path(path)
    if destination.is_file() and not overwrite:
        return read_cash_account(destination)
    values = dict(os.environ if environment is None else environment)
    raw_amount = investor_money if investor_money is not None else values.get(DEFAULT_INITIAL_CASH_ENV)
    if raw_amount is None or str(raw_amount).strip() == "":
        raise RuntimeError(f"Set {DEFAULT_INITIAL_CASH_ENV} or provide investor_money")
    account = build_cash_account(float(raw_amount), investor_id=investor_id)
    write_cash_account(account, destination)
    return account


def available_cash(account: Mapping[str, Any]) -> float:
    validate_cash_account(account)
    return round(float(account["available_cash"]), 2)
