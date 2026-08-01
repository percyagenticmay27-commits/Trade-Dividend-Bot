"""Refresh read-only Enterprise dashboard artifacts for the AI CIO portal."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.dividend_bot.enterprise_dashboard_evidence_adapter import build_dashboard_evidence
from src.dividend_bot.enterprise_strategy_kpi_adapter import build_strategy_kpis
from src.dividend_bot.enterprise_executive_dashboard import (
    build_executive_dashboard,
    render_executive_dashboard_markdown,
)
from src.dividend_bot.enterprise_investor_dashboard_integration import (
    build_enterprise_investor_dashboard,
    render_enterprise_investor_dashboard_markdown,
)

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True
DEFAULT_RESULTS_DIR = Path("results")
DEFAULT_EXECUTIVE_JSON = "ai_cio_executive_dashboard.json"
DEFAULT_EXECUTIVE_MARKDOWN = "ai_cio_executive_dashboard.md"
DEFAULT_INVESTOR_JSON = "enterprise_investor_dashboard.json"
DEFAULT_INVESTOR_MARKDOWN = "enterprise_investor_dashboard.md"
DEFAULT_INVESTOR_SOURCE_CANDIDATES = (
    "enterprise_dividend_investor_dashboard.json",
    "dividend_investor_dashboard.json",
    "investor_portfolio_report.json",
)
OPTIONAL_EXECUTIVE_INPUTS = (
    "runtime_snapshot.json",
    "event_statistics.json",
    "plugin_registry.json",
    "runtime_metrics.json",
    "scheduler_status.json",
)


def _read_mapping(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.is_file():
        return {}, None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, f"invalid dashboard source {path}: {exc}"
    if not isinstance(value, dict):
        return {}, f"invalid dashboard source {path}: root must be an object"
    return value, None


def _atomic_write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return path


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    return _atomic_write_text(
        path, json.dumps(dict(payload), indent=2, sort_keys=True) + "\n"
    )


def _existing_investor_source(
    directory: Path,
    candidates: Sequence[str | Path],
) -> tuple[dict[str, Any], Path | None, list[str]]:
    warnings: list[str] = []
    for candidate in candidates:
        path = Path(candidate)
        if not path.is_absolute():
            path = directory / path
        payload, warning = _read_mapping(path)
        if warning:
            warnings.append(warning)
        elif payload:
            return payload, path, warnings
    return {}, None, warnings


def _strategy_allocations(cash_state: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("strategy_allocations", "allocations", "allocated_by_strategy"):
        value = cash_state.get(key)
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _publish_optional_executive_evidence(
    directory: Path,
    *,
    inventory: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> None:
    """Publish explicit read-only availability records without inventing metrics."""
    strategies = (
        inventory.get("strategies")
        if isinstance(inventory.get("strategies"), list)
        else []
    )
    summary = (
        inventory.get("summary")
        if isinstance(inventory.get("summary"), Mapping)
        else {}
    )
    running = int(summary.get("running_count", 0) or 0)
    plugin_count = len(strategies)
    runtime_status = "RUNNING" if running else "UNKNOWN"
    documents: dict[str, dict[str, Any]] = {
        "runtime_snapshot.json": {
            "runtime_status": runtime_status,
            "plugin_count": plugin_count,
            "running_strategy_count": running,
            "evidence_status": "DERIVED_FROM_STRATEGY_INVENTORY",
            "read_only": True,
        },
        "plugin_registry.json": dict(registry)
        if registry
        else {
            "strategy_plugins": strategies,
            "evidence_status": "DERIVED_FROM_EXISTING_STRATEGY_INVENTORY",
            "read_only": True,
        },
        "event_statistics.json": {
            "evidence_status": "NOT_REPORTED",
            "read_only": True,
        },
        "runtime_metrics.json": {
            "evidence_status": "NOT_REPORTED",
            "read_only": True,
        },
        "scheduler_status.json": {
            "evidence_status": "NOT_REPORTED",
            "read_only": True,
        },
    }
    for filename in OPTIONAL_EXECUTIVE_INPUTS:
        path = directory / filename
        if not path.exists():
            _atomic_write_json(path, documents[filename])


def _adapter_availability(adapted: Mapping[str, Any]) -> dict[str, bool]:
    metadata = adapted.get("evidence_metadata")
    if not isinstance(metadata, Mapping):
        metadata = {}
    return {
        "portfolio_summary": bool(metadata.get("portfolio_summary_available")),
        "holdings": bool(metadata.get("holdings_available")),
        "payment_history": bool(metadata.get("payment_history_available")),
        "upcoming_payments": bool(metadata.get("upcoming_payments_available")),
    }


def _classify_investor_evidence(
    *,
    source_path: Path | None,
    adapted: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify provenance independently from dashboard calculations.

    A published artifact is authoritative for presentation. Adapter evidence is a
    read-only reconstruction from host state and reports. An empty generated
    summary is never treated as evidence merely because a builder returned a
    dictionary containing zero values.
    """
    if source_path is not None:
        return {
            "source_type": "PUBLISHED_ARTIFACT",
            "source_id": str(source_path),
            "completeness": "COMPLETE",
            "authoritative": True,
            "reconstructed": False,
        }

    availability = _adapter_availability(adapted)
    available_count = sum(availability.values())
    if available_count == 0:
        return {
            "source_type": "NONE",
            "source_id": None,
            "completeness": "NONE",
            "authoritative": False,
            "reconstructed": False,
            "available_components": availability,
        }

    complete = availability["portfolio_summary"] and (
        availability["holdings"] or availability["payment_history"]
    )
    return {
        "source_type": "ADAPTER_RECONSTRUCTION",
        "source_id": "enterprise_dashboard_evidence_adapter",
        "completeness": "COMPLETE" if complete else "PARTIAL",
        "authoritative": False,
        "reconstructed": True,
        "available_components": availability,
    }


