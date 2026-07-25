"""Paper-production acceptance validation for the Trade Dividend Bot."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "paper_production_acceptance"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

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


def build_acceptance_report(
    root_dir: str | Path,
    *,
    required_reports: Sequence[str] = REQUIRED_REPORTS,
    required_operational_files: Sequence[str] = REQUIRED_OPERATIONAL_FILES,
    email_delivery_status: str = "NOT_TESTED",
    restart_recovery_status: str = "NOT_TESTED",
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    root = Path(root_dir)
    checks: list[AcceptanceCheck] = []
    for relative_path in required_reports:
        checks.append(_file_check(root, relative_path))
    for relative_path in required_operational_files:
        checks.append(_file_check(root, relative_path))

    for relative_path in required_reports:
        if relative_path.endswith(".json"):
            checks.append(_json_check(root, relative_path))

    email_status = str(email_delivery_status).upper()
    recovery_status = str(restart_recovery_status).upper()
    checks.append(
        AcceptanceCheck(
            "email_delivery",
            "PASSED" if email_status in {"SENT", "DRY_RUN_PASSED"} else "FAILED",
            f"Email delivery status: {email_status}",
        )
    )
    checks.append(
        AcceptanceCheck(
            "restart_recovery",
            "PASSED" if recovery_status == "PASSED" else "FAILED",
            f"Restart recovery status: {recovery_status}",
        )
    )

    failed = [item for item in checks if item.status == "FAILED"]
    status = "ACCEPTED" if not failed else "REJECTED"
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at_utc or _now_utc(),
        "status": status,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "summary": {
            "total_checks": len(checks),
            "passed_checks": len(checks) - len(failed),
            "failed_checks": len(failed),
        },
        "checks": [item.to_dict() for item in checks],
        "governance": {
            "order_execution_allowed": False,
            "brokerage_communication_allowed": False,
            "capital_movement_allowed": False,
            "automatic_policy_change_allowed": False,
        },
    }


def write_acceptance_report(report: Mapping[str, Any], output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)
