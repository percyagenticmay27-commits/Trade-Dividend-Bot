"""Enrich DIVIDEND-001 holdings with read-only income evidence.

The builder consumes strategy-owned market/income evidence and attaches only
metrics that can be supported without fabrication. It never changes allocation,
state, capital, broker connectivity, or order execution.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

RESERVE_SYMBOLS = {"SGOV"}
YEARLY_DISTRIBUTION_YIELD_METHOD = "TRAILING_365D_DISTRIBUTIONS_DIVIDED_BY_CURRENT_HOLDING_PRICE"
ANNUAL_INCOME_METHOD = "TRAILING_365D_DISTRIBUTIONS_PER_SHARE_TIMES_CURRENT_SHARES"


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


def _first_text(row: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _find_record(payload: Any, symbol: str) -> Mapping[str, Any] | None:
    if isinstance(payload, Mapping):
        direct = payload.get(symbol)
        if isinstance(direct, Mapping):
            return direct
        own_symbol = str(payload.get("symbol") or payload.get("ticker") or payload.get("candidate_id") or "").strip().upper()
        if own_symbol == symbol:
            return payload
        for value in payload.values():
            found = _find_record(value, symbol)
            if found is not None:
                return found
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        for value in payload:
            found = _find_record(value, symbol)
            if found is not None:
                return found
    return None


def _nested_mapping(record: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = record.get(key)
    return value if isinstance(value, Mapping) else {}


def _parse_date(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _history_anchor(record: Mapping[str, Any]) -> datetime:
    history = _nested_mapping(record, "history")
    rows = history.get("rows")
    if isinstance(rows, list):
        dated = [parsed for item in rows if isinstance(item, Mapping) for parsed in [_parse_date(item.get("date"))] if parsed is not None]
        if dated:
            return max(dated)
    return datetime.now(timezone.utc)


def _observed_dividend_payments(record: Mapping[str, Any]) -> list[tuple[datetime, float]]:
    dividends = _nested_mapping(record, "dividends")
    rows = dividends.get("payments") or dividends.get("dividends") or dividends.get("history") or []
    result: list[tuple[datetime, float]] = []
    if not isinstance(rows, list):
        return result
    for item in rows:
        if not isinstance(item, Mapping):
            continue
        date = _parse_date(item.get("date"))
        amount = _number(item.get("amount", item.get("dividend", item.get("value"))))
        if date is not None and amount is not None and amount > 0:
            result.append((date, amount))
    return result


def _trailing_12m_distribution_audit(record: Mapping[str, Any]) -> dict[str, Any]:
    anchor = _history_anchor(record)
    start = anchor - timedelta(days=365)
    observed = [(date, amount) for date, amount in _observed_dividend_payments(record) if start < date <= anchor]
    rate = round(sum(amount for _, amount in observed), 6) if observed else None
    return {
        "trailing_12m_distribution_rate": rate,
        "trailing_12m_payment_count": len(observed),
        "trailing_12m_window_start": start.date().isoformat(),
        "trailing_12m_window_end": anchor.date().isoformat(),
        "trailing_12m_first_payment_date": min((date for date, _ in observed), default=None),
        "trailing_12m_last_payment_date": max((date for date, _ in observed), default=None),
    }


def _observed_frequency(payment_count: int) -> str | None:
    if payment_count <= 0:
        return None
    if payment_count >= 40:
        return "WEEKLY_OBSERVED"
    if payment_count >= 10:
        return "MONTHLY_OBSERVED"
    if payment_count >= 3:
        return "QUARTERLY_OBSERVED"
    if payment_count == 2:
        return "SEMIANNUAL_OBSERVED"
    return "ANNUAL_OBSERVED"


def _explicit_yield_percent(record: Mapping[str, Any]) -> float | None:
    return _first_number(record, (
        "yearly_distribution_yield_percent", "dividend_yield_percent", "yield_percent",
        "distribution_yield_percent", "trailing_yield_percent", "forward_yield_percent",
    ))


def _record_price(record: Mapping[str, Any]) -> float | None:
    price = _first_number(record, ("price", "market_price", "current_price"))
    if price is not None and price > 0:
        return price
    quote = _nested_mapping(record, "quote")
    price = _first_number(quote, ("price", "regular_market_price", "current_price"))
    return price if price is not None and price > 0 else None


def _yield_price(holding: Mapping[str, Any], record: Mapping[str, Any]) -> tuple[float | None, str | None]:
    """Prefer the same current holding price displayed on the dashboard.

    This removes the prior ambiguity where yield could use a stale snapshot quote
    while the Holdings table displayed a newer paper-state price.
    """
    holding_price = _number(holding.get("price"))
    if holding_price is not None and holding_price > 0:
        return holding_price, "HOLDING_CURRENT_PRICE"
    record_price = _record_price(record)
    if record_price is not None:
        return record_price, "MARKET_SNAPSHOT_PRICE_FALLBACK"
    return None, None


def _derived_yield_percent(trailing_rate: float | None, price: float | None) -> float | None:
    if trailing_rate is None or price is None or price <= 0:
        return None
    return round((trailing_rate / price) * 100.0, 4)


def _annual_income(record: Mapping[str, Any], shares: float | None, trailing_rate: float | None) -> tuple[float | None, str | None]:
    explicit = _first_number(record, ("annual_income", "projected_annual_income", "annual_dividend_income"))
    if explicit is not None:
        return explicit, "EXPLICIT_ANNUAL_INCOME"
    annual_rate = _first_number(record, ("annual_dividend_rate", "dividend_rate_per_share", "annual_distribution_rate", "trailing_annual_dividend_rate"))
    method = "EXPLICIT_ANNUAL_DISTRIBUTION_RATE_TIMES_CURRENT_SHARES"
    if annual_rate is None:
        annual_rate = trailing_rate
        method = ANNUAL_INCOME_METHOD
    if annual_rate is None or shares is None or shares < 0:
        return None, None
    return annual_rate * shares, method


def _security_name(record: Mapping[str, Any]) -> str | None:
    name = _first_text(record, ("name", "security_name", "display_name", "instrument_name", "short_name", "long_name", "shortName", "longName"))
    if name:
        return name
    quote = _nested_mapping(record, "quote")
    return _first_text(quote, ("name", "security_name", "display_name", "instrument_name", "short_name", "long_name", "shortName", "longName"))


def _next_ex_date(record: Mapping[str, Any]) -> str | None:
    value = _first_text(record, ("next_ex_dividend_date", "next_ex_date", "ex_dividend_date", "ex_date"))
    if value:
        return value
    quote = _nested_mapping(record, "quote")
    return _first_text(quote, ("next_ex_dividend_date", "next_ex_date", "ex_dividend_date", "ex_date"))


def _estimated_next_ex_date(record: Mapping[str, Any]) -> tuple[str | None, str | None]:
    payments = sorted(date for date, _ in _observed_dividend_payments(record))
    if len(payments) < 2:
        return None, None
    intervals = sorted(
        (payments[index] - payments[index - 1]).days
        for index in range(1, len(payments))
        if (payments[index] - payments[index - 1]).days > 0
    )
    if not intervals:
        return None, None
    cadence_days = intervals[len(intervals) // 2]
    if cadence_days < 5 or cadence_days > 100:
        return None, None
    anchor_date = _history_anchor(record)
    estimated = payments[-1] + timedelta(days=cadence_days)
    while estimated <= anchor_date:
        estimated += timedelta(days=cadence_days)
    return estimated.date().isoformat(), f"OBSERVED_MEDIAN_CADENCE_{cadence_days}_DAYS"


def enrich_holdings_with_income_analytics(
    holdings: Sequence[Mapping[str, Any]],
    market_snapshot: Any = None,
    income_snapshot: Any = None,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for raw in holdings:
        item = dict(raw)
        symbol = str(item.get("symbol") or "").strip().upper()
        sleeve = str(item.get("sleeve") or "").strip().upper()
        status = str(item.get("position_status") or item.get("status") or "").strip().upper()
        is_reserve = symbol in RESERVE_SYMBOLS or sleeve in {"RESERVE", "CASH"} or status in {"PARKED", "RESERVE", "CASH"}

        record = None
        source = None
        if symbol and income_snapshot is not None:
            record = _find_record(income_snapshot, symbol)
            if record is not None:
                source = "income_snapshot"
        if record is None and symbol and market_snapshot is not None:
            record = _find_record(market_snapshot, symbol)
            if record is not None:
                source = "market_data_snapshot.json"

        if record is not None:
            if not item.get("name"):
                name = _security_name(record)
                if name:
                    item["name"] = name

            if not is_reserve:
                audit = _trailing_12m_distribution_audit(record)
                trailing_rate = audit["trailing_12m_distribution_rate"]
                payment_count = int(audit["trailing_12m_payment_count"] or 0)
                price, price_source = _yield_price(item, record)

                yield_percent = _derived_yield_percent(trailing_rate, price)
                yield_source = None
                yield_method = None
                if yield_percent is not None:
                    yield_source = "TRAILING_12M_PAYMENT_HISTORY"
                    yield_method = YEARLY_DISTRIBUTION_YIELD_METHOD
                else:
                    yield_percent = _explicit_yield_percent(record)
                    if yield_percent is not None:
                        yield_source = "EXPLICIT_PERCENT_FIELD"
                        yield_method = "EXPLICIT_PERCENT_FIELD"
                if yield_percent is not None:
                    item["dividend_yield_percent"] = round(yield_percent, 4)
                    item["yearly_distribution_yield_percent"] = round(yield_percent, 4)

                shares = _number(item.get("shares"))
                annual_income, annual_income_method = _annual_income(record, shares, trailing_rate)
                if annual_income is not None:
                    item["annual_income"] = round(annual_income, 2)

                next_ex_date = _next_ex_date(record)
                if next_ex_date:
                    item["next_ex_dividend_date"] = next_ex_date
                    item["next_ex_dividend_date_status"] = "AUTHORITATIVE_REPORTED"
                else:
                    estimated_ex_date, estimate_method = _estimated_next_ex_date(record)
                    if estimated_ex_date:
                        item["estimated_next_ex_dividend_date"] = estimated_ex_date
                        item["next_ex_dividend_date_status"] = "ESTIMATED_FROM_OBSERVED_CADENCE"
                        item["next_ex_dividend_date_method"] = estimate_method

                payment_frequency = _first_text(record, ("payment_frequency", "dividend_frequency", "distribution_frequency"))
                if not payment_frequency:
                    payment_frequency = _observed_frequency(payment_count)
                if payment_frequency:
                    item["payment_frequency"] = payment_frequency

                if any(key in item for key in ("dividend_yield_percent", "yearly_distribution_yield_percent", "annual_income", "next_ex_dividend_date", "estimated_next_ex_dividend_date", "payment_frequency")):
                    item["income_analytics_source"] = source

                if trailing_rate is not None:
                    item["trailing_12m_distribution_rate"] = trailing_rate
                    item["trailing_12m_payment_count"] = payment_count
                    item["trailing_12m_window_start"] = audit["trailing_12m_window_start"]
                    item["trailing_12m_window_end"] = audit["trailing_12m_window_end"]
                    first_date = audit["trailing_12m_first_payment_date"]
                    last_date = audit["trailing_12m_last_payment_date"]
                    if first_date is not None:
                        item["trailing_12m_first_payment_date"] = first_date.date().isoformat()
                    if last_date is not None:
                        item["trailing_12m_last_payment_date"] = last_date.date().isoformat()
                if price is not None:
                    item["yearly_distribution_yield_price"] = round(price, 6)
                    item["yearly_distribution_yield_price_source"] = price_source
                    item["yearly_distribution_yield_price_as_of"] = audit["trailing_12m_window_end"]
                if shares is not None:
                    item["annual_income_share_count"] = round(shares, 10)
                if yield_source:
                    item["dividend_yield_source"] = yield_source
                if yield_method:
                    item["yearly_distribution_yield_method"] = yield_method
                if annual_income_method:
                    item["annual_income_method"] = annual_income_method

        enriched.append(item)
    return enriched


def total_projected_annual_income(holdings: Sequence[Mapping[str, Any]]) -> float | None:
    reported = [value for item in holdings for value in [_number(item.get("annual_income"))] if value is not None]
    return round(sum(reported), 2) if reported else None
