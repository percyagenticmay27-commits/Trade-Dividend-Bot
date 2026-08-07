"""Read-only Dividend Growth scoring from the shared market-data snapshot."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

MODULE_NAME = "dividend_growth_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
PAPER_TRADE_MODE = True
REPORTING_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
AUTOMATIC_ACTIVATION_ALLOWED = False

GROWTH_METRICS = ("revenue_growth", "earnings_growth", "quarterly_earnings_growth", "dividend_growth")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first(mapping: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in mapping:
            value = _number(mapping.get(key))
            if value is not None:
                return value
    return None


def _ratio(value: float | None) -> float | None:
    if value is None:
        return None
    return value / 100.0 if abs(value) > 2.0 else value


def _score(value: float | None) -> float:
    if value is None:
        return 0.0
    if value >= 0.15:
        return 100.0
    if value >= 0.10:
        return 85.0
    if value >= 0.05:
        return 70.0
    if value > 0:
        return 55.0
    if value >= -0.05:
        return 30.0
    return 0.0


def _records(snapshot: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(snapshot, Mapping):
        return []
    rows = snapshot.get("records")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def build_dividend_growth_report(
    market_data_snapshot: Mapping[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    for record in _records(market_data_snapshot):
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        quote = record.get("quote") if isinstance(record.get("quote"), Mapping) else {}
        values = {
            "revenue_growth": _ratio(_first(quote, "revenue_growth", "revenueGrowth")),
            "earnings_growth": _ratio(_first(quote, "earnings_growth", "earningsGrowth")),
            "quarterly_earnings_growth": _ratio(_first(quote, "earnings_quarterly_growth", "earningsQuarterlyGrowth")),
            "dividend_growth": _ratio(_first(quote, "dividend_growth", "dividendGrowth", "dividend_growth_rate")),
        }
        scores = {name: _score(value) for name, value in values.items()}
        missing = [name for name, value in values.items() if value is None]
        growth_score = round(sum(scores.values()) / len(GROWTH_METRICS), 2)
        if missing:
            warnings.append(f"{symbol}: missing growth evidence defaults to 0: {', '.join(missing)}")
        entries.append({
            "symbol": symbol,
            "growth_score": growth_score,
            "dividend_growth_score": growth_score,
            "metric_values": values,
            "metric_scores": scores,
            "missing_metrics": missing,
            "evidence_status": "AVAILABLE" if not missing else ("PARTIAL" if len(missing) < len(GROWTH_METRICS) else "NOT_REPORTED"),
        })
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "generated_at_utc": _now(),
        "paper_trade_mode": True,
        "reporting_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "order_placement_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
        "entries": entries,
        "entry_count": len(entries),
        "missing_evidence_policy": "MISSING_EVIDENCE_EQUALS_ZERO",
        "warnings": warnings,
        "errors": [],
    }
