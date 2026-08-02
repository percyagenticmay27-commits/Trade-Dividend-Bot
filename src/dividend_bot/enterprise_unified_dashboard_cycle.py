"""Paper-only orchestration for one unified Enterprise dashboard cycle."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Mapping, Sequence

from .enterprise_unified_dashboard_validation import (
    DEFAULT_REQUIRED_STRATEGIES,
    validate_and_write_unified_dashboard,
)
from .strategy_decision_journal_generator import (
    generate_all_strategy_decision_journals,
)

MODULE_NAME = "enterprise_unified_dashboard_cycle"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True

JournalGenerator = Callable[..., Mapping[str, Any]]
DashboardRefresher = Callable[..., Mapping[str, Any]]
DashboardValidator = Callable[..., Mapping[str, Any]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _step(status: str = "NOT_RUN") -> dict[str, Any]:
    return {"status": status, "paths": {}, "warnings": [], "errors": []}


def _messages(payload: Mapping[str, Any], name: str) -> list[str]:
    values = payload.get(name)
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value).strip()]


def _paths(payload: Mapping[str, Any]) -> dict[str, str]:
    values = payload.get("paths") or payload.get("output_paths")
    if not isinstance(values, Mapping):
        return {}
    return {str(key): str(value) for key, value in values.items()}


def _atomic_write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)
    return path


def render_unified_dashboard_cycle_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Enterprise Unified Dashboard Cycle",
        "",
        f"- Status: **{summary.get('cycle_status', 'UNKNOWN')}**",
        f"- Paper trade mode: {summary.get('paper_trade_mode')}",
        f"- Live trading enabled: {summary.get('live_trading_enabled')}",
        f"- Broker execution enabled: {summary.get('broker_execution_enabled')}",
        f"- Capital movement enabled: {summary.get('capital_movement_enabled')}",
        "",
        "## Steps",
        "",
    ]
    steps = summary.get("steps")
    if isinstance(steps, Mapping):
        for name, step in steps.items():
            status = step.get("status", "UNKNOWN") if isinstance(step, Mapping) else "UNKNOWN"
            lines.append(f"- {name}: {status}")
    lines.extend(["", "## Errors", ""])
    errors = summary.get("errors") if isinstance(summary.get("errors"), list) else []
    lines.extend(f"- {item}" for item in errors)
    if not errors:
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    warnings = summary.get("warnings") if isinstance(summary.get("warnings"), list) else []
    lines.extend(f"- {item}" for item in warnings)
    if not warnings:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def write_unified_dashboard_cycle_summary(
    summary: Mapping[str, Any], *, results_dir: str | Path
) -> dict[str, str]:
    directory = Path(results_dir)
    json_path = directory / "enterprise_unified_dashboard_cycle.json"
    markdown_path = directory / "enterprise_unified_dashboard_cycle.md"
    _atomic_write(json_path, json.dumps(dict(summary), indent=2, sort_keys=True) + "\n")
    _atomic_write(markdown_path, render_unified_dashboard_cycle_markdown(summary))
    return {"json": str(json_path), "markdown": str(markdown_path)}


def run_unified_dashboard_cycle(
    *,
    root_dir: str | Path = ".",
    results_dir: str | Path = "results",
    state_dir: str | Path = "state",
    required_strategy_ids: Sequence[str] = DEFAULT_REQUIRED_STRATEGIES,
    journal_generator: JournalGenerator = generate_all_strategy_decision_journals,
    dashboard_refresher: DashboardRefresher | None = None,
    dashboard_validator: DashboardValidator = validate_and_write_unified_dashboard,
) -> dict[str, Any]:
    """Generate, refresh, and validate one reporting-only Enterprise cycle."""
    if dashboard_refresher is None:
        from refresh_enterprise_dashboards import refresh_enterprise_dashboards

        dashboard_refresher = refresh_enterprise_dashboards

    root = Path(root_dir).resolve()
    results = Path(results_dir)
    results = results if results.is_absolute() else root / results
    state = Path(state_dir)
    state = state if state.is_absolute() else root / state
    results.mkdir(parents=True, exist_ok=True)

    steps = {
        "decision_journals": _step(),
        "dashboard_refresh": _step(),
        "unified_validation": _step(),
    }
    warnings: list[str] = []
    errors: list[str] = []

    try:
        generated = dict(journal_generator(results_dir=results))
        step_errors = _messages(generated, "errors")
        steps["decision_journals"] = {
            "status": "PASSED" if not step_errors else "FAILED",
            "paths": _paths(generated),
            "warnings": _messages(generated, "warnings"),
            "errors": step_errors,
            "decision_count": int(generated.get("decision_count", 0) or 0),
        }
    except Exception as exc:
        steps["decision_journals"]["status"] = "FAILED"
        steps["decision_journals"]["errors"] = [f"Decision journal generation failed: {exc}"]

    if steps["decision_journals"]["status"] == "PASSED":
        try:
            refreshed = dict(
                dashboard_refresher(
                    root_dir=root,
                    results_dir=results,
                    state_dir=state,
                )
            )
            step_errors = _messages(refreshed, "errors")
            steps["dashboard_refresh"] = {
                "status": "PASSED" if not step_errors else "FAILED",
                "paths": _paths(refreshed),
                "warnings": _messages(refreshed, "warnings"),
                "errors": step_errors,
                "registered_strategy_count": int(
                    refreshed.get("registered_strategy_count", 0) or 0
                ),
            }
        except Exception as exc:
            steps["dashboard_refresh"]["status"] = "FAILED"
            steps["dashboard_refresh"]["errors"] = [f"Dashboard refresh failed: {exc}"]

    if steps["dashboard_refresh"]["status"] == "PASSED":
        try:
            validated = dict(
                dashboard_validator(
                    results_dir=results,
                    required_strategy_ids=required_strategy_ids,
                )
            )
            validation_errors = _messages(validated, "errors")
            validation_status = str(validated.get("validation_status") or "FAILED")
            steps["unified_validation"] = {
                "status": "PASSED" if validation_status == "PASSED" and not validation_errors else "FAILED",
                "paths": _paths(validated),
                "warnings": _messages(validated, "warnings"),
                "errors": validation_errors,
                "validation_status": validation_status,
            }
        except Exception as exc:
            steps["unified_validation"]["status"] = "FAILED"
            steps["unified_validation"]["errors"] = [f"Unified validation failed: {exc}"]

    for step in steps.values():
        warnings.extend(step["warnings"])
        errors.extend(step["errors"])
    status = "PASSED" if all(step["status"] == "PASSED" for step in steps.values()) else "FAILED"
    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "generated_at_utc": _utc_now(),
        "cycle_status": status,
        "steps": steps,
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
    }
    summary["output_paths"] = write_unified_dashboard_cycle_summary(
        summary, results_dir=results
    )
    return summary
