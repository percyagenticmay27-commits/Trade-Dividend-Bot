"""Read-only AI CIO interpretation of registered strategy evidence.

Consumes the canonical strategy-discovery document and existing per-strategy KPI
rows. It never imports strategy production code, changes allocations, moves
capital, creates orders, or modifies dashboard-builder calculations.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True

_NUMERIC_METRICS = (
    "allocated_capital",
    "portfolio_value",
    "realized_gain",
    "unrealized_gain",
    "income",
)
_COUNT_METRICS = ("watchlist_count", "position_count")
_COMPARISON_METRICS = (
    "portfolio_value",
    "opportunity_quality",
    "win_rate_percent",
    "income",
)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _discovery_rows(discovery: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = discovery.get("strategies")
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
    return rows


def _index_kpis(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    indexed: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            warnings.append("Malformed strategy KPI row ignored.")
            continue
        strategy_id = str(row.get("strategy_id") or "").strip()
        if not strategy_id:
            warnings.append("Strategy KPI row without strategy_id ignored.")
            continue
        if strategy_id in indexed:
            warnings.append(f"Duplicate strategy KPI row ignored: {strategy_id}")
            continue
        indexed[strategy_id] = dict(row)
    return indexed, warnings


def _total(
    strategies: Sequence[Mapping[str, Any]], metric: str, *, integer: bool = False
) -> dict[str, Any]:
    values = [
        value
        for strategy in strategies
        if (value := _number(strategy.get(metric))) is not None
    ]
    total: int | float = int(sum(values)) if integer else round(sum(values), 2)
    return {
        "value": total,
        "reported_strategy_count": len(values),
        "registered_strategy_count": len(strategies),
        "complete": len(values) == len(strategies),
    }


def _leader(
    strategies: Sequence[Mapping[str, Any]], metric: str
) -> dict[str, Any] | None:
    candidates: list[tuple[float, str, str]] = []
    for strategy in strategies:
        value = _number(strategy.get(metric))
        if value is None:
            continue
        strategy_id = str(strategy.get("strategy_id") or "UNKNOWN")
        display_name = str(strategy.get("display_name") or strategy_id)
        candidates.append((value, strategy_id, display_name))
    if not candidates:
        return None
    value, strategy_id, display_name = sorted(
        candidates, key=lambda item: (-item[0], item[1])
    )[0]
    return {
        "strategy_id": strategy_id,
        "display_name": display_name,
        "metric": metric,
        "value": round(value, 2),
        "comparison_basis": "REPORTED_EVIDENCE_ONLY",
    }


def _commentary(
    strategies: Sequence[Mapping[str, Any]], totals: Mapping[str, Any]
) -> list[str]:
    if not strategies:
        return ["No registered strategy evidence is available for AI CIO interpretation."]
    names = ", ".join(
        str(item.get("display_name") or item["strategy_id"]) for item in strategies
    )
    comments = [
        f"The AI CIO interpreted {len(strategies)} registered strategies: {names}."
    ]
    registry_only = [
        str(item["strategy_id"])
        for item in strategies
        if item.get("evidence_status") != "AVAILABLE"
    ]
    if registry_only:
        comments.append(
            "Detailed KPI evidence is not yet available for: "
            + ", ".join(registry_only)
            + "."
        )
    portfolio = totals["portfolio_value"]
    comments.append(
        "Enterprise portfolio value is based on "
        f"{portfolio['reported_strategy_count']} of "
        f"{portfolio['registered_strategy_count']} registered strategies."
    )
    return comments


def build_ai_cio_strategy_interpretation(
    *,
    strategy_discovery: Mapping[str, Any],
    strategy_kpis: Sequence[Mapping[str, Any]] = (),
) -> tuple[dict[str, Any], list[str]]:
    """Build a deterministic, evidence-only multi-strategy interpretation."""
    discovery_rows = _discovery_rows(strategy_discovery)
    kpi_index, warnings = _index_kpis(strategy_kpis)
    registered_ids = [str(item["strategy_id"]) for item in discovery_rows]

    strategies: list[dict[str, Any]] = []
    for discovered in discovery_rows:
        strategy_id = str(discovered["strategy_id"])
        kpi = kpi_index.get(strategy_id)
        if kpi is None:
            warnings.append(f"{strategy_id}: strategy KPI evidence is unavailable.")
            kpi = {}
        row: dict[str, Any] = {
            "strategy_id": strategy_id,
            "display_name": str(
                discovered.get("display_name") or kpi.get("display_name") or strategy_id
            ),
            "strategy_type": discovered.get(
                "strategy_type", kpi.get("strategy_type", "UNKNOWN")
            ),
            "runtime_status": discovered.get(
                "runtime_status", kpi.get("runtime_status", "UNKNOWN")
            ),
            "health_status": discovered.get(
                "health_status", kpi.get("health_status", "UNKNOWN")
            ),
            "readiness": discovered.get(
                "readiness", kpi.get("readiness", "UNKNOWN")
            ),
            "enabled": bool(discovered.get("enabled", kpi.get("enabled", False))),
            "paper_trade_mode": bool(
                discovered.get("paper_trade_mode", kpi.get("paper_trade_mode", False))
            ),
            "paper_compatible": bool(
                discovered.get("paper_compatible", kpi.get("paper_compatible", False))
            ),
            "reporting_only": bool(
                discovered.get("reporting_only", kpi.get("reporting_only", True))
            ),
            "evidence_status": str(kpi.get("evidence_status", "REGISTRY_ONLY")),
        }
        for metric in _NUMERIC_METRICS + _COUNT_METRICS + (
            "opportunity_quality",
            "win_rate_percent",
        ):
            value = _number(kpi.get(metric))
            row[metric] = (
                int(value)
                if metric in _COUNT_METRICS and value is not None
                else value
            )
        strategies.append(row)

    for strategy_id in sorted(set(kpi_index) - set(registered_ids)):
        warnings.append(f"Unregistered strategy KPI row ignored: {strategy_id}")

    unsafe = [
        str(item["strategy_id"])
        for item in strategies
        if not item["paper_trade_mode"] or not item["reporting_only"]
    ]
    if unsafe:
        warnings.append("Unsafe strategy safety metadata detected: " + ", ".join(unsafe))

    totals = {metric: _total(strategies, metric) for metric in _NUMERIC_METRICS}
    totals.update(
        {metric: _total(strategies, metric, integer=True) for metric in _COUNT_METRICS}
    )
    leaders = {
        metric: leader
        for metric in _COMPARISON_METRICS
        if (leader := _leader(strategies, metric)) is not None
    }

    health: dict[str, int] = {}
    readiness: dict[str, int] = {}
    for strategy in strategies:
        health_key = str(strategy["health_status"])
        readiness_key = str(strategy["readiness"])
        health[health_key] = health.get(health_key, 0) + 1
        readiness[readiness_key] = readiness.get(readiness_key, 0) + 1

    document = {
        "schema_version": "1.0",
        "source": "ENTERPRISE_AI_CIO_MULTI_STRATEGY_INTERPRETATION",
        "scope": "ALL_REGISTERED_STRATEGIES",
        "registered_strategy_count": len(strategies),
        "strategy_ids": registered_ids,
        "enterprise_totals": totals,
        "health_summary": dict(sorted(health.items())),
        "readiness_summary": dict(sorted(readiness.items())),
        "strategy_comparisons": {"leaders": leaders},
        "strategies": strategies,
        "commentary": _commentary(strategies, totals),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "read_only": True,
    }
    return document, sorted(set(warnings))
