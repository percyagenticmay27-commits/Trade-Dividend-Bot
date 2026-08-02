"""Final deployment validation and documentation freeze for the paper-only host."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping, Sequence

MODULE_NAME = "enterprise_deployment_release_gate"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True
VALIDATION_ONLY = True

REQUIRED_REPORTS = {
    "evidence_package": "enterprise_unified_dashboard_evidence_package.json",
    "hardening": "enterprise_production_hardening_audit.json",
    "recovery": "enterprise_backup_recovery_validation.json",
    "soak": "enterprise_stability_soak_validation.json",
}

DEFAULT_FREEZE_FILES = (
    "src/dividend_bot/enterprise_unified_dashboard_validation.py",
    "src/dividend_bot/enterprise_unified_dashboard_cycle.py",
    "src/dividend_bot/enterprise_unified_dashboard_cycle_acceptance.py",
    "src/dividend_bot/enterprise_unified_dashboard_acceptance_renderer.py",
    "src/dividend_bot/enterprise_unified_dashboard_evidence_package.py",
    "src/dividend_bot/enterprise_production_hardening_audit.py",
    "src/dividend_bot/enterprise_backup_recovery_validation.py",
    "src/dividend_bot/enterprise_stability_soak_validation.py",
    "src/dividend_bot/enterprise_deployment_release_gate.py",
    "docs/decisions/2026/08/2026-08-02_PHASE_6_5_ACCEPTANCE_EVIDENCE_PACKAGE.md",
    "docs/decisions/2026/08/2026-08-02_PHASE_7_1_PRODUCTION_HARDENING_BASELINE.md",
    "docs/decisions/2026/08/2026-08-02_PHASE_7_2_BACKUP_RECOVERY_VALIDATION.md",
    "docs/decisions/2026/08/2026-08-02_PHASE_7_3_STABILITY_SOAK_VALIDATION.md",
    "docs/decisions/2026/08/2026-08-02_PHASE_7_4_DEPLOYMENT_VALIDATION_DOCUMENTATION_FREEZE.md",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _read_mapping(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.is_file():
        return {}, f"Deployment gate report is missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, f"Deployment gate report is unreadable: {path}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"Deployment gate report root must be an object: {path}"
    return payload, None


def build_documentation_freeze_manifest(
    *,
    root_dir: str | Path,
    freeze_files: Sequence[str] = DEFAULT_FREEZE_FILES,
) -> tuple[dict[str, Any], list[str]]:
    root = Path(root_dir).resolve()
    files: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for requested in sorted(set(str(item) for item in freeze_files)):
        path = Path(requested)
        if path.is_absolute() or ".." in path.parts:
            errors.append(f"Documentation freeze path is unsafe: {requested}")
            continue
        source = root / path
        if not source.is_file():
            errors.append(f"Documentation freeze file is missing: {requested}")
            continue
        try:
            content = source.read_bytes()
        except OSError as exc:
            errors.append(f"Documentation freeze file is unreadable: {requested}: {exc}")
            continue
        files[path.as_posix()] = {
            "size_bytes": len(content),
            "sha256": _sha256_bytes(content),
        }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "freeze_status": "FROZEN" if not errors else "FAILED",
        "file_count": len(files),
        "files": files,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
    }
    return manifest, errors


def _safety_errors(name: str, payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for field, expected in (
        ("paper_trade_mode", True),
        ("live_trading_enabled", False),
        ("broker_execution_enabled", False),
        ("capital_movement_enabled", False),
        ("reporting_only", True),
    ):
        if payload.get(field) is not expected:
            errors.append(f"{name} safety field {field} must be {expected}")
    return errors


def validate_deployment_release(
    *,
    root_dir: str | Path = ".",
    results_dir: str | Path = "results",
    freeze_files: Sequence[str] = DEFAULT_FREEZE_FILES,
) -> dict[str, Any]:
    root = Path(root_dir).resolve()
    results = Path(results_dir)
    results = results if results.is_absolute() else root / results
    reports: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    warnings: list[str] = []
    for name, filename in REQUIRED_REPORTS.items():
        payload, error = _read_mapping(results / filename)
        reports[name] = payload
        if error:
            errors.append(error)
        elif payload:
            errors.extend(_safety_errors(name, payload))

    package = reports["evidence_package"]
    hardening = reports["hardening"]
    recovery = reports["recovery"]
    soak = reports["soak"]
    statuses = {
        "package_status": str(package.get("package_status") or "MISSING"),
        "acceptance_status": str(package.get("acceptance_status") or "MISSING"),
        "verification_status": str(package.get("verification_status") or "MISSING"),
        "hardening_status": str(hardening.get("hardening_status") or "MISSING"),
        "recovery_status": str(recovery.get("recovery_status") or "MISSING"),
        "restore_test_status": str(recovery.get("restore_test_status") or "MISSING"),
        "soak_status": str(soak.get("soak_status") or "MISSING"),
    }
    allowed = {
        "package_status": {"PASSED"},
        "acceptance_status": {"PASSED"},
        "verification_status": {"PASSED"},
        "hardening_status": {"READY", "READY_WITH_WARNINGS"},
        "recovery_status": {"PASSED"},
        "restore_test_status": {"PASSED"},
    }
    for name, accepted in allowed.items():
        if statuses[name] not in accepted:
            errors.append(f"Deployment gate status is not acceptable: {name}={statuses[name]}")
    if statuses["soak_status"] == "IN_PROGRESS":
        warnings.append("Long-duration stability soak is still in progress")
    elif statuses["soak_status"] != "PASSED":
        errors.append(
            f"Deployment gate status is not acceptable: soak_status={statuses['soak_status']}"
        )

    freeze_manifest, freeze_errors = build_documentation_freeze_manifest(
        root_dir=root, freeze_files=freeze_files
    )
    errors.extend(freeze_errors)
    errors = sorted(set(errors))
    warnings = sorted(set(warnings))
    release_status = (
        "BLOCKED"
        if errors
        else "IN_PROGRESS"
        if statuses["soak_status"] == "IN_PROGRESS"
        else "READY"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "generated_at_utc": _utc_now(),
        "release_status": release_status,
        **statuses,
        "documentation_freeze_status": freeze_manifest["freeze_status"],
        "documentation_frozen": freeze_manifest["freeze_status"] == "FROZEN",
        "freeze_file_count": freeze_manifest["file_count"],
        "freeze_manifest": freeze_manifest,
        "warnings": warnings,
        "errors": errors,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "validation_only": True,
    }


def _atomic_write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)
    return path


def render_deployment_release_markdown(report: Mapping[str, Any]) -> str:
    errors = report.get("errors") if isinstance(report.get("errors"), list) else []
    warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
    lines = [
        "# Enterprise Deployment Validation and Documentation Freeze",
        "",
        f"- Release status: **{report.get('release_status', 'UNKNOWN')}**",
        f"- Evidence package: {report.get('package_status', 'UNKNOWN')}",
        f"- Hardening: {report.get('hardening_status', 'UNKNOWN')}",
        f"- Recovery: {report.get('recovery_status', 'UNKNOWN')}",
        f"- Stability soak: {report.get('soak_status', 'UNKNOWN')}",
        f"- Documentation freeze: {report.get('documentation_freeze_status', 'UNKNOWN')}",
        f"- Frozen files: {report.get('freeze_file_count', 0)}",
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


def validate_and_write_deployment_release(
    *,
    root_dir: str | Path = ".",
    results_dir: str | Path = "results",
    freeze_files: Sequence[str] = DEFAULT_FREEZE_FILES,
) -> dict[str, Any]:
    root = Path(root_dir).resolve()
    results = Path(results_dir)
    results = results if results.is_absolute() else root / results
    report = validate_deployment_release(
        root_dir=root, results_dir=results, freeze_files=freeze_files
    )
    freeze_path = results / "enterprise_documentation_freeze_manifest.json"
    _atomic_write(
        freeze_path,
        json.dumps(report["freeze_manifest"], indent=2, sort_keys=True) + "\n",
    )
    report["freeze_manifest_path"] = str(freeze_path)
    report["freeze_manifest_sha256"] = _sha256_bytes(freeze_path.read_bytes())
    json_path = results / "enterprise_deployment_validation.json"
    markdown_path = results / "enterprise_deployment_validation.md"
    _atomic_write(json_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    _atomic_write(markdown_path, render_deployment_release_markdown(report))
    report["output_paths"] = {
        "json": str(json_path),
        "markdown": str(markdown_path),
        "freeze_manifest": str(freeze_path),
    }
    return report
