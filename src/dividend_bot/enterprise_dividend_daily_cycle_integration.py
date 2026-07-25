"""Enterprise Dividend Daily Cycle Integration.

Creates a deterministic paper-only cycle plan and aggregates read-only step
results in dependency order. It never places orders, contacts a broker, or
moves capital.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "enterprise_dividend_daily_cycle_integration"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ADVISORY_ONLY = True
ORCHESTRATION_ONLY = True

STEP_ORDER = (
    "LIFECYCLE", "INCOME", "FORECAST", "ANALYTICS", "REPORTING",
    "DASHBOARD", "ALERTS", "REVIEWS", "LEARNING", "CIO_ADVISORY",
    "REPLACEMENT", "STRATEGY_HEALTH",
)

DEFAULT_OUTPUT_FILES = {
    "json": "enterprise_dividend_daily_cycle.json",
    "markdown": "enterprise_dividend_daily_cycle.md",
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    text = str(value or default).strip()
    return text.upper() if text else default


def _cycle_id(reporting_period: str, generated_at_utc: str) -> str:
    raw = f"{reporting_period}|{generated_at_utc}|{MODULE_VERSION}"
    return f"DIV-CYCLE-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16].upper()}"


def _normalize_step(step: Mapping[str, Any]) -> dict[str, Any]:
    name = _upper(step.get("step_name") or step.get("name"), "")
    if name not in STEP_ORDER:
        raise ValueError(f"Unsupported daily-cycle step: {name}")
    dependencies = [_upper(item, "") for item in step.get("dependencies", []) if str(item).strip()]
    invalid = [item for item in dependencies if item not in STEP_ORDER]
    if invalid:
        raise ValueError(f"Unsupported dependencies for {name}: {invalid}")
    return {
        "step_name": name,
        "sequence": STEP_ORDER.index(name) + 1,
        "service_name": str(step.get("service_name") or name.lower()),
        "input_artifacts": sorted({str(item) for item in step.get("input_artifacts", []) if str(item).strip()}),
        "output_artifacts": sorted({str(item) for item in step.get("output_artifacts", []) if str(item).strip()}),
        "dependencies": sorted(set(dependencies), key=STEP_ORDER.index),
        "required": bool(step.get("required", True)),
        "enabled": bool(step.get("enabled", True)),
        "status": _upper(step.get("status"), "PENDING"),
        "warnings": list(step.get("warnings") or []),
        "error": step.get("error"),
    }


def default_daily_cycle_steps() -> list[dict[str, Any]]:
    outputs = {
        "LIFECYCLE": ["dividend_lifecycle.json"],
        "INCOME": ["dividend_income.json"],
        "FORECAST": ["dividend_forecast.json"],
        "ANALYTICS": ["dividend_analytics.json"],
        "REPORTING": ["enterprise_dividend_report.json"],
        "DASHBOARD": ["enterprise_dividend_dashboard.json", "enterprise_investor_dashboard.json"],
        "ALERTS": ["enterprise_dividend_alerts.json"],
        "REVIEWS": ["enterprise_dividend_reviews.json"],
        "LEARNING": ["enterprise_dividend_learning.json"],
        "CIO_ADVISORY": ["enterprise_dividend_cio_advisory.json"],
        "REPLACEMENT": ["enterprise_dividend_replacement.json"],
        "STRATEGY_HEALTH": ["enterprise_dividend_strategy_health.json"],
    }
    steps: list[dict[str, Any]] = []
    previous: Optional[str] = None
    for name in STEP_ORDER:
        steps.append(_normalize_step({
            "step_name": name,
            "service_name": f"enterprise_dividend_{name.lower()}_service",
            "output_artifacts": outputs[name],
            "dependencies": [previous] if previous else [],
        }))
        previous = name
    return steps


def build_enterprise_dividend_daily_cycle(
    *,
    steps: Optional[Sequence[Mapping[str, Any]]] = None,
    available_artifacts: Optional[Sequence[str]] = None,
    step_results: Optional[Mapping[str, Mapping[str, Any]]] = None,
    reporting_period: str = "CURRENT",
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Build a validated cycle snapshot from already-produced read-only results."""
    generated_at = generated_at_utc or _now_utc()
    normalized = default_daily_cycle_steps() if steps is None else [
        _normalize_step(item) for item in steps if isinstance(item, Mapping)
    ]
    normalized.sort(key=lambda item: item["sequence"])
    seen: set[str] = set()
    for step in normalized:
        name = step["step_name"]
        if name in seen:
            raise ValueError(f"Duplicate daily-cycle step: {name}")
        seen.add(name)
        invalid = [dep for dep in step["dependencies"] if STEP_ORDER.index(dep) >= STEP_ORDER.index(name)]
        if invalid:
            raise ValueError(f"Step {name} has invalid forward dependency: {invalid}")

    available = {str(item) for item in (available_artifacts or []) if str(item).strip()}
    supplied_results = {str(key).upper(): dict(value) for key, value in (step_results or {}).items() if isinstance(value, Mapping)}
    warnings: list[str] = []
    completed: set[str] = set()
    for step in normalized:
        name = step["step_name"]
        missing_inputs = [item for item in step["input_artifacts"] if item not in available]
        if missing_inputs:
            message = f"Missing input artifacts: {', '.join(missing_inputs)}"
            step["warnings"].append(message)
            warnings.append(f"{name}: {message}")
        if not step["enabled"]:
            step["status"] = "SKIPPED"
            continue
        if any(dep not in completed for dep in step["dependencies"]):
            step["status"] = "BLOCKED"
            step["error"] = "One or more dependencies did not complete."
            continue
        result = supplied_results.get(name)
        if result is None:
            step["status"] = "PENDING"
            continue
        status = _upper(result.get("status"), "COMPLETED")
        step["status"] = status if status in {"COMPLETED", "WARNING", "FAILED", "SKIPPED"} else "COMPLETED"
        step["result"] = result
        if step["status"] in {"COMPLETED", "WARNING", "SKIPPED"}:
            completed.add(name)

    statuses = [item["status"] for item in normalized]
    if "FAILED" in statuses or "BLOCKED" in statuses:
        cycle_status = "FAILED"
    elif all(status in {"COMPLETED", "WARNING", "SKIPPED"} for status in statuses):
        cycle_status = "COMPLETED_WITH_WARNINGS" if "WARNING" in statuses or "SKIPPED" in statuses else "COMPLETED"
    else:
        cycle_status = "PLANNED"

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "cycle_id": _cycle_id(reporting_period, generated_at),
        "reporting_period": reporting_period,
        "generated_at_utc": generated_at,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "advisory_only": True,
        "orchestration_only": True,
        "cycle_status": cycle_status,
        "summary": {
            "total_steps": len(normalized),
            "completed_steps": statuses.count("COMPLETED"),
            "warning_steps": statuses.count("WARNING"),
            "pending_steps": statuses.count("PENDING"),
            "skipped_steps": statuses.count("SKIPPED"),
            "blocked_steps": statuses.count("BLOCKED"),
            "failed_steps": statuses.count("FAILED"),
            "warning_count": len(warnings),
        },
        "steps": normalized,
        "warnings": warnings,
        "governance": {
            "human_approval_required": True,
            "order_execution_allowed": False,
            "capital_movement_allowed": False,
            "policy_changes_allowed": False,
        },
    }


