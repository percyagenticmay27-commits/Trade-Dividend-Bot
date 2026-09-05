"""Read-only market refresh for Dividend suitability evidence."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from math import isfinite
from statistics import mean
from typing import Any, Mapping


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _history(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for raw in payload.get("rows", []) if isinstance(payload.get("rows"), list) else []:
        if not isinstance(raw, Mapping):
            continue
        try:
            observed = date.fromisoformat(str(raw.get("date") or "")[:10])
        except ValueError:
            continue
        close = _number(raw.get("adj_close")) or _number(raw.get("close"))
        volume = _number(raw.get("volume"))
        if close and close > 0:
            rows.append({"date": observed, "close": close, "volume": volume})
    return sorted(rows, key=lambda row: row["date"])


def _completed_month_income(rows: list[dict[str, Any]], dividends: Mapping[str, Any]) -> dict[str, Any]:
    """Measure actual distributions in the most recently completed calendar month.

    The denominator is the last available vehicle close in that completed month.
    This deliberately does not annualize distributions or divide an annual yield by 12.
    """
    if not rows:
        return {
            "observed_income_monthly_percent": None,
            "observed_income_month": None,
            "observed_month_distribution_per_share": None,
            "observed_month_end_price": None,
        }
    latest = rows[-1]["date"]
    current_month_start = latest.replace(day=1)
    completed_month_end = current_month_start - timedelta(days=1)
    completed_month_start = completed_month_end.replace(day=1)
    month_rows = [row for row in rows if completed_month_start <= row["date"] <= completed_month_end]
    month_end_price = month_rows[-1]["close"] if month_rows else None

    payments = dividends.get("payments") if isinstance(dividends, Mapping) else None
    total = 0.0
    payment_count = 0
    if isinstance(payments, list):
        for payment in payments:
            if not isinstance(payment, Mapping):
                continue
            try:
                paid = date.fromisoformat(str(payment.get("date") or "")[:10])
            except ValueError:
                continue
            amount = _number(payment.get("amount"))
            if completed_month_start <= paid <= completed_month_end and amount is not None and amount >= 0:
                total += amount
                payment_count += 1

    observed = (total / month_end_price * 100) if month_end_price and payment_count else None
    return {
        "observed_income_monthly_percent": round(observed, 6) if observed is not None else None,
        "observed_income_month": completed_month_start.strftime("%Y-%m"),
        "observed_month_distribution_per_share": round(total, 8) if payment_count else None,
        "observed_month_distribution_payment_count": payment_count,
        "observed_month_end_price": round(month_end_price, 6) if month_end_price is not None else None,
        "monthly_income_method": "COMPLETED_CALENDAR_MONTH_DISTRIBUTIONS_DIVIDED_BY_MONTH_END_VEHICLE_PRICE",
    }


def build_vehicle_evidence(symbol: str, mapping_type: str, profile: Mapping[str, Any],
                           history: Mapping[str, Any], quote: Mapping[str, Any],
                           dividends: Mapping[str, Any] | None = None) -> dict[str, Any]:
    rows = _history(history)
    first, latest = (rows[0], rows[-1]) if rows else (None, None)
    total_return = (
        round(((latest["close"] / first["close"]) - 1) * 100, 6)
        if first and latest and len(rows) >= 20 and (latest["date"] - first["date"]).days >= 300 else None
    )
    recent = [row["close"] * row["volume"] for row in rows[-20:]
              if row.get("volume") is not None and row["volume"] > 0]
    dollar_volume = round(mean(recent), 2) if len(recent) >= 5 else None
    stale = bool(history.get("is_stale") or quote.get("is_stale") or (dividends or {}).get("is_stale"))
    output = {
        "income_symbol": symbol,
        "reviewed": True,
        "evidence_as_of": latest["date"].isoformat() if latest else profile.get("reviewed_at"),
        "latest_dollar_volume": dollar_volume,
        "total_return_1y_percent": total_return,
        "market_history_source": history.get("data_source") or history.get("provider"),
        "is_stale": stale,
        "freshness_status": "STALE_OR_UNAVAILABLE" if stale else "FRESH",
        "sources": list(profile.get("sources") or []),
    }
    if mapping_type == "INCOME_ETF":
        inception = date.fromisoformat(str(profile["fund_inception_date"]))
        as_of = latest["date"] if latest else date.fromisoformat(str(profile["reviewed_at"]))
        price = _number(quote.get("price"))
        output.update({
            "expense_ratio_percent": profile.get("expense_ratio_percent"),
            "latest_distribution_roc_percent": profile.get("latest_distribution_roc_percent"),
            "fund_inception_date": inception.isoformat(),
            "fund_age_days": max(0, (as_of - inception).days),
            "vehicle_status": "ACTIVE" if price is not None and price > 0 else None,
            "distribution_evidence_source": (dividends or {}).get("data_source") or (dividends or {}).get("provider"),
        })
        output.update(_completed_month_income(rows, dividends or {}))
    else:
        dividend_rate = _number(quote.get("dividend_rate"))
        price = _number(quote.get("price"))
        raw_yield = _number(quote.get("trailing_annual_dividend_yield"))
        if raw_yield is None:
            raw_yield = _number(quote.get("dividend_yield"))
        if dividend_rate is not None and price is not None and dividend_rate >= 0 and price > 0:
            yield_percent = dividend_rate / price * 100
        elif raw_yield is not None:
            # Reporting/suitability context only. The Dividend Gateway never uses
            # this annual yield for its completed-month income qualification.
            yield_percent = raw_yield if raw_yield > 0.20 else raw_yield * 100
        else:
            yield_percent = None
        if yield_percent is not None and not 0 <= yield_percent <= 25:
            yield_percent = None
        output.update({
            "forward_dividend_yield_percent": (
                round(yield_percent, 6) if yield_percent is not None else None
            ),
            "dividend_cut_last_12m": profile.get("dividend_cut_last_12m"),
        })
    return output


def collect_suitability_evidence(mapping_report: Mapping[str, Any], profiles: Mapping[str, Any],
                                 service: Any) -> dict[str, Any]:
    profile_rows = profiles.get("profiles")
    if not isinstance(profile_rows, list):
        raise ValueError("suitability profiles must be a list")
    indexed = {str(row.get("income_symbol") or "").upper(): row for row in profile_rows
               if isinstance(row, Mapping)}
    vehicles, warnings = [], []
    for mapping in mapping_report.get("candidates", []):
        symbol = str(mapping.get("income_symbol") or "").upper()
        if not symbol:
            # RESEARCH_REQUIRED mappings intentionally have no approved vehicle.
            continue
        profile = indexed.get(symbol)
        if not profile or profile.get("reviewed") is not True:
            warnings.append(f"Reviewed suitability profile unavailable for {symbol}")
            continue
        try:
            history = service.get_history(symbol, period="1y", interval="1d")
            quote = service.get_quote(symbol)
            mapping_type = str(mapping.get("mapping_type") or "")
            dividends = service.get_dividends(symbol, period="1y") if mapping_type == "INCOME_ETF" else None
            vehicles.append(build_vehicle_evidence(
                symbol, mapping_type, profile, history, quote, dividends,
            ))
        except Exception as exc:
            warnings.append(f"Suitability market evidence unavailable for {symbol}: {exc}")
    return {
        # Keep the established suitability-catalog contract at schema 1.0.
        # The added monthly-income fields are backward-compatible extensions.
        "schema_version": "1.0",
        "strategy_id": "DIVIDEND-001",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "vehicles": vehicles,
        "warnings": warnings,
        "read_only_market_data": True,
        "inference_allowed": False,
    }
