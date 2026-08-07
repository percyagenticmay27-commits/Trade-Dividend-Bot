"""Read-only Dividend Quality scoring from the shared market-data snapshot.

Missing evidence contributes 0 to the component score and is disclosed explicitly.
The engine never contacts a provider, moves capital, or enables execution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

MODULE_NAME = "dividend_quality_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
AUTOMATIC_ACTIVATION_ALLOWED = False
REPORTING_ONLY = True

QUALITY_METRICS = (
    "return_on_equity",
    "profit_margin",
    "operating_margin",
    "free_cash_flow",
)


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


def _score_ratio(value: float | None, thresholds: tuple[tuple[float, float], ...]) -> float:
    if value is None:
        return 0.0
    for minimum, score in thresholds:
        if value >= minimum:
            return score
    return 0.0


def _records(snapshot: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(snapshot, Mapping):
        return []
    rows = snapshot.get("records")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def build_dividend_quality_report(
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

        roe = _ratio(_first(quote, "return_on_equity", "returnOnEquity", "roe"))
        profit_margin = _ratio(_first(quote, "profit_margins", "profitMargins", "profit_margin"))
        operating_margin = _ratio(_first(quote, "operating_margins", "operatingMargins", "operating_margin"))
        free_cash_flow = _first(quote, "free_cashflow", "freeCashflow", "free_cash_flow")

        metric_scores = {
            "return_on_equity": _score_ratio(roe, ((0.25, 100.0), (0.15, 85.0), (0.08, 70.0), (0.0, 50.0))),
            "profit_margin": _score_ratio(profit_margin, ((0.20, 100.0), (0.10, 85.0), (0.05, 70.0), (0.0, 50.0))),
            "operating_margin": _score_ratio(operating_margin, ((0.20, 100.0), (0.10, 85.0), (0.05, 70.0), (0.0, 50.0))),
            "free_cash_flow": 100.0 if free_cash_flow is not None and free_cash_flow > 0 else 0.0,
        }
        values = {
            "return_on_equity": roe,
            "profit_margin": profit_margin,
            "operating_margin": operating_margin,
            "free_cash_flow": free_cash_flow,
        }
        missing = [name for name, value in values.items() if value is None]
        score = round(sum(metric_scores.values()) / len(QUALITY_METRICS), 2)
        if missing:
            warnings.append(f"{symbol}: missing quality evidence defaults to 0: {', '.join(missing)}")

        entries.append({
            "symbol": symbol,
            "quality_score": score,
            "dividend_quality_score": score,
            "metric_values": values,
            "metric_scores": metric_scores,
            "missing_metrics": missing,
            "evidence_status": "AVAILABLE" if not missing else ("PARTIAL" if len(missing) < len(QUALITY_METRICS) else "NOT_REPORTED"),
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
