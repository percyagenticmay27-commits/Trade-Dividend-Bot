"""End-to-end operational validation for the paper-only Trade Dividend Bot.

This module validates already-produced artifacts. It does not run strategy logic,
contact a broker, move capital, schedule jobs, or send email.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "end_to_end_paper_trading_validation"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
ADVISORY_ONLY = True

DEFAULT_REQUIRED_ARTIFACTS = (
    "results/enterprise_dividend_daily_cycle.json",
    "results/paper_production_acceptance.json",
    "results/cloud_readiness.json",
    "results/enterprise_dividend_dashboard.json",
    "results/enterprise_dividend_strategy_health.json",
    "results/enterprise_dividend_service_registry.json",
    "logs/dividend_bot.jsonl",
    "state/paper_state.json",
    "state/paper_cash_account.json",
    "state/paper_cash_transactions.jsonl",
    "state/paper_allocation_requests.jsonl",
)


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    status: str
    details: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "details": self.details}


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("JSON root must be an object")
    return payload


def _artifact_check(root: Path, relative_path: str) -> ValidationCheck:
    path = root / relative_path
    if not path.is_file():
        return ValidationCheck(relative_path, "FAILED", "Required artifact is missing")
    if path.stat().st_size == 0:
        return ValidationCheck(relative_path, "FAILED", "Required artifact is empty")
    if path.suffix == ".json":
        try:
            _load_json(path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return ValidationCheck(relative_path, "FAILED", f"Invalid JSON: {exc}")
    if path.suffix == ".jsonl":
        try:
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, json.JSONDecodeError) as exc:
            return ValidationCheck(relative_path, "FAILED", f"Invalid JSONL: {exc}")
        if not rows or any(not isinstance(row, Mapping) for row in rows):
            return ValidationCheck(relative_path, "FAILED", "JSONL must contain object records")
    return ValidationCheck(relative_path, "PASSED", "Artifact exists and is readable")


def _safety_check(name: str, payload: Mapping[str, Any]) -> ValidationCheck:
    safe = (
        payload.get("paper_trade_mode") is True
        and payload.get("live_trading_enabled") is False
        and payload.get("broker_execution_enabled") is False
    )
    return ValidationCheck(
        f"{name}_paper_safety",
        "PASSED" if safe else "FAILED",
        "Paper-only safety contract validated" if safe else "Unsafe or incomplete execution settings",
    )


def build_end_to_end_paper_trading_validation(
    root_dir: str | Path,
    *,
    required_artifacts: Sequence[str] = DEFAULT_REQUIRED_ARTIFACTS,
    scheduler_status: str = "NOT_TESTED",
    email_delivery_status: str = "NOT_TESTED",
    restart_recovery_status: str = "NOT_TESTED",
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    root = Path(root_dir)
    checks = [_artifact_check(root, item) for item in required_artifacts]
    blockers: list[str] = []
    warnings: list[str] = []

    payloads: dict[str, Mapping[str, Any]] = {}
    sources = {
        "daily_cycle": "results/enterprise_dividend_daily_cycle.json",
        "acceptance": "results/paper_production_acceptance.json",
        "cloud_readiness": "results/cloud_readiness.json",
    }
    for name, relative_path in sources.items():
        path = root / relative_path
        try:
            payloads[name] = _load_json(path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            blockers.append(f"{name}: {exc}")
            continue
        checks.append(_safety_check(name, payloads[name]))

    cycle = payloads.get("daily_cycle", {})
    cycle_status = str(cycle.get("cycle_status", "UNKNOWN")).upper()
    cycle_ok = cycle_status in {"COMPLETED", "COMPLETED_WITH_WARNINGS"}
    checks.append(ValidationCheck("daily_cycle_status", "PASSED" if cycle_ok else "FAILED", f"Daily cycle status: {cycle_status}"))
    if cycle_status == "COMPLETED_WITH_WARNINGS":
        warnings.append("Daily cycle completed with warnings")

    acceptance = payloads.get("acceptance", {})
    acceptance_status = str(acceptance.get("status", "UNKNOWN")).upper()
    checks.append(ValidationCheck("paper_production_acceptance", "PASSED" if acceptance_status == "ACCEPTED" else "FAILED", f"Acceptance status: {acceptance_status}"))

    cloud = payloads.get("cloud_readiness", {})
    cloud_status = str(cloud.get("status", "UNKNOWN")).upper()
    checks.append(ValidationCheck("cloud_readiness_status", "PASSED" if cloud_status == "HEALTHY" else "FAILED", f"Cloud readiness status: {cloud_status}"))

    operational = {
        "scheduler": str(scheduler_status).upper(),
        "email_delivery": str(email_delivery_status).upper(),
        "restart_recovery": str(restart_recovery_status).upper(),
    }
    accepted_values = {
        "scheduler": {"PASSED"},
        "email_delivery": {"SENT", "DRY_RUN_PASSED"},
        "restart_recovery": {"PASSED"},
    }
    for name, status in operational.items():
        passed = status in accepted_values[name]
        checks.append(ValidationCheck(name, "PASSED" if passed else "FAILED", f"Operational status: {status}"))

    failed = [check for check in checks if check.status == "FAILED"]
    blockers.extend(check.name for check in failed)
    final_status = "VALIDATED" if not blockers else "BLOCKED"

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at_utc or _now_utc(),
        "status": final_status,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "advisory_only": True,
        "summary": {
            "total_checks": len(checks),
            "passed_checks": len(checks) - len(failed),
            "failed_checks": len(failed),
            "warning_count": len(warnings),
        },
        "operational_status": operational,
        "checks": [check.to_dict() for check in checks],
        "warnings": warnings,
        "blockers": sorted(set(blockers)),
        "governance": {
            "strategy_execution_allowed": False,
            "order_execution_allowed": False,
            "brokerage_communication_allowed": False,
            "capital_movement_allowed": False,
            "automatic_policy_change_allowed": False,
            "investor_approval_required": True,
        },
    }


def render_end_to_end_paper_trading_validation_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# End-to-End Paper Trading Validation",
        "",
        f"- Status: **{report.get('status', 'UNKNOWN')}**",
        f"- Generated: `{report.get('generated_at_utc', '')}`",
        f"- Paper trade mode: `{report.get('paper_trade_mode')}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Details |",
        "|---|---|---|",
    ]
    for check in report.get("checks", []):
        lines.append(f"| {check.get('name')} | {check.get('status')} | {check.get('details')} |")
    lines.extend(["", "## Blockers", ""])
    blockers = list(report.get("blockers") or [])
    lines.extend([f"- {item}" for item in blockers] if blockers else ["- None"])
    lines.extend([
        "",
        "## Governance",
        "",
        "This validation is read-only and paper-only. It does not execute strategy logic, contact a broker, move capital, schedule jobs, or send email.",
        "",
    ])
    return "\n".join(lines)


def write_end_to_end_paper_trading_validation(report: Mapping[str, Any], output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "end_to_end_paper_trading_validation.json"
    markdown_path = output / "end_to_end_paper_trading_validation.md"
    json_path.write_text(json.dumps(dict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_end_to_end_paper_trading_validation_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def build_and_write_end_to_end_paper_trading_validation(output_dir: str | Path, root_dir: str | Path, **kwargs: Any) -> dict[str, Any]:
    report = build_end_to_end_paper_trading_validation(root_dir, **kwargs)
    report["output_files"] = write_end_to_end_paper_trading_validation(report, output_dir)
    return report
