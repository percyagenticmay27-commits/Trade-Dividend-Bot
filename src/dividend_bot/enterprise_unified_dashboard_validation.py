"""End-to-end validation for the unified Enterprise AI CIO dashboard artifacts.

The validator is paper-only, read-only, and reporting-only. It verifies existing
published artifacts and never imports strategy production code, changes
calculations, moves capital, contacts a broker, or places orders.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping, Sequence

MODULE_NAME = "enterprise_unified_dashboard_validation"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True
READ_ONLY = True

DEFAULT_REQUIRED_STRATEGIES = ("DIVIDEND-001", "SWING-001")
ARTIFACT_FILENAMES = {
    "registry": "enterprise_dividend_service_registry.json",
    "executive_dashboard": "ai_cio_executive_dashboard.json",
    "investor_dashboard": "enterprise_investor_dashboard.json",
    "strategy_kpis": "enterprise_strategy_kpis.json",
    "dividend_journal": "dividend_strategy_decision_journal.json",
    "swing_journal": "swing_strategy_decision_journal.json",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _read_mapping(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.is_file():
        return {}, f"Required unified-dashboard artifact is missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, f"Unified-dashboard artifact is invalid: {path}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"Unified-dashboard artifact root must be an object: {path}"
    return payload, None


def _strategy_ids(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    return sorted(
        {
            str(row.get("strategy_id") or "").strip()
            for row in rows
            if isinstance(row, Mapping)
            and str(row.get("strategy_id") or "").strip()
        }
    )


def _registry_rows(registry: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = registry.get("strategy_plugins")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _kpi_rows(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = document.get("strategies")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _dashboard_rows(dashboard: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = dashboard.get("strategy_kpis")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _paper_safety_errors(
    name: str,
    payload: Mapping[str, Any],
    *,
    require_read_only: bool = False,
) -> list[str]:
    errors: list[str] = []
    if payload.get("paper_trade_mode") is not True:
        errors.append(f"{name}: paper_trade_mode must be true")
    if payload.get("live_trading_enabled") is not False:
        errors.append(f"{name}: live_trading_enabled must be false")
    if payload.get("broker_execution_enabled") is not False:
        errors.append(f"{name}: broker_execution_enabled must be false")
    if payload.get("capital_movement_enabled") not in (None, False):
        errors.append(f"{name}: capital_movement_enabled must be false")
    if require_read_only and payload.get("read_only") is not True:
        errors.append(f"{name}: read_only must be true")
    return errors


def _required_strategy_errors(
    source_name: str,
    actual_ids: Sequence[str],
    required_ids: Sequence[str],
) -> list[str]:
    errors: list[str] = []
    actual = set(actual_ids)
    for strategy_id in required_ids:
        if strategy_id not in actual:
            errors.append(f"{source_name}: required strategy is missing: {strategy_id}")
    if len(actual_ids) != len(set(actual_ids)):
        errors.append(f"{source_name}: duplicate strategy IDs are not allowed")
    return errors


def validate_unified_dashboard_artifacts(
    *,
    results_dir: str | Path = "results",
    required_strategy_ids: Sequence[str] = DEFAULT_REQUIRED_STRATEGIES,
) -> dict[str, Any]:
    """Validate registry-to-dashboard-to-journal continuity for required strategies."""
    directory = Path(results_dir)
    artifacts: dict[str, dict[str, Any]] = {}
    artifact_paths: dict[str, str] = {}
    errors: list[str] = []
    warnings: list[str] = []

    for name, filename in ARTIFACT_FILENAMES.items():
        path = directory / filename
        payload, error = _read_mapping(path)
        artifacts[name] = payload
        artifact_paths[name] = str(path)
        if error:
            errors.append(error)

    required_ids = sorted(
        {str(item).strip() for item in required_strategy_ids if str(item).strip()}
    )
    registry_ids = _strategy_ids(_registry_rows(artifacts["registry"]))
    kpi_rows = _kpi_rows(artifacts["strategy_kpis"])
    kpi_ids = _strategy_ids(kpi_rows)
    executive_ids = _strategy_ids(_dashboard_rows(artifacts["executive_dashboard"]))
    investor_ids = _strategy_ids(_dashboard_rows(artifacts["investor_dashboard"]))

    errors.extend(_required_strategy_errors("registry", registry_ids, required_ids))
    errors.extend(_required_strategy_errors("strategy_kpis", kpi_ids, required_ids))
    errors.extend(
        _required_strategy_errors("executive_dashboard", executive_ids, required_ids)
    )
    errors.extend(
        _required_strategy_errors("investor_dashboard", investor_ids, required_ids)
    )

    for name in ("executive_dashboard", "investor_dashboard"):
        if artifacts[name]:
            errors.extend(_paper_safety_errors(name, artifacts[name]))
    for name in ("dividend_journal", "swing_journal"):
        journal = artifacts[name]
        if not journal:
            continue
        errors.extend(_paper_safety_errors(name, journal, require_read_only=True))
        journal_strategy_id = str(journal.get("strategy_id") or "").strip()
        decisions = journal.get("decisions")
        if not isinstance(decisions, list):
            errors.append(f"{name}: decisions must be a list")
            decisions = []
        for decision in decisions:
            if not isinstance(decision, Mapping):
                errors.append(f"{name}: decision entries must be objects")
                continue
            entry_strategy_id = str(
                decision.get("strategy_id") or journal_strategy_id
            ).strip()
            if entry_strategy_id != journal_strategy_id:
                errors.append(
                    f"{name}: cross-strategy decision rejected: "
                    f"expected {journal_strategy_id}, got {entry_strategy_id}"
                )
        if not decisions:
            warnings.append(
                f"{name}: no decision evidence is currently reported; "
                "safe empty journal accepted"
            )

    journal_ids = sorted(
        {
            str(artifacts[name].get("strategy_id") or "").strip()
            for name in ("dividend_journal", "swing_journal")
            if artifacts[name]
            and str(artifacts[name].get("strategy_id") or "").strip()
        }
    )
    errors.extend(_required_strategy_errors("decision_journals", journal_ids, required_ids))

    kpi_summary: dict[str, dict[str, Any]] = {}
    for row in kpi_rows:
        strategy_id = str(row.get("strategy_id") or "").strip()
        if not strategy_id:
            continue
        health = str(row.get("health_status") or "").strip()
        allocated = row.get("allocated_capital")
        if not health:
            errors.append(f"strategy_kpis: health_status is missing: {strategy_id}")
        if not isinstance(allocated, (int, float)) or isinstance(allocated, bool):
            errors.append(
                f"strategy_kpis: allocated_capital must be numeric: {strategy_id}"
            )
        elif allocated < 0:
            errors.append(
                f"strategy_kpis: allocated_capital must not be negative: {strategy_id}"
            )
        elif allocated == 0:
            warnings.append(
                f"strategy_kpis: allocated_capital is zero: {strategy_id}"
            )
        kpi_summary[strategy_id] = {
            "health_status": health or "UNKNOWN",
            "allocated_capital": allocated,
            "evidence_status": str(row.get("evidence_status") or "NOT_REPORTED"),
            "decision_journal_status": str(
                row.get("decision_journal_status") or "NOT_REPORTED"
            ),
        }

    errors = sorted(set(errors))
    warnings = sorted(set(warnings))
    status = "PASSED" if not errors else "FAILED"
    return {
        "schema_version": SCHEMA_VERSION,
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "generated_at_utc": _utc_now(),
        "validation_status": status,
        "required_strategy_ids": required_ids,
        "registry_strategy_ids": registry_ids,
        "kpi_strategy_ids": kpi_ids,
        "executive_strategy_ids": executive_ids,
        "investor_strategy_ids": investor_ids,
        "journal_strategy_ids": journal_ids,
        "strategy_count": len(kpi_ids),
        "strategy_kpi_summary": kpi_summary,
        "artifact_paths": artifact_paths,
        "errors": errors,
        "warnings": warnings,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "read_only": True,
    }


def render_unified_dashboard_validation_markdown(
    report: Mapping[str, Any],
) -> str:
    strategy_ids = report.get("kpi_strategy_ids")
    strategies = ", ".join(str(item) for item in strategy_ids) if isinstance(strategy_ids, list) else "None"
    errors = report.get("errors") if isinstance(report.get("errors"), list) else []
    warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
    lines = [
        "# Enterprise Unified Dashboard Validation",
        "",
        f"- Status: **{report.get('validation_status', 'UNKNOWN')}**",
        f"- Strategies: {strategies or 'None'}",
        f"- Paper trade mode: {report.get('paper_trade_mode')}",
        f"- Live trading enabled: {report.get('live_trading_enabled')}",
        f"- Broker execution enabled: {report.get('broker_execution_enabled')}",
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


def write_unified_dashboard_validation(
    report: Mapping[str, Any],
    *,
    results_dir: str | Path = "results",
) -> dict[str, str]:
    directory = Path(results_dir)
    json_path = directory / "enterprise_unified_dashboard_validation.json"
    markdown_path = directory / "enterprise_unified_dashboard_validation.md"
    _atomic_write(
        json_path,
        json.dumps(dict(report), indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(
        markdown_path,
        render_unified_dashboard_validation_markdown(report),
    )
    return {
        "json": str(json_path),
        "markdown": str(markdown_path),
    }


def validate_and_write_unified_dashboard(
    *,
    results_dir: str | Path = "results",
    required_strategy_ids: Sequence[str] = DEFAULT_REQUIRED_STRATEGIES,
) -> dict[str, Any]:
    report = validate_unified_dashboard_artifacts(
        results_dir=results_dir,
        required_strategy_ids=required_strategy_ids,
    )
    report["output_paths"] = write_unified_dashboard_validation(
        report,
        results_dir=results_dir,
    )
    return report