def _effective_investor_status(
    builder_status: Any,
    provenance: Mapping[str, Any],
) -> str:
    """Keep builder calculations intact while preventing false READY labels."""
    status = str(builder_status or "UNKNOWN").upper()
    source_type = str(provenance.get("source_type", "NONE"))
    completeness = str(provenance.get("completeness", "NONE"))

    if source_type == "NONE":
        return "PARTIAL"
    if source_type == "ADAPTER_RECONSTRUCTION" and completeness != "COMPLETE":
        return "PARTIAL"
    return status


def refresh_enterprise_dashboards(
    *,
    results_dir: str | Path = DEFAULT_RESULTS_DIR,
    root_dir: str | Path = ".",
    state_dir: str | Path = "state",
    investor_source_candidates: Sequence[str | Path] = DEFAULT_INVESTOR_SOURCE_CANDIDATES,
) -> dict[str, Any]:
    """Publish existing dashboards plus registry-driven per-strategy evidence."""
    root = Path(root_dir)
    requested_results = Path(results_dir)
    directory = requested_results
    if not directory.is_absolute():
        directory = root / directory

    state = Path(state_dir)
    if not state.is_absolute():
        if requested_results.is_absolute() and Path(root_dir) == Path("."):
            state = directory.parent / state
        else:
            state = root / state
    directory.mkdir(parents=True, exist_ok=True)

    evidence = build_dashboard_evidence(
        root_dir=root,
        results_dir=directory,
        state_dir=state,
    )
    inventory = (
        evidence.get("strategy_inventory")
        if isinstance(evidence.get("strategy_inventory"), Mapping)
        else {}
    )
    health = (
        evidence.get("enterprise_health")
        if isinstance(evidence.get("enterprise_health"), Mapping)
        else {}
    )
    if evidence.get("required_evidence_available"):
        _atomic_write_json(directory / "strategy_inventory.json", inventory)
        _atomic_write_json(directory / "enterprise_health.json", health)

    registry, registry_warning = _read_mapping(
        directory / "enterprise_dividend_service_registry.json"
    )
    if evidence.get("required_evidence_available"):
        _publish_optional_executive_evidence(
            directory,
            inventory=inventory,
            registry=registry,
        )

    cash_state, cash_warning = _read_mapping(state / "paper_cash_account.json")
    strategy_kpis, kpi_warnings = build_strategy_kpis(
        registry=registry,
        strategy_allocations=_strategy_allocations(cash_state),
        root_dir=root,
    )
    _atomic_write_json(
        directory / "enterprise_strategy_kpis.json",
        {
            "scope": "ALL_REGISTERED_STRATEGIES",
            "strategy_count": len(strategy_kpis),
            "strategies": strategy_kpis,
            "warnings": kpi_warnings,
        },
    )

    executive = build_executive_dashboard(input_dir=directory)
    executive["dashboard_scope"] = "ENTERPRISE_ALL_REGISTERED_STRATEGIES"
    executive["strategy_kpis"] = strategy_kpis
    executive_json = _atomic_write_json(
        directory / DEFAULT_EXECUTIVE_JSON,
        executive,
    )
    executive_markdown = _atomic_write_text(
        directory / DEFAULT_EXECUTIVE_MARKDOWN,
        render_executive_dashboard_markdown(executive),
    )

    existing_source, source_path, source_warnings = _existing_investor_source(
        directory,
        investor_source_candidates,
    )
    adapted = (
        evidence.get("investor_evidence")
        if isinstance(evidence.get("investor_evidence"), Mapping)
        else {}
    )

    if existing_source:
        investor = build_enterprise_investor_dashboard(
            dividend_dashboard=existing_source
        )
    else:
        investor = build_enterprise_investor_dashboard(
            portfolio_summary=adapted.get("portfolio_summary"),
            holdings=adapted.get("holdings"),
            payment_history=adapted.get("payment_history"),
            upcoming_payments=adapted.get("upcoming_payments"),
            review_flags=adapted.get("review_flags"),
        )

    provenance = _classify_investor_evidence(
        source_path=source_path,
        adapted=adapted,
    )
    investor_source = provenance.get("source_id")
    adapter_warning: str | None = None
    if provenance["source_type"] == "ADAPTER_RECONSTRUCTION":
        adapter_warning = (
            "enterprise_dashboard_evidence_adapter: reconstructed investor "
            f"evidence used ({str(provenance['completeness']).lower()})"
        )
    elif provenance["source_type"] == "NONE":
        adapter_warning = (
            "enterprise_dashboard_evidence_adapter: no usable investor evidence "
            "was available"
        )

    effective_investor_status = _effective_investor_status(
        investor.get("dashboard_status"),
        provenance,
    )
    investor["dashboard_status"] = effective_investor_status
    investor["evidence_provenance"] = provenance
    investor["dashboard_scope"] = "ENTERPRISE_ALL_REGISTERED_STRATEGIES"
    investor["strategy_kpis"] = strategy_kpis
    investor_json = _atomic_write_json(
        directory / DEFAULT_INVESTOR_JSON,
        investor,
    )
    investor_markdown = _atomic_write_text(
        directory / DEFAULT_INVESTOR_MARKDOWN,
        render_enterprise_investor_dashboard_markdown(investor),
    )

    warnings = list(evidence.get("warnings", [])) + source_warnings + kpi_warnings
    warnings.extend(
        item
        for item in (registry_warning, cash_warning, adapter_warning)
        if item
    )
    warnings.extend(str(item) for item in executive.get("warnings", []) if item)
    warnings.extend(str(item) for item in investor.get("warnings", []) if item)
    errors = [str(item) for item in executive.get("errors", []) if item]

    return {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "dashboard_scope": "ENTERPRISE_ALL_REGISTERED_STRATEGIES",
        "executive_dashboard_status": executive.get(
            "enterprise_summary", {}
        ).get("enterprise_status", "UNKNOWN"),
        "investor_dashboard_status": effective_investor_status,
        "investor_source": investor_source,
        "investor_evidence_provenance": provenance,
        "registered_strategy_count": len(strategy_kpis)
        or int(
            executive.get("enterprise_summary", {}).get(
                "registered_strategy_count", 0
            )
            or 0
        ),
        "paths": {
            "strategy_inventory": str(directory / "strategy_inventory.json"),
            "enterprise_health": str(directory / "enterprise_health.json"),
            "strategy_kpis": str(directory / "enterprise_strategy_kpis.json"),
            "executive_json": str(executive_json),
            "executive_markdown": str(executive_markdown),
            "investor_json": str(investor_json),
            "investor_markdown": str(investor_markdown),
        },
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refresh read-only AI CIO portal dashboards"
    )
    parser.add_argument("--root-dir", default=".")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--state-dir", default="state")
    args = parser.parse_args(argv)
    try:
        summary = refresh_enterprise_dashboards(
            root_dir=args.root_dir,
            results_dir=args.results_dir,
            state_dir=args.state_dir,
        )
    except Exception as exc:
        print(f"Dashboard refresh failed: {exc}")
        return 1

    print(f"Dashboard scope: {summary['dashboard_scope']}")
    print(f"Executive dashboard: {summary['paths']['executive_json']}")
    print(f"Investor dashboard: {summary['paths']['investor_json']}")
    print(f"Strategy KPIs: {summary['paths']['strategy_kpis']}")
    print(f"Registered strategies: {summary['registered_strategy_count']}")
    print(f"Executive status: {summary['executive_dashboard_status']}")
    print(f"Investor status: {summary['investor_dashboard_status']}")
    provenance = summary["investor_evidence_provenance"]
    print(
        "Investor evidence: "
        f"{provenance['source_type']} / {provenance['completeness']}"
    )
    for warning in summary["warnings"]:
        print(f"WARNING: {warning}")
    for error in summary["errors"]:
        print(f"ERROR: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
