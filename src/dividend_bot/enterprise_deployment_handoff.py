"""Environment-aware Phase 7.5 handoff for paper-only production validation."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
from tempfile import NamedTemporaryFile
from typing import Any, Mapping

MODULE_NAME = "enterprise_deployment_handoff"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True
VALIDATION_ONLY = True

REQUIRED_REPORTS = {
    "evidence_package": ("enterprise_unified_dashboard_evidence_package.json", "package_status", {"PASSED"}),
    "hardening": ("enterprise_production_hardening_audit.json", "hardening_status", {"READY", "READY_WITH_WARNINGS"}),
    "recovery": ("enterprise_backup_recovery_validation.json", "recovery_status", {"PASSED"}),
    "soak": ("enterprise_stability_soak_validation.json", "soak_status", {"PASSED"}),
    "release": ("enterprise_deployment_validation.json", "release_status", {"READY"}),
}
REQUIRED_DEPLOYMENT_VARIABLES = (
    "REPORT_RECIPIENT",
    "SENDGRID_API_KEY",
    "SENDGRID_FROM_EMAIL",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def detect_environment(
    *, env: Mapping[str, str] | None = None, system_name: str | None = None
) -> str:
    values = os.environ if env is None else env
    explicit = str(values.get("TRADE_BOT_DEPLOYMENT_ENV", "")).strip().upper()
    if explicit in {"DIGITALOCEAN", "PRODUCTION"}:
        return "DIGITALOCEAN"
    if explicit in {"LOCAL", "DEVELOPMENT", "TEST"}:
        return "LOCAL"
    host_markers = (
        values.get("DIGITALOCEAN_APP_ID"),
        values.get("DROPLET_ID"),
        values.get("DIGITALOCEAN_DEPLOYMENT"),
    )
    if any(str(value or "").strip() for value in host_markers):
        return "DIGITALOCEAN"
    return "LOCAL" if (system_name or platform.system()).upper() == "WINDOWS" else "UNKNOWN"


def build_deployment_handoff(
    *,
    root_dir: str | Path = ".",
    results_dir: str | Path = "results",
    env: Mapping[str, str] | None = None,
    system_name: str | None = None,
) -> dict[str, Any]:
    root = Path(root_dir).resolve()
    results = Path(results_dir)
    results = results if results.is_absolute() else root / results
    values = os.environ if env is None else env
    environment = detect_environment(env=values, system_name=system_name)
    reports: dict[str, dict[str, Any]] = {}
    blockers: list[str] = []
    for name, (filename, field, accepted) in REQUIRED_REPORTS.items():
        payload = _read_mapping(results / filename)
        status = str(payload.get(field) or "MISSING").upper()
        reports[name] = {"filename": filename, "status": status}
        if status not in accepted:
            blockers.append(f"{name} is not ready: {field}={status}")

    missing_variables = [
        name for name in REQUIRED_DEPLOYMENT_VARIABLES
        if not str(values.get(name, "")).strip()
    ]
    if environment == "DIGITALOCEAN" and missing_variables:
        blockers.extend(
            f"DigitalOcean deployment variable is missing: {name}"
            for name in missing_variables
        )

    local_ready = all(
        reports[name]["status"] in REQUIRED_REPORTS[name][2]
        for name in ("evidence_package", "hardening", "recovery")
    )
    production_ready = not blockers and environment == "DIGITALOCEAN"
    next_actions: list[str] = []
    if not local_ready:
        next_actions.append("Complete local evidence package, hardening, and isolated recovery validation")
    elif environment != "DIGITALOCEAN":
        next_actions.append("Deploy the validated feature branch to DigitalOcean")
    if environment == "DIGITALOCEAN" and reports["soak"]["status"] != "PASSED":
        next_actions.append("Complete the authoritative seven-day DigitalOcean stability soak")
    if environment == "DIGITALOCEAN" and reports["release"]["status"] != "READY":
        next_actions.append("Run the final deployment release gate after the soak passes")
    if production_ready:
        next_actions.append("Preserve the frozen evidence package and release validation")

    return {
        "schema_version": SCHEMA_VERSION,
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "generated_at_utc": _utc_now(),
        "environment": environment,
        "handoff_status": (\n            "READY"\n            if production_ready\n            else "BLOCKED"\n            if environment == "DIGITALOCEAN" and blockers\n            else "LOCAL_READY"\n            if local_ready\n            else "BLOCKED"\n        ),
        "local_validation_ready": local_ready,
        "production_validation_ready": production_ready,
        "reports": reports,
        "deployment_variables": {
            "required": list(REQUIRED_DEPLOYMENT_VARIABLES),
            "missing": missing_variables,
            "values_exposed": False,
        },
        "next_actions": next_actions,
        "blockers": sorted(set(blockers)),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "validation_only": True,
    }


def _atomic_write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)
    return path


def build_and_write_deployment_handoff(
    *, root_dir: str | Path = ".", results_dir: str | Path = "results"
) -> dict[str, Any]:
    report = build_deployment_handoff(root_dir=root_dir, results_dir=results_dir)
    root = Path(root_dir).resolve()
    results = Path(results_dir)
    results = results if results.is_absolute() else root / results
    output = results / "enterprise_deployment_handoff.json"
    _atomic_write(output, json.dumps(report, indent=2, sort_keys=True) + "\n")
    report["output_path"] = str(output)
    return report
