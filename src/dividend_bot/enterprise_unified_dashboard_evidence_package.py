"""Build a deterministic paper-only Enterprise dashboard evidence package."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from .enterprise_unified_dashboard_acceptance_renderer import (
    generate_acceptance_evidence_preview,
)
from .enterprise_unified_dashboard_cycle_acceptance import (
    REQUIRED_CYCLE_ARTIFACTS,
    run_and_accept_unified_dashboard_cycle,
)
from .enterprise_unified_dashboard_validation import DEFAULT_REQUIRED_STRATEGIES

MODULE_NAME = "enterprise_unified_dashboard_evidence_package"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True

PACKAGE_ARTIFACTS = (
    *REQUIRED_CYCLE_ARTIFACTS,
    "enterprise_unified_dashboard_cycle_acceptance.json",
    "enterprise_unified_dashboard_cycle_acceptance.md",
    "enterprise-unified-dashboard-acceptance.html",
)
PACKAGE_NAME = "enterprise-unified-dashboard-evidence-package.zip"
MANIFEST_NAME = "enterprise-unified-dashboard-evidence-manifest.json"

AcceptanceRunner = Callable[..., Mapping[str, Any]]
PreviewGenerator = Callable[..., Mapping[str, Any]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def build_evidence_manifest(
    *, results_dir: str | Path, artifact_names: Sequence[str] = PACKAGE_ARTIFACTS
) -> tuple[dict[str, Any], list[str]]:
    directory = Path(results_dir)
    files: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for raw_name in sorted(set(str(item) for item in artifact_names)):
        name = Path(raw_name).name
        if not raw_name or name != raw_name:
            errors.append(f"Package artifact name must be a flat local filename: {raw_name}")
            continue
        path = directory / name
        if not path.is_file():
            errors.append(f"Package artifact is missing: {path}")
            continue
        try:
            size = path.stat().st_size
            if size <= 0:
                errors.append(f"Package artifact is empty: {path}")
                continue
            files[name] = {
                "size_bytes": size,
                "sha256": _sha256_file(path),
            }
        except OSError as exc:
            errors.append(f"Package artifact is unreadable: {path}: {exc}")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "package_type": "ENTERPRISE_UNIFIED_DASHBOARD_ACCEPTANCE_EVIDENCE",
        "artifact_count": len(files),
        "artifacts": files,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
    }
    return manifest, errors


def _zip_info(name: str) -> ZipInfo:
    info = ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info


def write_deterministic_evidence_package(
    *,
    results_dir: str | Path,
    manifest: Mapping[str, Any],
    package_path: str | Path | None = None,
) -> dict[str, Any]:
    directory = Path(results_dir)
    output = Path(package_path) if package_path is not None else directory / PACKAGE_NAME
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_bytes = (
        json.dumps(dict(manifest), indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    files = manifest.get("artifacts")
    artifact_rows = files if isinstance(files, Mapping) else {}
    with NamedTemporaryFile(
        "wb", dir=output.parent, delete=False, suffix=".tmp"
    ) as handle:
        temporary = Path(handle.name)
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
            for name in sorted(artifact_rows):
                content = (directory / name).read_bytes()
                expected = str(artifact_rows[name].get("sha256") or "")
                if _sha256_bytes(content) != expected:
                    raise ValueError(f"Package artifact changed after manifest: {name}")
                archive.writestr(_zip_info(name), content)
            archive.writestr(_zip_info(MANIFEST_NAME), manifest_bytes)
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return {
        "path": str(output),
        "size_bytes": output.stat().st_size,
        "sha256": _sha256_file(output),
        "entry_count": len(artifact_rows) + 1,
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


def render_evidence_package_markdown(report: Mapping[str, Any]) -> str:
    package = report.get("package")
    package_data = package if isinstance(package, Mapping) else {}
    errors = report.get("errors") if isinstance(report.get("errors"), list) else []
    warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
    lines = [
        "# Enterprise Unified Dashboard Evidence Package",
        "",
        f"- Status: **{report.get('package_status', 'UNKNOWN')}**",
        f"- Acceptance: {report.get('acceptance_status', 'UNKNOWN')}",
        f"- UI verification: {report.get('verification_status', 'UNKNOWN')}",
        f"- Artifacts: {report.get('artifact_count', 0)}",
        f"- ZIP: {package_data.get('path', 'Not produced')}",
        f"- ZIP SHA-256: {package_data.get('sha256', 'Not produced')}",
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


def write_evidence_package_report(
    report: Mapping[str, Any], *, results_dir: str | Path
) -> dict[str, str]:
    directory = Path(results_dir)
    json_path = directory / "enterprise_unified_dashboard_evidence_package.json"
    markdown_path = directory / "enterprise_unified_dashboard_evidence_package.md"
    _atomic_write(json_path, json.dumps(dict(report), indent=2, sort_keys=True) + "\n")
    _atomic_write(markdown_path, render_evidence_package_markdown(report))
    return {"json": str(json_path), "markdown": str(markdown_path)}


def build_unified_dashboard_evidence_package(
    *,
    root_dir: str | Path = ".",
    results_dir: str | Path = "results",
    state_dir: str | Path = "state",
    required_strategy_ids: Sequence[str] = DEFAULT_REQUIRED_STRATEGIES,
    artifact_names: Sequence[str] = PACKAGE_ARTIFACTS,
    acceptance_runner: AcceptanceRunner = run_and_accept_unified_dashboard_cycle,
    preview_generator: PreviewGenerator = generate_acceptance_evidence_preview,
) -> dict[str, Any]:
    """Execute acceptance, verify its UI, then package only verified evidence."""
    root = Path(root_dir).resolve()
    results = Path(results_dir)
    results = results if results.is_absolute() else root / results
    state = Path(state_dir)
    state = state if state.is_absolute() else root / state
    results.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    warnings: list[str] = []
    acceptance: dict[str, Any] = {}
    preview: dict[str, Any] = {}
    package: dict[str, Any] = {}
    manifest: dict[str, Any] = {}

    try:
        acceptance = dict(
            acceptance_runner(
                root_dir=root,
                results_dir=results,
                state_dir=state,
                required_strategy_ids=required_strategy_ids,
            )
        )
    except Exception as exc:
        errors.append(f"Acceptance execution failed: {exc}")
    acceptance_status = str(acceptance.get("acceptance_status") or "FAILED")
    if acceptance_status != "PASSED":
        errors.append(f"Acceptance status is not PASSED: {acceptance_status}")

    if not errors:
        try:
            preview = dict(preview_generator(results_dir=results))
        except Exception as exc:
            errors.append(f"Acceptance evidence preview failed: {exc}")
    verification_status = str(preview.get("verification_status") or "NOT_RUN")
    if not errors and verification_status != "PASSED":
        errors.append(f"Acceptance evidence verification is not PASSED: {verification_status}")

    if not errors:
        manifest, manifest_errors = build_evidence_manifest(
            results_dir=results, artifact_names=artifact_names
        )
        errors.extend(manifest_errors)
    if not errors:
        try:
            package = write_deterministic_evidence_package(
                results_dir=results, manifest=manifest
            )
        except (OSError, ValueError) as exc:
            errors.append(f"Evidence package creation failed: {exc}")

    acceptance_warnings = acceptance.get("warnings")
    if isinstance(acceptance_warnings, list):
        warnings.extend(str(item) for item in acceptance_warnings if str(item).strip())
    acceptance_errors = acceptance.get("errors")
    if isinstance(acceptance_errors, list):
        errors.extend(str(item) for item in acceptance_errors if str(item).strip())

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "generated_at_utc": _utc_now(),
        "package_status": "PASSED" if not errors else "FAILED",
        "acceptance_status": acceptance_status,
        "verification_status": verification_status,
        "artifact_count": int(manifest.get("artifact_count", 0) or 0),
        "manifest": manifest,
        "package": package,
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
    }
    report["output_paths"] = write_evidence_package_report(report, results_dir=results)
    return report
