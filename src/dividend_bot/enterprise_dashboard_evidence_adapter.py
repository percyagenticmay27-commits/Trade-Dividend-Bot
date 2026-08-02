"""Adapt existing AI CIO host artifacts into dashboard input contracts.

Read-only and paper-only. This module never changes cash, allocations, governance,
trading state, registry state, or broker state.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True


def _mapping(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.is_file():
        return {}, f"missing evidence: {path}"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, f"invalid evidence {path}: {exc}"
    if not isinstance(value, dict):
        return {}, f"invalid evidence {path}: root must be an object"
    return value, None


def _rows_json(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    payload, warning = _mapping(path)
    if warning:
        return [], warning
    for key in ("rows", "records", "transactions", "payments", "holdings", "positions", "allocations"):
        value = payload.get(key)
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, Mapping)], None
    return [], None


def _rows_csv(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    if not path.is_file():
        return [], f"missing evidence: {path}"
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)], None
    except (OSError, UnicodeError, csv.Error) as exc:
        return [], f"invalid evidence {path}: {exc}"


def _bool(value: Any, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first(mapping: Mapping[str, Any], names: Sequence[str], default: Any = None) -> Any:
    for name in names:
        if name in mapping and mapping[name] is not None:
            return mapping[name]
    return default


def _registry_plugins(registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = registry.get("strategy_plugins")
    return [dict(item) for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _strategy_id(plugin: Mapping[str, Any]) -> str:
    return str(_first(plugin, ("strategy_id", "plugin_id", "service_id"), "UNKNOWN"))


def _strategy_name(plugin: Mapping[str, Any]) -> str:
    return str(_first(plugin, ("display_name", "strategy_name", "name"), _strategy_id(plugin)))


def _paper_safe(plugin: Mapping[str, Any]) -> bool:
    return (
        _bool(plugin.get("paper_trade_mode"), False)
        and _bool(plugin.get("paper_compatible"), True)
        and _bool(plugin.get("advisory_only"), True)
        and _bool(plugin.get("reporting_only"), True)
        and not _bool(plugin.get("live_trading_enabled"), True)
        and not _bool(plugin.get("broker_execution_enabled"), True)
        and not _bool(plugin.get("capital_movement_enabled"), True)
        and not _bool(plugin.get("automatic_activation_allowed"), True)
        and not _bool(plugin.get("direct_database_writes"), True)
    )


def build_strategy_inventory(registry: Mapping[str, Any]) -> dict[str, Any]:
    strategies: list[dict[str, Any]] = []
    for plugin in _registry_plugins(registry):
        strategy_id = _strategy_id(plugin)
        status = str(_first(plugin, ("runtime_status", "status"), "UNKNOWN")).upper()
        health = str(_first(plugin, ("health_status", "health"), "UNKNOWN")).upper()
        safe = _paper_safe(plugin)
        strategies.append({
            "strategy_id": strategy_id,
            "strategy_name": _strategy_name(plugin),
            "strategy_type": str(_first(plugin, ("strategy_type", "plugin_type", "bot_type"), "STRATEGY")),
            "version": str(plugin.get("version", "UNKNOWN")),
            "lifecycle_status": str(plugin.get("lifecycle_status", status)),
            "certification_level": str(plugin.get("certification_level", "PAPER_ONLY")),
            "runtime_status": status,
            "health_status": health,
            "readiness": str(_first(plugin, ("readiness", "status"), "UNKNOWN")).upper(),
            "output_count": int(_number(plugin.get("output_count"), 0)),
            "registered": True,
            "paper_safe": safe,
            "evidence_complete": bool(plugin.get("evidence_complete", plugin.get("output_count", 0))),
            "contract_complete": safe,
            "paper_trade_mode": _bool(plugin.get("paper_trade_mode"), False),
            "live_trading_enabled": _bool(plugin.get("live_trading_enabled"), False),
            "broker_execution_enabled": _bool(plugin.get("broker_execution_enabled"), False),
        })
    strategies.sort(key=lambda item: item["strategy_id"])
    return {
        "strategies": strategies,
        "summary": {
            "strategy_count": len(strategies),
            "running_count": sum(item["runtime_status"] in {"ONLINE", "ACTIVE", "RUNNING", "READY", "AVAILABLE"} for item in strategies),
            "contract_complete_count": sum(item["contract_complete"] for item in strategies),
        },
    }


def build_enterprise_health(inventory: Mapping[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for item in inventory.get("strategies", []):
        if not isinstance(item, Mapping):
            continue
        safe = bool(item.get("paper_safe", item.get("contract_complete")))
        health = str(item.get("health_status", "UNKNOWN")).upper()
        if not safe:
            classification = "CRITICAL"
        elif health in {"HEALTHY", "WARNING", "DEGRADED", "CRITICAL"}:
            classification = health
        else:
            classification = "HEALTHY"
        score = 95 if classification == "HEALTHY" else 75 if classification == "WARNING" else 50 if classification == "DEGRADED" else 0
        rows.append({"strategy_id": item.get("strategy_id"), "classification": classification, "health_score": score})
    counts = {name: sum(row["classification"] == name for row in rows) for name in ("HEALTHY", "WARNING", "DEGRADED", "CRITICAL")}
    status = (
        "UNKNOWN" if not rows
        else "CRITICAL" if counts["CRITICAL"]
        else "DEGRADED" if counts["DEGRADED"]
        else "WARNING" if counts["WARNING"]
        else "HEALTHY"
    )
    return {
        "enterprise_status": status,
        "strategies": rows,
        "summary": {
            "healthy_count": counts["HEALTHY"],
            "warning_count": counts["WARNING"],
            "degraded_count": counts["DEGRADED"],
            "critical_count": counts["CRITICAL"],
            "offline_count": 0,
            "average_health_score": round(sum(row["health_score"] for row in rows) / len(rows), 2) if rows else 0.0,
        },
    }


def _load_first_rows(paths: Sequence[Path]) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    for path in paths:
        rows, warning = _rows_csv(path) if path.suffix.lower() == ".csv" else _rows_json(path)
        if warning:
            warnings.append(warning)
        if rows:
            return rows, warnings
    return [], warnings


def build_investor_evidence(*, root_dir: Path, results_dir: Path, state_dir: Path) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    cash, warning = _mapping(state_dir / "paper_cash_account.json")
    if warning:
        warnings.append(warning)
    holdings, row_warnings = _load_first_rows((results_dir / "portfolio_snapshot.csv", root_dir / "portfolio_snapshot.csv", results_dir / "portfolio_snapshot.json"))
    warnings.extend(row_warnings)
    payments, payment_warnings = _load_first_rows((results_dir / "payment_history.csv", root_dir / "paper_dividend_history.csv", results_dir / "paper_dividend_history.csv", results_dir / "payment_history.json"))
    warnings.extend(payment_warnings)
    upcoming, upcoming_warnings = _load_first_rows((results_dir / "upcoming_payments.csv", results_dir / "upcoming_payments.json"))
    warnings.extend(upcoming_warnings)

    summary: dict[str, Any] = {}
    if cash or holdings:
        available = _number(_first(cash, ("available_cash", "cash_available", "current_cash"), 0.0))
        allocated = _number(_first(cash, ("allocated_cash", "total_allocated_cash"), 0.0))
        holdings_value = sum(_number(_first(row, ("market_value", "position_value", "value"), 0.0)) for row in holdings)
        portfolio_value = _number(_first(cash, ("portfolio_value",), available + allocated if cash else holdings_value))
        summary = {
            "portfolio_value": portfolio_value,
            "cost_basis": _number(_first(cash, ("cost_basis",), allocated)),
            "capital_appreciation": _number(_first(cash, ("capital_appreciation",), 0.0)),
            "projected_annual_income": _number(_first(cash, ("projected_annual_income", "annual_income"), 0.0)),
            "cash_value": available,
            "cash_percent": (available / portfolio_value * 100.0) if portfolio_value else 0.0,
        }
    return {
        "portfolio_summary": summary,
        "holdings": holdings,
        "payment_history": payments,
        "upcoming_payments": upcoming,
        "review_flags": [],
        "evidence_metadata": {
            "read_only": True,
            "paper_trade_mode": True,
            "portfolio_summary_available": bool(summary),
            "holdings_available": bool(holdings),
            "payment_history_available": bool(payments),
            "upcoming_payments_available": bool(upcoming),
        },
    }, warnings


def build_dashboard_evidence(*, root_dir: str | Path = ".", results_dir: str | Path = "results", state_dir: str | Path = "state") -> dict[str, Any]:
    root = Path(root_dir)
    results = Path(results_dir)
    state = Path(state_dir)
    if not results.is_absolute():
        results = root / results
    if not state.is_absolute():
        state = root / state

    registry, registry_warning = _mapping(results / "enterprise_dividend_service_registry.json")
    registry_plugins = _registry_plugins(registry)
    warnings: list[str] = []
    if registry_warning:
        warnings.append(registry_warning)

    evidence_source: str | None = None
    if registry_plugins:
        inventory = build_strategy_inventory(registry)
        health = build_enterprise_health(inventory)
        evidence_source = "enterprise_service_registry"
    else:
        existing_inventory, inventory_warning = _mapping(results / "strategy_inventory.json")
        existing_health, health_warning = _mapping(results / "enterprise_health.json")
        if existing_inventory and existing_health:
            inventory = existing_inventory
            health = existing_health
            evidence_source = "existing_dashboard_inputs"
        else:
            inventory = {}
            health = {}
            warnings.extend(message for message in (inventory_warning, health_warning) if message)

    investor, investor_warnings = build_investor_evidence(root_dir=root, results_dir=results, state_dir=state)
    warnings.extend(investor_warnings)
    return {
        "strategy_inventory": inventory,
        "enterprise_health": health,
        "required_evidence_available": bool(inventory and health),
        "executive_evidence_source": evidence_source,
        "investor_evidence": investor,
        "warnings": sorted(set(warnings)),
    }
