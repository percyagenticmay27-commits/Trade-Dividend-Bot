"""Read-only production-hardening baseline for the paper-only Enterprise host."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping, Sequence

MODULE_NAME = "enterprise_production_hardening_audit"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True
READ_ONLY = True

REQUIRED_DEPLOYMENT_FILES = (
    "run_daily_paper_cycle.py",
    "send_daily_reports.py",
    "health_check_dividend_bot.sh",
    "backup_dividend_bot.sh",
    "rotate_dividend_logs.sh",
    "build_enterprise_unified_dashboard_evidence_package.py",
)
DEPLOYMENT_LOCAL_FILES = ("run_dividend_bot.sh",)
REQUIRED_ENVIRONMENT_NAMES = (
    "SENDGRID_API_KEY",
    "SENDGRID_FROM_EMAIL",
    "REPORT_RECIPIENT",
)
PACKAGE_REPORT_NAME = "enterprise_unified_dashboard_evidence_package.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_mapping(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.is_file():
        return {}, f"Required production evidence is missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, f"Production evidence is unreadable: {path}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"Production evidence root must be an object: {path}"
    return payload, None


def _file_inventory(root: Path, names: Sequence[str]) -> dict[str, bool]:
    return {name: (root / name).is_file() for name in names}


def audit_production_hardening(
    *,
    root_dir: str | Path = ".",
    results_dir: str | Path = "results",
    environment: Mapping[str, str] | None = None,
    required_deployment_files: Sequence[str] = REQUIRED_DEPLOYMENT_FILES,
    deployment_local_files: Sequence[str] = DEPLOYMENT_LOCAL_FILES,
    required_environment_names: Sequence[str] = REQUIRED_ENVIRONMENT_NAMES,
) -> dict[str, Any]:
    """Audit deployment readiness without executing workflows or exposing secrets."""
    root = Path(root_dir).resolve()
    results = Path(results_dir)
    results = results if results.is_absolute() else root / results
    env = os.environ if environment is None else environment
    errors: list[str] = []
    warnings: list[str] = []

    required_files = _file_inventory(root, required_deployment_files)
    for name, present in required_files.items():
        if not present:
            errors.append(f"Required deployment file is missing: {name}")

    local_files = _file_inventory(root, deployment_local_files)
    for name, present in local_files.items():
        if not present:
            warnings.append(
                f"Deployment-local file is not present in repository checkout: {name}"
            )

    environment_presence = {
        name: bool(str(env.get(name, "")).strip())
        for name in required_environment_names
    }
    for name, present in environment_presence.items():
        if not present:
            warnings.append(f"Deployment environment variable is not configured: {name}")

    package_report_path = results / PACKAGE_REPORT_NAME
    package_report, package_error = _read_mapping(package_report_path)
    if package_error:
        errors.append(package_error)
    package_status = str(package_report.get("package_status") or "MISSING")
    acceptance_status = str(package_report.get("acceptance_status") or "MISSING")
    verification_status = str(package_report.get("verification_status") or "MISSING")
    for label, status in (
        ("Evidence package", package_status),
        ("Cycle acceptance", acceptance_status),
        ("Operator UI verification", verification_status),
    ):
        if status != "PASSED":
            errors.append(f"{label} status must be PASSED: {status}")

    package_data = package_report.get("package")
    package = package_data if isinstance(package_data, Mapping) else {}
    package_path_value = str(package.get("path") or "").strip()
    package_path = Path(package_path_value) if package_path_value else None
    if package_path is not None and not package_path.is_absolute():
        direct = root / package_path
        package_path = direct if direct.is_file() else results / package_path.name
    expected_hash = str(package.get("sha256") or "").strip()
    actual_hash: str | None = None
    if package_path is None or not package_path.is_file():
        errors.append("Accepted evidence package ZIP is missing")
    else:
        try:
            actual_hash = _sha256(package_path)
        except OSError as exc:
            errors.append(f"Accepted evidence package ZIP is unreadable: {exc}")
        if actual_hash is not None and actual_hash != expected_hash:
            errors.append("Accepted evidence package ZIP SHA-256 does not match report")

    for field, expected in (
        ("paper_trade_mode", True),
        ("live_trading_enabled", False),
        ("broker_execution_enabled", False),
        ("capital_movement_enabled", False),
        ("reporting_only", True),
    ):
        if package_report.get(field) is not expected:
            errors.append(f"Evidence package safety field {field} must be {expected}")

    recovery = {
        "backup_script_present": required_files.get("backup_dividend_bot.sh", False),
        "health_check_present": required_files.get("health_check_dividend_bot.sh", False),
        "log_rotation_present": required_files.get("rotate_dividend_logs.sh", False),
        "restore_test_status": "NOT_YET_EXECUTED",
    }
    warnings.append("Recovery restore test has not yet been executed")
    errors = sorted(set(errors))
    warnings = sorted(set(warnings))
    status = "BLOCKED" if errors else "READY_WITH_WARNINGS" if warnings else "READY"
    return {
        "schema_version": SCHEMA_VERSION,
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "generated_at_utc": _utc_now(),
        "hardening_status": status,
        "required_deployment_files": required_files,
        "deployment_local_files": local_files,
        "environment_configuration": environment_presence,
        "environment_values_exposed": False,
        "package_status": package_status,
        "acceptance_status": acceptance_status,
        "verification_status": verification_status,
        "package_path": str(package_path) if package_path is not None else None,
        "package_expected_sha256": expected_hash or None,
        "package_actual_sha256": actual_hash,
        "recovery_readiness": recovery,
        "warnings": warnings,
        "errors": errors,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "read_only": True,
    }


def render_production_hardening_markdown(report: Mapping[str, Any]) -> str:
    errors = report.get("errors") if isinstance(report.get("errors"), list) else []
    warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
    lines = [
        "# Enterprise Production Hardening Baseline",
        "",
        f"- Status: **{report.get('hardening_status', 'UNKNOWN')}**",
        f"- Evidence package: {report.get('package_status', 'UNKNOWN')}",
        f"- Acceptance: {report.get('acceptance_status', 'UNKNOWN')}",
        f"- UI verification: {report.get('verification_status', 'UNKNOWN')}",
        f"- Package SHA-256 verified: {report.get('package_expected_sha256') == report.get('package_actual_sha256')}",
        f"- Environment values exposed: {report.get('environment_values_exposed')}",
        f"- Paper trade mode: {report.get('paper_trade_mode')}",
        f"- Live trading enabled: {report.get('live_trading_enabled')}",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {item}" for item in errors)
    if not errors:
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {item}" for item in warnings)
    if not warnings:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)
    return path


def audit_and_write_production_hardening(
    *, root_dir: str | Path = ".", results_dir: str | Path = "results",
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    root = Path(root_dir).resolve()
    results = Path(results_dir)
    results = results if results.is_absolute() else root / results
    report = audit_production_hardening(
        root_dir=root, results_dir=results, environment=environment
    )
    json_path = results / "enterprise_production_hardening_audit.json"
    markdown_path = results / "enterprise_production_hardening_audit.md"
    _atomic_write(json_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    _atomic_write(markdown_path, render_production_hardening_markdown(report))
    report["output_paths"] = {
        "json": str(json_path),
        "markdown": str(markdown_path),
    }
    return report
