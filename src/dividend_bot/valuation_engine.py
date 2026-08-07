"""Read-only valuation scoring from the shared market-data snapshot."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

MODULE_NAME = "valuation_engine"
MODULE_VERSION = "1.1.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
PAPER_TRADE_MODE = True
REPORTING_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
AUTOMATIC_ACTIVATION_ALLOWED = False

COMPANY_VALUATION_METRICS = ("trailing_pe", "forward_pe", "price_to_book", "price_position_52w")
ETF_VALUATION_METRICS = ("price_position_52w", "dividend_yield", "expense_ratio", "price_to_book")


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


def _yield_score(value: float | None) -> float:
    value = _ratio(value)
    if value is None or value < 0:
        return 0.0
    if value >= 0.07:
        return 100.0
    if value >= 0.05:
        return 90.0
    if value >= 0.035:
        return 80.0
    if value >= 0.02:
        return 65.0
    if value > 0:
        return 45.0
    return 0.0


def _expense_score(value: float | None) -> float:
    value = _ratio(value)
    if value is None or value < 0:
        return 0.0
    if value <= 0.003:
        return 100.0
    if value <= 0.006:
        return 85.0
    if value <= 0.010:
        return 70.0
    if value <= 0.015:
        return 50.0
    return 30.0


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


def _is_fund(record: Mapping[str, Any], quote: Mapping[str, Any]) -> bool:
    quote_type = str(quote.get("quote_type") or record.get("quote_type") or "").upper()
    return quote_type in {"ETF", "MUTUALFUND", "MONEYMARKET"}


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
        price = _number(record.get("price"))
        low = _number(record.get("fifty_two_week_low"))
        high = _number(record.get("fifty_two_week_high"))
        price_position = _position(price, low, high)

        if _is_fund(record, quote):
            price_to_book = _first(quote, "price_to_book", "priceToBook")
            dividend_yield = _first(quote, "dividend_yield", "dividendYield", "trailing_annual_dividend_yield")
            expense_ratio = _first(quote, "annual_report_expense_ratio", "annualReportExpenseRatio")
            values = {
                "price_position_52w": price_position,
                "dividend_yield": _ratio(dividend_yield),
                "expense_ratio": _ratio(expense_ratio),
                "price_to_book": price_to_book,
            }
            scores = {
                "price_position_52w": _position_score(price_position),
                "dividend_yield": _yield_score(dividend_yield),
                "expense_ratio": _expense_score(expense_ratio),
                "price_to_book": _book_score(price_to_book),
            }
            metrics = ETF_VALUATION_METRICS
            model = "ETF_INCOME_VALUATION"
        else:
            trailing_pe = _first(quote, "trailing_pe", "trailingPE")
            forward_pe = _first(quote, "forward_pe", "forwardPE")
            price_to_book = _first(quote, "price_to_book", "priceToBook")
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
            metrics = COMPANY_VALUATION_METRICS
            model = "COMPANY_VALUATION"

        missing = [name for name, value in values.items() if value is None]
        valuation_score = round(sum(scores.values()) / len(metrics), 2)
        if missing:
            warnings.append(f"{symbol}: missing valuation evidence defaults to 0: {', '.join(missing)}")
        entries.append({
            "symbol": symbol,
            "valuation_score": valuation_score,
            "evidence_model": model,
            "metric_values": values,
            "metric_scores": scores,
            "missing_metrics": missing,
            "evidence_status": "AVAILABLE" if not missing else ("PARTIAL" if len(missing) < len(metrics) else "NOT_REPORTED"),
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
