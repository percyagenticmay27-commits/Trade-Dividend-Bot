"""Normalize universal and conditional Enterprise strategy KPI fields.

The contract distinguishes a legitimate numeric zero from evidence that is not
applicable, not reported, or still pending. It is reporting-only and does not
change strategy calculations, allocations, orders, or broker behavior.
"""
from __future__ import annotations

from typing import Any, Mapping

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True

VALID_METRIC_STATUSES = frozenset(
    {"REPORTED", "NOT_APPLICABLE", "NOT_REPORTED", "PENDING"}
)

UNIVERSAL_METRICS = frozenset(
    {
        "allocated_capital",
        "portfolio_value",
        "performance_percent",
        "realized_gain",
        "unrealized_gain",
        "win_rate_percent",
        "opportunity_quality",
        "watchlist_count",
        "position_count",
    }
)

CONDITIONAL_METRICS = frozenset(
    {
        "income",
        "yield_percent",
        "capital_appreciation",
    }
)


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_metric(
    value: Any,
    *,
    default_status: str = "NOT_REPORTED",
    unit: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Return one canonical metric envelope.

    Accepted input forms are a raw numeric value or a mapping containing value,
    status, unit, and reason. A raw zero remains a reported zero.
    """
    if isinstance(value, Mapping):
        raw_value = value.get("value")
        status = str(value.get("status") or default_status).upper()
        resolved_unit = value.get("unit", unit)
        resolved_reason = value.get("reason", reason)
    else:
        raw_value = value
        status = "REPORTED" if _number(value) is not None else default_status.upper()
        resolved_unit = unit
        resolved_reason = reason

    if status not in VALID_METRIC_STATUSES:
        raise ValueError(f"Unsupported Enterprise KPI metric status: {status}")

    numeric = _number(raw_value)
    if status == "REPORTED" and numeric is None:
        raise ValueError("REPORTED metric status requires a numeric value")
    if status != "REPORTED":
        numeric = None

    return {
        "value": numeric,
        "status": status,
        "unit": resolved_unit,
        "reason": resolved_reason,
    }


def normalize_strategy_kpi_contract(
    row: Mapping[str, Any],
    *,
    applicability: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Normalize Enterprise KPI v1 fields while preserving strategy extensions."""
    normalized = dict(row)
    applicability_map = {
        str(key): str(value).upper()
        for key, value in (applicability or {}).items()
    }

    metrics: dict[str, dict[str, Any]] = {}
    for metric in sorted(UNIVERSAL_METRICS | CONDITIONAL_METRICS):
        default_status = applicability_map.get(metric, "NOT_REPORTED")
        metrics[metric] = normalize_metric(
            row.get(metric),
            default_status=default_status,
        )

    normalized["enterprise_kpi_contract_version"] = "1.0"
    normalized["metrics"] = metrics
    normalized["paper_trade_mode"] = True
    normalized["live_trading_enabled"] = False
    normalized["broker_execution_enabled"] = False
    normalized["capital_movement_enabled"] = False
    normalized["reporting_only"] = True
    normalized["read_only"] = True
    return normalized
