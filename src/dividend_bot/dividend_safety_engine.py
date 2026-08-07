"""Read-only Dividend Safety scoring from the shared market-data snapshot."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

MODULE_NAME = "dividend_safety_engine"
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

COMPANY_SAFETY_METRICS = ("payout_ratio", "debt_to_equity", "current_ratio", "dividend_history")
ETF_SAFETY_METRICS = ("beta", "expense_ratio", "total_assets", "dividend_history")


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


def _payout_score(value: float | None) -> float:
    if value is None or value < 0:
        return 0.0
    if value <= 0.60:
        return 100.0
    if value <= 0.75:
        return 80.0
    if value <= 0.90:
        return 60.0
    if value <= 1.00:
        return 40.0
    return 10.0


def _debt_score(value: float | None) -> float:
    if value is None or value < 0:
        return 0.0
    normalized = value / 100.0 if value > 5.0 else value
    if normalized <= 0.5:
        return 100.0
    if normalized <= 1.0:
        return 80.0
    if normalized <= 2.0:
        return 60.0
    if normalized <= 3.0:
        return 40.0
    return 20.0


def _current_ratio_score(value: float | None) -> float:
    if value is None or value <= 0:
        return 0.0
    if value >= 2.0:
        return 100.0
    if value >= 1.5:
        return 85.0
    if value >= 1.0:
        return 65.0
    return 40.0


def _history_score(count: int | None) -> float:
    if count is None:
        return 0.0
    if count >= 20:
        return 100.0
    if count >= 12:
        return 80.0
    if count >= 4:
        return 60.0
    if count > 0:
        return 40.0
    return 0.0


def _beta_score(value: float | None) -> float:
    if value is None or value < 0:
        return 0.0
    if value <= 0.6:
        return 100.0
    if value <= 0.9:
        return 85.0
    if value <= 1.1:
        return 70.0
    if value <= 1.4:
        return 50.0
    return 25.0


def _expense_score(value: float | None) -> float:
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


def _assets_score(value: float | None) -> float:
    if value is None or value <= 0:
        return 0.0
    if value >= 10_000_000_000:
        return 100.0
    if value >= 2_000_000_000:
        return 85.0
    if value >= 500_000_000:
        return 70.0
    if value >= 100_000_000:
        return 50.0
    return 30.0


def _records(snapshot: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(snapshot, Mapping):
        return []
    rows = snapshot.get("records")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _is_fund(record: Mapping[str, Any], quote: Mapping[str, Any]) -> bool:
    quote_type = str(quote.get("quote_type") or record.get("quote_type") or "").upper()
    return quote_type in {"ETF", "MUTUALFUND", "MONEYMARKET"}


def build_dividend_safety_report(
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
        raw_count = _number(record.get("dividend_record_count"))
        history_count = int(raw_count) if raw_count is not None and raw_count >= 0 else None

        if _is_fund(record, quote):
            beta = _first(quote, "beta_3y", "beta3Year", "beta")
            expense = _ratio(_first(quote, "annual_report_expense_ratio", "annualReportExpenseRatio"))
            total_assets = _first(quote, "total_assets", "totalAssets")
            values = {
                "beta": beta,
                "expense_ratio": expense,
                "total_assets": total_assets,
                "dividend_history": history_count,
            }
            scores = {
                "beta": _beta_score(beta),
                "expense_ratio": _expense_score(expense),
                "total_assets": _assets_score(total_assets),
                "dividend_history": _history_score(history_count),
            }
            metrics = ETF_SAFETY_METRICS
            model = "ETF_FUND_SAFETY"
        else:
            payout = _ratio(_first(quote, "payout_ratio", "payoutRatio"))
            debt = _first(quote, "debt_to_equity", "debtToEquity")
            current = _first(quote, "current_ratio", "currentRatio")
            values = {
                "payout_ratio": payout,
                "debt_to_equity": debt,
                "current_ratio": current,
                "dividend_history": history_count,
            }
            scores = {
                "payout_ratio": _payout_score(payout),
                "debt_to_equity": _debt_score(debt),
                "current_ratio": _current_ratio_score(current),
                "dividend_history": _history_score(history_count),
            }
            metrics = COMPANY_SAFETY_METRICS
            model = "COMPANY_DIVIDEND_SAFETY"

        missing = [name for name, value in values.items() if value is None]
        safety_score = round(sum(scores.values()) / len(metrics), 2)
        if missing:
            warnings.append(f"{symbol}: missing safety evidence defaults to 0: {', '.join(missing)}")
        entries.append({
            "symbol": symbol,
            "safety_score": safety_score,
            "dividend_safety_score": safety_score,
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
