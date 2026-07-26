"""Persistent investor-controlled cash account for paper mode and future live providers."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

MODULE_NAME = "paper_cash_account"
MODULE_VERSION = "1.1.0"
SCHEMA_VERSION = "1.1"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
INVESTOR_CONTROLS_LIVE_MODE = True

DEFAULT_CASH_ACCOUNT_PATH = Path("state/paper_cash_account.json")
DEFAULT_CASH_TRANSACTION_PATH = Path("state/paper_cash_transactions.jsonl")
DEFAULT_INITIAL_CASH_ENV = "DIVIDEND_INITIAL_PAPER_CASH"
DEFAULT_CASH_PROVIDER_ENV = "CASH_ACCOUNT_PROVIDER"
PAPER_PROVIDER = "PAPER"
ROBINHOOD_PROVIDER = "ROBINHOOD"
SUPPORTED_PROVIDERS = {PAPER_PROVIDER, ROBINHOOD_PROVIDER}


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_cash_provider(environment: Optional[Mapping[str, str]] = None) -> str:
    values = dict(os.environ if environment is None else environment)
    provider = str(values.get(DEFAULT_CASH_PROVIDER_ENV, PAPER_PROVIDER)).strip().upper()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"unsupported cash account provider: {provider}")
    return provider


def build_cash_account(
    investor_money: float,
    *,
    investor_id: str = "default-investor",
    currency: str = "USD",
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
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
        "cash_account_provider": PAPER_PROVIDER,
        "starting_cash": amount,
        "available_cash": amount,
        "reserved_cash": 0.0,
        "allocated_cash": 0.0,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "investor_controls_live_mode": True,
        "source": "INVESTOR_SUPPLIED_PAPER_CAPITAL",
    }


def validate_cash_account(account: Mapping[str, Any]) -> None:
    required = (
        "investor_id", "currency", "starting_cash", "available_cash", "reserved_cash", "allocated_cash"
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


def build_paper_deposit(
    *, account: Mapping[str, Any], amount: float, reason: str = "ADDITIONAL_PAPER_DEPOSIT",
    investor_id: Optional[str] = None, created_at_utc: Optional[str] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_cash_account(account)
    deposit = round(float(amount), 2)
    if deposit <= 0:
        raise ValueError("paper deposit amount must be greater than zero")
    created = created_at_utc or _now_utc()
    before = round(float(account["available_cash"]), 2)
    after = round(before + deposit, 2)
    updated = dict(account)
    updated["starting_cash"] = round(float(account["starting_cash"]) + deposit, 2)
    updated["available_cash"] = after
    updated["generated_at_utc"] = created
    updated["module_version"] = MODULE_VERSION
    identity = json.dumps({"investor_id": investor_id or account["investor_id"], "amount": deposit, "created_at_utc": created, "reason": reason}, sort_keys=True)
    transaction_id = "PCT-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16].upper()
    transaction = {
        "transaction_id": transaction_id,
        "created_at_utc": created,
        "transaction_type": "PAPER_DEPOSIT",
        "reason": str(reason).strip() or "ADDITIONAL_PAPER_DEPOSIT",
        "investor_id": investor_id or account["investor_id"],
        "currency": account["currency"],
        "amount": deposit,
        "balance_before": before,
        "balance_after": after,
        "status": "CONFIRMED_BY_INVESTOR",
        "cash_account_provider": PAPER_PROVIDER,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "investor_controls_live_mode": True,
    }
    validate_cash_account(updated)
    return updated, transaction


def append_cash_transaction(transaction: Mapping[str, Any], path: str | Path = DEFAULT_CASH_TRANSACTION_PATH) -> bool:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    transaction_id = str(transaction.get("transaction_id") or "")
    if not transaction_id:
        raise ValueError("transaction_id is required")
    if destination.exists():
        for line in destination.read_text(encoding="utf-8").splitlines():
            if line.strip() and json.loads(line).get("transaction_id") == transaction_id:
                return False
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(transaction), sort_keys=True) + "\n")
    return True


def apply_paper_deposit(
    *, account_path: str | Path = DEFAULT_CASH_ACCOUNT_PATH,
    transaction_path: str | Path = DEFAULT_CASH_TRANSACTION_PATH,
    amount: float, reason: str = "ADDITIONAL_PAPER_DEPOSIT",
    investor_id: Optional[str] = None, created_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    account = read_cash_account(account_path)
    if not account:
        raise RuntimeError("paper cash account has not been initialized")
    updated, transaction = build_paper_deposit(account=account, amount=amount, reason=reason, investor_id=investor_id, created_at_utc=created_at_utc)
    if not append_cash_transaction(transaction, transaction_path):
        return transaction
    write_cash_account(updated, account_path)
    return transaction


def require_investor_live_authorization(*, investor_approved: bool, provider: str) -> None:
    """Future-live guard: only the investor can authorize transition from paper to live."""
    normalized = str(provider).upper()
    if normalized == ROBINHOOD_PROVIDER and not investor_approved:
        raise PermissionError("investor approval is required before Robinhood live synchronization")
