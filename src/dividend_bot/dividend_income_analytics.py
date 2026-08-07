"""Enrich DIVIDEND-001 holdings with read-only income evidence.

The builder consumes strategy-owned market/income evidence and attaches only
metrics that can be supported without fabrication. It never changes allocation,
state, capital, broker connectivity, or order execution.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


RESERVE_SYMBOLS = {"SGOV"}


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
        own_symbol = str(
            payload.get("symbol")
            or payload.get("ticker")
            or payload.get("candidate_id")
            or ""
        ).strip().upper()
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


def _yield_percent(record: Mapping[str, Any]) -> float | None:
    """Read only fields whose names explicitly declare percent semantics."""
    return _first_number(
        record,
        (
            "dividend_yield_percent",
            "yield_percent",
            "distribution_yield_percent",
            "trailing_yield_percent",
            "forward_yield_percent",
        ),
    )


def _annual_income(record: Mapping[str, Any], shares: float | None) -> float | None:
    explicit = _first_number(
        record,
        (
            "annual_income",
            "projected_annual_income",
            "annual_dividend_income",
        ),
    )
    if explicit is not None:
        return explicit

    annual_rate = _first_number(
        record,
        (
            "annual_dividend_rate",
            "dividend_rate_per_share",
            "annual_distribution_rate",
            "trailing_annual_dividend_rate",
        ),
    )
    if annual_rate is None or shares is None or shares < 0:
        return None
    return annual_rate * shares


def enrich_holdings_with_income_analytics(
    holdings: Sequence[Mapping[str, Any]],
    market_snapshot: Any = None,
    income_snapshot: Any = None,
) -> list[dict[str, Any]]:
    """Return enriched holding copies with authoritative income metrics only."""
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
                name = _first_text(
                    record,
                    (
                        "name",
                        "security_name",
                        "display_name",
                        "instrument_name",
                        "shortName",
                        "longName",
                    ),
                )
                if name:
                    item["name"] = name

            if not is_reserve:
                yield_percent = _yield_percent(record)
                if yield_percent is not None:
                    item["dividend_yield_percent"] = round(yield_percent, 4)

                shares = _number(item.get("shares"))
                annual_income = _annual_income(record, shares)
                if annual_income is not None:
                    item["annual_income"] = round(annual_income, 2)

                next_ex_date = _first_text(
                    record,
                    (
                        "next_ex_dividend_date",
                        "next_ex_date",
                        "ex_dividend_date",
                        "ex_date",
                    ),
                )
                if next_ex_date:
                    item["next_ex_dividend_date"] = next_ex_date

                payment_frequency = _first_text(
                    record,
                    (
                        "payment_frequency",
                        "dividend_frequency",
                        "distribution_frequency",
                    ),
                )
                if payment_frequency:
                    item["payment_frequency"] = payment_frequency

                if any(
                    key in item
                    for key in (
                        "dividend_yield_percent",
                        "annual_income",
                        "next_ex_dividend_date",
                        "payment_frequency",
                    )
                ):
                    item["income_analytics_source"] = source

        enriched.append(item)
    return enriched


def total_projected_annual_income(holdings: Sequence[Mapping[str, Any]]) -> float | None:
    reported = [
        value
        for item in holdings
        for value in [_number(item.get("annual_income"))]
        if value is not None
    ]
    return round(sum(reported), 2) if reported else None
