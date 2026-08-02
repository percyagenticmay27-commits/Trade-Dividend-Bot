"""Acceptance gate for a real paper-only unified Enterprise dashboard cycle."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Mapping, Sequence

from .enterprise_unified_dashboard_cycle import run_unified_dashboard_cycle
from .enterprise_unified_dashboard_validation import DEFAULT_REQUIRED_STRATEGIES

MODULE_NAME = "enterprise_unified_dashboard_cycle_acceptance"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True

REQUIRED_CYCLE_ARTIFACTS = (
    "enterprise_dividend_service_registry.json",
    "dividend_strategy_decision_journal.json",
    "swing_strategy_decision_journal.json",
    "enterprise_strategy_kpis.json",
    "ai_cio_executive_dashboard.json",
    "enterprise_investor_dashboard.json",
    "enterprise_unified_dashboard_validation.json",
    "enterprise_unified_dashboard_validation.md",
    "enterprise_unified_dashboard_cycle.json",
    "enterprise_unified_dashboard_cycle.md",
)

CycleRunner = Callable[..., Mapping[str, Any]]


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


def snapshot_directory(directory: str | Path) -> dict[str, str]:
    """Return a deterministic content manifest without modifying the directory."""
    root = Path(directory)
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def validate_cycle_artifacts(
    *,
    results_dir: str | Path,
    required_artifacts: Sequence[str] = REQUIRED_CYCLE_ARTIFACTS,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Validate that required real-cycle artifacts exist, are nonempty and readable."""
    directory = Path(results_dir)
    manifest: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for name in required_artifacts:
        path = directory / name
        entry: dict[str, Any] = {
            "path": str(path),
            "exists": path.is_file(),
            "size_bytes": 0,
            "sha256": None,
        }
        if not path.is_file():
            errors.append(f"Required cycle artifact is missing: {path}")
            manifest[name] = entry
            continue
        try:
            entry["size_bytes"] = path.stat().st_size
            entry["sha256"] = _sha256(path)
            if entry["size_bytes"] <= 0:
                errors.append(f"Required cycle artifact is empty: {path}")
            elif path.suffix.lower() == ".json":
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    errors.append(f"Cycle artifact JSON root must be an object: {path}")
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"Required cycle artifact is unreadable: {path}: {exc}")
        manifest[name] = entry
    return manifest, errors


def _atomic_write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)
    return path


def render_cycle_acceptance_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Enterprise Unified Dashboard Cycle Acceptance",
        "",
        f"- Status: **{report.get('acceptance_status', 'UNKNOWN')}**",
        f"- Cycle status: {report.get('cycle_status', 'UNKNOWN')}",
        f"- Required artifacts: {report.get('required_artifact_count', 0)}",
        f"- Protected state unchanged: {report.get('protected_state_unchanged')}",
        f"- Paper trade mode: {report.get('paper_trade_mode')}",
        f"- Live trading enabled: {report.get('live_trading_enabled')}",
        f"- Broker execution enabled: {report.get('broker_execution_enabled')}",
        f"- Capital movement enabled: {report.get('capital_movement_enabled')}",
        "",
        "## Errors",
        "",
    ]
    errors = report.get("errors") if isinstance(report.get("errors"), list) else []
    lines.extend(f"- {item}" for item in errors)
    if not errors:
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
    lines.extend(f"- {item}" for item in warnings)
    if not warnings:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def write_cycle_acceptance(
    report: Mapping[str, Any], *, results_dir: str | Path
) -> dict[str, str]:
    directory = Path(results_dir)
    json_path = directory / "enterprise_unified_dashboard_cycle_acceptance.json"
    markdown_path = directory / "enterprise_unified_dashboard_cycle_acceptance.md"
    _atomic_write(json_path, json.dumps(dict(report), indent=2, sort_keys=True) + "\n")
    _atomic_write(markdown_path, render_cycle_acceptance_markdown(report))
    return {"json": str(json_path), "markdown": str(markdown_path)}


def run_and_accept_unified_dashboard_cycle(
    *,
    root_dir: str | Path = ".",
    results_dir: str | Path = "results",
    state_dir: str | Path = "state",
    required_strategy_ids: Sequence[str] = DEFAULT_REQUIRED_STRATEGIES,
    required_artifacts: Sequence[str] = REQUIRED_CYCLE_ARTIFACTS,
    cycle_runner: CycleRunner = run_unified_dashboard_cycle,
) -> dict[str, Any]:
    """Run the real reporting cycle and accept it only if outputs and state are safe."""
    root = Path(root_dir).resolve()
    results = Path(results_dir)
    results = results if results.is_absolute() else root / results
    state = Path(state_dir)
    state = state if state.is_absolute() else root / state
    results.mkdir(parents=True, exist_ok=True)

    before_state = snapshot_directory(state)
    errors: list[str] = []
    warnings: list[str] = []
    cycle: dict[str, Any] = {}
    try:
        cycle = dict(
            cycle_runner(
                root_dir=root,
                results_dir=results,
                state_dir=state,
                required_strategy_ids=required_strategy_ids,
            )
        )
    except Exception as exc:
        errors.append(f"Unified dashboard cycle execution failed: {exc}")

    after_state = snapshot_directory(state)
    state_unchanged = before_state == after_state
    if not state_unchanged:
        errors.append("Protected state directory changed during reporting cycle")

    artifact_manifest, artifact_errors = validate_cycle_artifacts(
        results_dir=results,
        required_artifacts=required_artifacts,
    )
    errors.extend(artifact_errors)

    cycle_status = str(cycle.get("cycle_status") or "FAILED")
    if cycle_status != "PASSED":
        errors.append(f"Unified dashboard cycle did not pass: {cycle_status}")
    expected_safety = {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
    }
    for name, expected in expected_safety.items():
        if cycle.get(name) is not expected:
            errors.append(f"Cycle safety field {name} must be {expected}")

    cycle_warnings = cycle.get("warnings")
    if isinstance(cycle_warnings, list):
        warnings.extend(str(item) for item in cycle_warnings if str(item).strip())
    cycle_errors = cycle.get("errors")
    if isinstance(cycle_errors, list):
        errors.extend(str(item) for item in cycle_errors if str(item).strip())

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "generated_at_utc": _utc_now(),
        "acceptance_status": "PASSED" if not errors else "FAILED",
        "cycle_status": cycle_status,
        "required_strategy_ids": sorted(
            {str(item).strip() for item in required_strategy_ids if str(item).strip()}
        ),
        "required_artifact_count": len(required_artifacts),
        "artifact_manifest": artifact_manifest,
        "protected_state_unchanged": state_unchanged,
        "protected_state_file_count": len(after_state),
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
        **expected_safety,
    }
    report["output_paths"] = write_cycle_acceptance(report, results_dir=results)
    return report
