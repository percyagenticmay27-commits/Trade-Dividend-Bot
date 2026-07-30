"""Investor-governed approval and application of paper allocation requests.

This module changes simulated cash balances only. It never contacts a broker,
places an order, enables live trading, or moves real capital.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from .paper_cash_account import read_cash_account, validate_cash_account, write_cash_account

MODULE_NAME = "paper_allocation_governance"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False

PENDING_STATUS = "PENDING_GOVERNANCE_REVIEW"
APPROVED_STATUS = "APPROVED_PAPER_ALLOCATION"
REJECTED_STATUS = "REJECTED_BY_INVESTOR"
DEFAULT_APPROVAL_LOG = Path("state/paper_allocation_approvals.jsonl")
DEFAULT_ALLOCATION_TRANSACTION_LOG = Path("state/paper_allocation_transactions.jsonl")


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL record must be an object: {source}")
        records.append(value)
    return records


def find_allocation_request(request_id: str, request_log: str | Path) -> dict[str, Any]:
    wanted = str(request_id).strip()
    if not wanted:
        raise ValueError("request_id is required")
    for record in read_jsonl(request_log):
        if str(record.get("request_id") or "") == wanted:
            return record
    raise ValueError(f"allocation request not found: {wanted}")


def latest_governance_decision(request_id: str, approval_log: str | Path = DEFAULT_APPROVAL_LOG) -> dict[str, Any]:
    matches = [
        record for record in read_jsonl(approval_log)
        if str(record.get("request_id") or "") == str(request_id)
    ]
    return matches[-1] if matches else {}


def _append_once(record: Mapping[str, Any], path: str | Path, identity_field: str) -> bool:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    identity = str(record.get(identity_field) or "")
    if not identity:
        raise ValueError(f"{identity_field} is required")
    for existing in read_jsonl(destination):
        if str(existing.get(identity_field) or "") == identity:
            return False
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(record), sort_keys=True) + "\n")
    return True


def build_approved_allocation(
    *,
    request: Mapping[str, Any],
    account: Mapping[str, Any],
    investor_id: str,
    investor_confirmed: bool,
    decided_at_utc: Optional[str] = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build updated paper balances, governance decision, and audit transaction."""
    validate_cash_account(account)
    if not investor_confirmed:
        raise ValueError("investor approval confirmation is required")
    if str(request.get("status") or "") != PENDING_STATUS:
        raise ValueError("only pending governance requests can be approved")
    if str(request.get("investor_id") or "") != str(investor_id):
        raise PermissionError("allocation request investor does not match approving investor")
    governance = request.get("governance")
    if not isinstance(governance, Mapping) or governance.get("paper_trade_mode") is not True:
        raise ValueError("allocation request is not paper-safe")
    if governance.get("live_trading_enabled") is not False or governance.get("broker_execution_enabled") is not False:
        raise ValueError("live trading and broker execution must remain disabled")

    amount = round(float(request.get("requested_cash", 0)), 2)
    available = round(float(account.get("available_cash", 0)), 2)
    if amount <= 0:
        raise ValueError("requested_cash must be greater than zero")
    if amount > available:
        raise ValueError("approved allocation exceeds available paper cash")

    allocations = request.get("allocations")
    if not isinstance(allocations, list) or not allocations:
        raise ValueError("allocation request has no strategy allocations")
    strategy_total = round(sum(float(item.get("amount", 0)) for item in allocations if isinstance(item, Mapping)), 2)
    if strategy_total != amount:
        raise ValueError("strategy allocations must equal requested_cash")

    decided = decided_at_utc or _now_utc()
    updated = dict(account)
    updated["available_cash"] = round(available - amount, 2)
    updated["allocated_cash"] = round(float(account.get("allocated_cash", 0)) + amount, 2)
    updated["generated_at_utc"] = decided
    strategy_balances = dict(account.get("strategy_allocations", {})) if isinstance(account.get("strategy_allocations"), Mapping) else {}
    for item in allocations:
        if not isinstance(item, Mapping):
            continue
        strategy_id = str(item.get("strategy_id") or "").strip()
        strategy_amount = round(float(item.get("amount", 0)), 2)
        if not strategy_id or strategy_amount <= 0:
            raise ValueError("strategy allocation entries require a strategy_id and positive amount")
        strategy_balances[strategy_id] = round(float(strategy_balances.get(strategy_id, 0)) + strategy_amount, 2)
    updated["strategy_allocations"] = strategy_balances
    validate_cash_account(updated)

    request_id = str(request.get("request_id") or "")
    decision_identity = json.dumps(
        {"request_id": request_id, "investor_id": investor_id, "decision": APPROVED_STATUS},
        sort_keys=True,
    )
    decision_id = "PAG-" + hashlib.sha256(decision_identity.encode("utf-8")).hexdigest()[:16].upper()
    decision = {
        "decision_id": decision_id,
        "request_id": request_id,
        "schema_version": SCHEMA_VERSION,
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "decided_at_utc": decided,
        "investor_id": investor_id,
        "status": APPROVED_STATUS,
        "requested_cash": amount,
        "allocations": [dict(item) for item in allocations if isinstance(item, Mapping)],
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "order_execution_allowed": False,
    }
    transaction = {
        "transaction_id": "PAT-" + hashlib.sha256((decision_id + request_id).encode("utf-8")).hexdigest()[:16].upper(),
        "request_id": request_id,
        "created_at_utc": decided,
        "transaction_type": "PAPER_STRATEGY_ALLOCATION",
        "amount": amount,
        "available_cash_before": available,
        "available_cash_after": updated["available_cash"],
        "allocated_cash_after": updated["allocated_cash"],
        "strategy_allocations": strategy_balances,
        "status": "APPLIED_TO_PAPER_ACCOUNT",
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
    }
    return updated, decision, transaction


def approve_allocation_request(
    *,
    request_id: str,
    request_log: str | Path,
    account_path: str | Path,
    approval_log: str | Path = DEFAULT_APPROVAL_LOG,
    transaction_log: str | Path = DEFAULT_ALLOCATION_TRANSACTION_LOG,
    investor_id: str = "default-investor",
    investor_confirmed: bool,
    decided_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Approve once and apply the request to the simulated paper cash account."""
    existing = latest_governance_decision(request_id, approval_log)
    if existing:
        return existing
    request = find_allocation_request(request_id, request_log)
    account = read_cash_account(account_path)
    if not account:
        raise RuntimeError("paper cash account has not been initialized")
    updated, decision, transaction = build_approved_allocation(
        request=request,
        account=account,
        investor_id=investor_id,
        investor_confirmed=investor_confirmed,
        decided_at_utc=decided_at_utc,
    )
    write_cash_account(updated, account_path)
    _append_once(transaction, transaction_log, "transaction_id")
    _append_once(decision, approval_log, "decision_id")
    return decision
