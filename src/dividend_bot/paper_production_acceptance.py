"""Paper-production acceptance validation for the Trade Dividend Bot."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "paper_production_acceptance"
MODULE_VERSION = "1.1.0"
SCHEMA_VERSION = "1.1"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
INVESTOR_CONTROLS_LIVE_MODE = True

REQUIRED_REPORTS = (
    "results/enterprise_dividend_dashboard.json",
    "results/enterprise_dividend_dashboard.md",
    "results/html/index.html",
    "results/html/executive_dashboard.html",
    "results/html/investor_dashboard.html",
    "results/html/strategy_health.html",
)
REQUIRED_OPERATIONAL_FILES = (
    "logs/dividend_bot.jsonl",
    "state/paper_state.json",
    "state/paper_cash_account.json",
    "state/paper_cash_transactions.jsonl",
    "state/paper_allocation_requests.jsonl",
    "results/enterprise_dividend_service_registry.json",
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class AcceptanceCheck:
    name: str
    status: str
    details: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "details": self.details}


def _file_check(root: Path, relative_path: str, *, non_empty: bool = True) -> AcceptanceCheck:
    path = root / relative_path
    if not path.is_file():
        return AcceptanceCheck(relative_path, "FAILED", "Required file is missing")
    if non_empty and path.stat().st_size == 0:
        return AcceptanceCheck(relative_path, "FAILED", "Required file is empty")
    return AcceptanceCheck(relative_path, "PASSED", "Required file exists")


def _json_check(root: Path, relative_path: str) -> AcceptanceCheck:
    path = root / relative_path
    if not path.is_file():
        return AcceptanceCheck(relative_path, "FAILED", "Required JSON file is missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return AcceptanceCheck(relative_path, "FAILED", f"Invalid JSON: {exc}")
    if not isinstance(payload, Mapping):
        return AcceptanceCheck(relative_path, "FAILED", "JSON root must be an object")
    return AcceptanceCheck(relative_path, "PASSED", "JSON parsed successfully")


def _jsonl_check(root: Path, relative_path: str, required_fields: Sequence[str]) -> AcceptanceCheck:
    path = root / relative_path
    if not path.is_file() or path.stat().st_size == 0:
        return AcceptanceCheck(relative_path, "FAILED", "Required JSONL file is missing or empty")
    try:
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        return AcceptanceCheck(relative_path, "FAILED", f"Invalid JSONL: {exc}")
    if not records or any(not isinstance(item, Mapping) for item in records):
        return AcceptanceCheck(relative_path, "FAILED", "JSONL must contain object records")
    missing = [field for field in required_fields if field not in records[-1]]
    if missing:
        return AcceptanceCheck(relative_path, "FAILED", "Latest record missing fields: " + ", ".join(missing))
    return AcceptanceCheck(relative_path, "PASSED", f"Validated {len(records)} append-only record(s)")


def _cash_account_check(root: Path) -> AcceptanceCheck:
    path = root / "state/paper_cash_account.json"
    try:
        account = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return AcceptanceCheck("paper_cash_account", "FAILED", f"Invalid paper cash account: {exc}")
    required = {"investor_id", "currency", "starting_cash", "available_cash", "reserved_cash", "allocated_cash"}
    missing = sorted(required - set(account)) if isinstance(account, Mapping) else sorted(required)
    if missing:
        return AcceptanceCheck("paper_cash_account", "FAILED", "Missing fields: " + ", ".join(missing))
    balances = [float(account[name]) for name in ("starting_cash", "available_cash", "reserved_cash", "allocated_cash")]
    if any(value < 0 for value in balances):
        return AcceptanceCheck("paper_cash_account", "FAILED", "Cash balances cannot be negative")
    if account.get("paper_trade_mode") is not True:
        return AcceptanceCheck("paper_cash_account", "FAILED", "paper_trade_mode must remain true")
    return AcceptanceCheck("paper_cash_account", "PASSED", "Canonical investor paper cash account validated")


def build_acceptance_report(
    root_dir: str | Path,
    *,
    required_reports: Sequence[str] = REQUIRED_REPORTS,
    required_operational_files: Sequence[str] = REQUIRED_OPERATIONAL_FILES,
    email_delivery_status: str = "NOT_TESTED",
    restart_recovery_status: str = "NOT_TESTED",
    allocation_ui_status: str = "NOT_TESTED",
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    root = Path(root_dir)
    checks: list[AcceptanceCheck] = []
    for relative_path in required_reports:
        checks.append(_file_check(root, relative_path))
    for relative_path in required_operational_files:
        checks.append(_file_check(root, relative_path))
    for relative_path in (*required_reports, *required_operational_files):
        if relative_path.endswith(".json"):
            checks.append(_json_check(root, relative_path))

    checks.append(_cash_account_check(root))
    checks.append(_jsonl_check(root, "state/paper_cash_transactions.jsonl", ("transaction_id", "amount", "balance_after", "paper_trade_mode")))
    checks.append(_jsonl_check(root, "state/paper_allocation_requests.jsonl", ("request_id", "status", "requested_cash", "allocations", "paper_trade_mode")))

    email_status = str(email_delivery_status).upper()
    recovery_status = str(restart_recovery_status).upper()
    ui_status = str(allocation_ui_status).upper()
    checks.append(AcceptanceCheck("email_delivery", "PASSED" if email_status in {"SENT", "DRY_RUN_PASSED"} else "FAILED", f"Email delivery status: {email_status}"))
    checks.append(AcceptanceCheck("restart_recovery", "PASSED" if recovery_status == "PASSED" else "FAILED", f"Restart recovery status: {recovery_status}"))
    checks.append(AcceptanceCheck("paper_cash_allocation_ui", "PASSED" if ui_status == "PASSED" else "FAILED", f"Cash funding and allocation UI status: {ui_status}"))

    failed = [item for item in checks if item.status == "FAILED"]
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at_utc or _now_utc(),
        "status": "ACCEPTED" if not failed else "REJECTED",
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "investor_controls_live_mode": True,
        "summary": {"total_checks": len(checks), "passed_checks": len(checks) - len(failed), "failed_checks": len(failed)},
        "checks": [item.to_dict() for item in checks],
        "governance": {
            "order_execution_allowed": False,
            "brokerage_communication_allowed": False,
            "capital_movement_allowed": False,
            "automatic_policy_change_allowed": False,
            "live_mode_requires_investor_authorization": True,
        },
    }


def write_acceptance_report(report: Mapping[str, Any], output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)
