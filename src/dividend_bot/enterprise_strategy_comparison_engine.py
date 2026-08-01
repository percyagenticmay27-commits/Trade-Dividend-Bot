"""Read-only comparison of AI CIO multi-strategy interpretation evidence.

The engine compares only values already published by the Enterprise AI CIO
strategy interpretation layer. It does not import strategy production code,
change allocations, move capital, place orders, or create recommendations.
Missing evidence remains explicit and never becomes an invented zero.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True

_COMPARISON_METRICS = (
    "allocated_capital",
    "portfolio_value",
    "realized_gain",
    "unrealized_gain",
    "income",
    "watchlist_count",
    "position_count",
    "opportunity_quality",
    "win_rate_percent",
)

_STATUS_FIELDS = (
    "runtime_status",
    "health_status",
    "readiness",
    "evidence_status",
)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _strategy_rows(
    interpretation: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    raw = interpretation.get("strategies")
    if not isinstance(raw, list):
        return [], ["AI CIO interpretation does not contain a strategies list."]

    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            warnings.append("Malformed interpreted strategy row ignored.")
            continue
        strategy_id = str(item.get("strategy_id") or "").strip()
        if not strategy_id:
            warnings.append("Interpreted strategy row without strategy_id ignored.")
            continue
        if strategy_id in seen:
            warnings.append(f"Duplicate interpreted strategy ignored: {strategy_id}")
            continue
        seen.add(strategy_id)
        rows.append(dict(item))
    rows.sort(key=lambda item: str(item["strategy_id"]))
    return rows, warnings


def _metric_comparison(
    strategies: Sequence[Mapping[str, Any]],
    metric: str,
) -> dict[str, Any]:
    contributors: list[dict[str, Any]] = []
    missing: list[str] = []

    for strategy in strategies:
        strategy_id = str(strategy["strategy_id"])
        value = _number(strategy.get(metric))
        if value is None:
            missing.append(strategy_id)
            continue
        contributors.append(
            {
                "strategy_id": strategy_id,
                "display_name": str(
                    strategy.get("display_name") or strategy_id
                ),
                "value": round(value, 2),
            }
        )

    contributors.sort(key=lambda item: (-item["value"], item["strategy_id"]))
    enterprise_total = round(sum(item["value"] for item in contributors), 2)
    leader = contributors[0] if contributors else None

    for item in contributors:
        item["difference_from_leader"] = (
            round(leader["value"] - item["value"], 2) if leader else None
        )
        item["share_of_reported_total_percent"] = (
            round((item["value"] / enterprise_total) * 100.0, 2)
            if enterprise_total != 0
            else None
        )

    return {
        "metric": metric,
        "enterprise_total": enterprise_total,
        "reported_strategy_count": len(contributors),
        "registered_strategy_count": len(strategies),
        "complete": len(contributors) == len(strategies),
        "leader": dict(leader) if leader else None,
        "contributors": contributors,
        "missing_strategy_ids": sorted(missing),
        "comparison_basis": "REPORTED_EVIDENCE_ONLY",
    }


def _status_comparison(
    strategies: Sequence[Mapping[str, Any]],
    field: str,
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    rows: list[dict[str, str]] = []
    for strategy in strategies:
        value = str(strategy.get(field) or "UNKNOWN").upper()
        counts[value] = counts.get(value, 0) + 1
        rows.append(
            {
                "strategy_id": str(strategy["strategy_id"]),
                "display_name": str(
                    strategy.get("display_name") or strategy["strategy_id"]
                ),
                "value": value,
            }
        )
    return {
        "field": field,
        "counts": dict(sorted(counts.items())),
        "strategies": rows,
    }


def _pairwise_differences(
    strategies: Sequence[Mapping[str, Any]],
    metric: str,
) -> list[dict[str, Any]]:
    reported = [
        (str(item["strategy_id"]), _number(item.get(metric)))
        for item in strategies
    ]
    reported = [(strategy_id, value) for strategy_id, value in reported if value is not None]
    result: list[dict[str, Any]] = []
    for index, (left_id, left_value) in enumerate(reported):
        for right_id, right_value in reported[index + 1 :]:
            result.append(
                {
                    "metric": metric,
                    "left_strategy_id": left_id,
                    "right_strategy_id": right_id,
                    "difference": round(left_value - right_value, 2),
                    "absolute_difference": round(abs(left_value - right_value), 2),
                }
            )
    return result


def build_enterprise_strategy_comparison(
    *,
    interpretation: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Build deterministic enterprise comparisons from interpreted evidence."""
    strategies, warnings = _strategy_rows(interpretation)

    metric_comparisons = {
        metric: _metric_comparison(strategies, metric)
        for metric in _COMPARISON_METRICS
    }
    status_comparisons = {
        field: _status_comparison(strategies, field)
        for field in _STATUS_FIELDS
    }
    pairwise = {
        metric: _pairwise_differences(strategies, metric)
        for metric in _COMPARISON_METRICS
    }

    incomplete_metrics = sorted(
        metric
        for metric, comparison in metric_comparisons.items()
        if not comparison["complete"]
    )
    if incomplete_metrics:
        warnings.append(
            "Comparison evidence is incomplete for: "
            + ", ".join(incomplete_metrics)
        )

    document = {
        "schema_version": "1.0",
        "source": "ENTERPRISE_AI_CIO_STRATEGY_COMPARISON",
        "scope": "ALL_INTERPRETED_REGISTERED_STRATEGIES",
        "registered_strategy_count": len(strategies),
        "strategy_ids": [str(item["strategy_id"]) for item in strategies],
        "metric_comparisons": metric_comparisons,
        "status_comparisons": status_comparisons,
        "pairwise_differences": pairwise,
        "incomplete_metrics": incomplete_metrics,
        "interpretation_source": str(
            interpretation.get("source")
            or "ENTERPRISE_AI_CIO_MULTI_STRATEGY_INTERPRETATION"
        ),
        "comparison_policy": {
            "missing_evidence": "NOT_REPORTED",
            "ranking_basis": "REPORTED_EVIDENCE_ONLY",
            "recommendations_generated": False,
            "allocation_changes_generated": False,
        },
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "read_only": True,
    }
    return document, sorted(set(warnings))
