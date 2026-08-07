"""Read-only valuation scoring from the shared market-data snapshot."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

MODULE_NAME = "valuation_engine"
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

VALUATION_METRICS = ("trailing_pe", "forward_pe", "price_to_book", "price_position_52w")


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


def _pe_score(value: float | None) -> float:
    if value is None or value <= 0:
        return 0.0
    if value <= 12:
        return 100.0
    if value <= 18:
        return 85.0
    if value <= 25:
        return 70.0
    if value <= 35:
        return 50.0
    return 30.0


def _book_score(value: float | None) -> float:
    if value is None or value <= 0:
        return 0.0
    if value <= 1.5:
        return 100.0
    if value <= 3:
        return 80.0
    if value <= 5:
        return 60.0
    if value <= 8:
        return 40.0
    return 20.0


def _position(price: float | None, low: float | None, high: float | None) -> float | None:
    if price is None or low is None or high is None or high <= low:
        return None
    return min(1.0, max(0.0, (price - low) / (high - low)))


def _position_score(value: float | None) -> float:
    if value is None:
        return 0.0
    if value <= 0.35:
        return 100.0
    if value <= 0.50:
        return 80.0
    if value <= 0.70:
        return 60.0
    if value <= 0.85:
        return 40.0
    return 20.0


def _records(snapshot: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(snapshot, Mapping):
        return []
    rows = snapshot.get("records")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def build_valuation_report(
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
        trailing_pe = _first(quote, "trailing_pe", "trailingPE")
        forward_pe = _first(quote, "forward_pe", "forwardPE")
        price_to_book = _first(quote, "price_to_book", "priceToBook")
        price = _number(record.get("price"))
        low = _number(record.get("fifty_two_week_low"))
        high = _number(record.get("fifty_two_week_high"))
        price_position = _position(price, low, high)
        values = {
            "trailing_pe": trailing_pe,
            "forward_pe": forward_pe,
            "price_to_book": price_to_book,
            "price_position_52w": price_position,
        }
        scores = {
            "trailing_pe": _pe_score(trailing_pe),
            "forward_pe": _pe_score(forward_pe),
            "price_to_book": _book_score(price_to_book),
            "price_position_52w": _position_score(price_position),
        }
        missing = [name for name, value in values.items() if value is None]
        valuation_score = round(sum(scores.values()) / len(VALUATION_METRICS), 2)
        if missing:
            warnings.append(f"{symbol}: missing valuation evidence defaults to 0: {', '.join(missing)}")
        entries.append({
            "symbol": symbol,
            "valuation_score": valuation_score,
            "metric_values": values,
            "metric_scores": scores,
            "missing_metrics": missing,
            "evidence_status": "AVAILABLE" if not missing else ("PARTIAL" if len(missing) < len(VALUATION_METRICS) else "NOT_REPORTED"),
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
