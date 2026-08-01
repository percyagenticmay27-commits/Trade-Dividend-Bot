"""Build read-only enterprise KPI contributor drill-downs.

The engine consumes normalized AI CIO strategy interpretation rows. It powers
Investor Dashboard More/Details views without mixing strategy-owned KPI
workspaces or changing trading, allocation, governance, or broker behavior.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True

_METRICS: dict[str, dict[str, Any]] = {
    "income": {
        "label": "Income",
        "value_keys": ("income",),
        "aggregation": "SUM",
        "unit": "CURRENCY",
    },
    "performance": {
        "label": "Performance",
        "value_keys": ("performance_percent", "return_percent", "total_return_percent"),
        "aggregation": "REPORTED_NATIVE_VALUES",
        "unit": "PERCENT",
    },
    "realized_pnl": {
        "label": "Realized P&L",
        "value_keys": ("realized_gain", "realized_pnl"),
        "aggregation": "SUM",
        "unit": "CURRENCY",
    },
    "unrealized_pnl": {
        "label": "Unrealized P&L",
        "value_keys": ("unrealized_gain", "unrealized_pnl"),
        "aggregation": "SUM",
        "unit": "CURRENCY",
    },
    "win_rate": {
        "label": "Win Rate",
        "value_keys": ("win_rate_percent",),
        "aggregation": "WEIGHTED_WHEN_COUNTS_AVAILABLE",
        "unit": "PERCENT",
    },
    "yield": {
        "label": "Yield",
        "value_keys": ("yield_percent", "current_yield_percent"),
        "aggregation": "WEIGHTED_WHEN_BASIS_AVAILABLE",
        "unit": "PERCENT",
    },
    "capital_appreciation": {
        "label": "Capital Appreciation",
        "value_keys": ("capital_appreciation", "capital_appreciation_value"),
        "aggregation": "SUM",
        "unit": "CURRENCY",
    },
    "watchlist_count": {
        "label": "Watchlist Count",
        "value_keys": ("watchlist_count",),
        "aggregation": "SUM",
        "unit": "COUNT",
    },
}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_number(row: Mapping[str, Any], keys: Sequence[str]) -> float | None:
    for key in keys:
        value = _number(row.get(key))
        if value is not None:
            return value
    return None


def _strategy_rows(interpretation: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = interpretation.get("strategies")
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        strategy_id = str(item.get("strategy_id") or "").strip()
        if not strategy_id or strategy_id in seen:
            continue
        seen.add(strategy_id)
        rows.append(dict(item))
    rows.sort(key=lambda item: str(item["strategy_id"]))
    return rows


def _weighted_win_rate(rows: Sequence[Mapping[str, Any]]) -> tuple[float | None, str]:
    wins_total = 0.0
    observations_total = 0.0
    for row in rows:
        wins = _number(row.get("wins"))
        observations = _number(row.get("completed_observations"))
        if observations is None:
            losses = _number(row.get("losses"))
            if wins is not None and losses is not None:
                observations = wins + losses
        if wins is not None and observations is not None and observations > 0:
            wins_total += wins
            observations_total += observations
    if observations_total > 0:
        return round((wins_total / observations_total) * 100.0, 2), "WEIGHTED_BY_COMPLETED_OBSERVATIONS"
    return None, "NATIVE_PERCENTAGES_ONLY"


def _weighted_yield(rows: Sequence[Mapping[str, Any]]) -> tuple[float | None, str]:
    weighted = 0.0
    basis_total = 0.0
    for row in rows:
        value = _first_number(row, _METRICS["yield"]["value_keys"])
        basis = _first_number(row, ("yield_basis", "invested_value", "portfolio_value", "allocated_capital"))
        if value is not None and basis is not None and basis > 0:
            weighted += value * basis
            basis_total += basis
    if basis_total > 0:
        return round(weighted / basis_total, 2), "WEIGHTED_BY_REPORTED_BASIS"
    return None, "NATIVE_PERCENTAGES_ONLY"


def build_enterprise_contributor_details(
    *,
    interpretation: Mapping[str, Any],
    metric_id: str,
) -> tuple[dict[str, Any], list[str]]:
    """Return one enterprise More/Details document for the requested metric."""
    if metric_id not in _METRICS:
        raise ValueError(f"Unsupported enterprise contributor metric: {metric_id}")

    definition = _METRICS[metric_id]
    rows = _strategy_rows(interpretation)
    warnings: list[str] = []
    contributors: list[dict[str, Any]] = []
    reported_values: list[float] = []

    for row in rows:
        value = _first_number(row, definition["value_keys"])
        if value is not None:
            reported_values.append(value)
        contributors.append({
            "strategy_id": row["strategy_id"],
            "display_name": str(row.get("display_name") or row["strategy_id"]),
            "strategy_type": str(row.get("strategy_type") or "UNKNOWN"),
            "value": round(value, 2) if value is not None else None,
            "display_status": "REPORTED" if value is not None else "NOT_REPORTED",
            "contribution_percent": None,
            "runtime_status": str(row.get("runtime_status") or "UNKNOWN"),
            "health_status": str(row.get("health_status") or "UNKNOWN"),
            "readiness": str(row.get("readiness") or "UNKNOWN"),
            "lifecycle_status": str(row.get("lifecycle_status") or "UNKNOWN"),
            "evidence_status": str(row.get("evidence_status") or "REGISTRY_ONLY"),
            "paper_trade_mode": bool(row.get("paper_trade_mode", False)),
            "reporting_only": bool(row.get("reporting_only", True)),
        })

    total: float | None
    calculation_method = str(definition["aggregation"])
    if metric_id == "win_rate":
        total, calculation_method = _weighted_win_rate(rows)
        if total is None and reported_values:
            total = round(sum(reported_values) / len(reported_values), 2)
    elif metric_id == "yield":
        total, calculation_method = _weighted_yield(rows)
        if total is None and reported_values:
            total = round(sum(reported_values) / len(reported_values), 2)
    elif metric_id == "performance":
        total = None
        if reported_values:
            warnings.append(
                "Enterprise Performance requires an approved normalization contract; native strategy values are shown without inventing a combined total."
            )
    else:
        total = round(sum(reported_values), 2) if reported_values else None

    if metric_id not in {"performance", "win_rate", "yield"} and total not in (None, 0):
        for contributor in contributors:
            value = contributor["value"]
            if value is not None:
                contributor["contribution_percent"] = round((value / total) * 100.0, 2)

    missing_ids = [item["strategy_id"] for item in contributors if item["value"] is None]
    complete = len(reported_values) == len(contributors) and bool(contributors)

    document = {
        "schema_version": "1.0",
        "source": "ENTERPRISE_CONTRIBUTOR_ENGINE",
        "scope": "ALL_REGISTERED_STRATEGIES",
        "metric_id": metric_id,
        "metric_label": definition["label"],
        "unit": definition["unit"],
        "enterprise_value": total,
        "calculation_method": calculation_method,
        "reported_strategy_count": len(reported_values),
        "registered_strategy_count": len(contributors),
        "complete": complete,
        "missing_strategy_ids": missing_ids,
        "contributors": contributors,
        "details_action": "MORE_OR_DETAILS",
        "analysis_workspace": "ONE_VIEW_ANALYSIS",
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "read_only": True,
    }
    return document, sorted(set(warnings))


def build_all_enterprise_contributor_details(
    *, interpretation: Mapping[str, Any]
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Build all approved enterprise contributor drill-down documents."""
    documents: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for metric_id in _METRICS:
        document, metric_warnings = build_enterprise_contributor_details(
            interpretation=interpretation,
            metric_id=metric_id,
        )
        documents[metric_id] = document
        warnings.extend(metric_warnings)
    return documents, sorted(set(warnings))