def render_enterprise_dividend_daily_cycle_markdown(cycle: Mapping[str, Any]) -> str:
    lines = [
        "# Enterprise Dividend Daily Cycle",
        "",
        f"- Cycle ID: `{cycle.get('cycle_id', '')}`",
        f"- Status: **{cycle.get('cycle_status', 'UNKNOWN')}**",
        f"- Reporting period: `{cycle.get('reporting_period', '')}`",
        f"- Paper trade mode: `{cycle.get('paper_trade_mode')}`",
        "",
        "## Dependency-Ordered Steps",
        "",
        "| # | Step | Service | Status |",
        "|---:|---|---|---|",
    ]
    for step in cycle.get("steps", []):
        lines.append(f"| {step.get('sequence')} | {step.get('step_name')} | `{step.get('service_name')}` | {step.get('status')} |")
    lines.extend(["", "## Warnings", ""])
    warnings = list(cycle.get("warnings") or [])
    lines.extend([f"- {item}" for item in warnings] if warnings else ["- None"])
    lines.extend([
        "", "## Governance", "",
        "This cycle is paper-only and orchestration-only. It cannot place orders, communicate with a broker, move capital, or change policy.", "",
    ])
    return "\n".join(lines)


def write_enterprise_dividend_daily_cycle(cycle: Mapping[str, Any], output_dir: Path | str) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / DEFAULT_OUTPUT_FILES["json"]
    markdown_path = output_path / DEFAULT_OUTPUT_FILES["markdown"]
    json_path.write_text(json.dumps(dict(cycle), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_enterprise_dividend_daily_cycle_markdown(cycle), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def build_and_write_enterprise_dividend_daily_cycle(output_dir: Path | str, **kwargs: Any) -> dict[str, Any]:
    cycle = build_enterprise_dividend_daily_cycle(**kwargs)
    cycle["output_files"] = write_enterprise_dividend_daily_cycle(cycle, output_dir)
    return cycle
