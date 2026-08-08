"""Derive read-only DIVIDEND-001 position analytics from paper artifacts.

The builder reconstructs open paper cost basis and current-position purchase dates
from the Dividend Bot's own trade log and enriches currently reported holdings with
authoritative market snapshot metadata when available. It does not place orders,
move capital, or alter state.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

BUY_ACTIONS = {"PAPER_BUY_OPEN", "PAPER_BUY_FROM_SGOV"}
SELL_ACTIONS = {"PAPER_SELL_TO_SGOV", "PAPER_SELL_CLOSE", "PAPER_SELL"}
RESERVE_STATUSES = {"PARKED", "CASH", "RESERVE"}
DATE_KEYS = ("Date", "date", "Trade_Date", "trade_date", "Timestamp", "timestamp")


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _symbol(row: Mapping[str, Any]) -> str:
    return str(row.get("Ticker") or row.get("ticker") or row.get("symbol") or "").strip().upper()


def _trade_date(row: Mapping[str, Any]) -> str | None:
    for key in DATE_KEYS:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip() or None
    return None


def _open_lots(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Reconstruct aggregate open shares/cost and the current position open date.

    ``purchase_date`` is the first buy date belonging to the currently open
    position. A complete exit removes the lot, so a later re-entry receives a new
    purchase date rather than inheriting an older historical purchase.
    """
    lots: dict[str, dict[str, Any]] = {}
    for row in rows:
        symbol = _symbol(row)
        action = str(row.get("Action") or row.get("action") or "").strip().upper()
        shares = _number(row.get("Shares") if "Shares" in row else row.get("shares"))
        price = _number(row.get("Price") if "Price" in row else row.get("price"))
        paper_value = _number(row.get("Paper_Value") if "Paper_Value" in row else row.get("paper_value"))
        if not symbol or shares is None or shares <= 0:
            continue
        if action in BUY_ACTIONS:
            cost = paper_value if paper_value is not None and paper_value >= 0 else (shares * price if price is not None else None)
            if cost is None:
                continue
            lot = lots.get(symbol)
            if lot is None:
                lot = {
                    "shares": 0.0,
                    "cost_basis": 0.0,
                    "purchase_date": _trade_date(row),
                }
                lots[symbol] = lot
            lot["shares"] += shares
            lot["cost_basis"] += cost
        elif action in SELL_ACTIONS:
            lot = lots.get(symbol)
            if not lot or lot["shares"] <= 0:
                continue
            sold = min(shares, lot["shares"])
            avg_cost = lot["cost_basis"] / lot["shares"] if lot["shares"] else 0.0
            lot["shares"] -= sold
            lot["cost_basis"] -= sold * avg_cost
            if lot["shares"] <= 1e-9:
                lots.pop(symbol, None)
    return lots


def _find_market_record(payload: Any, symbol: str) -> Mapping[str, Any] | None:
    if isinstance(payload, Mapping):
        direct = payload.get(symbol)
        if isinstance(direct, Mapping):
            return direct
        own_symbol = str(payload.get("symbol") or payload.get("ticker") or payload.get("candidate_id") or "").strip().upper()
        if own_symbol == symbol:
            return payload
        for value in payload.values():
            found = _find_market_record(value, symbol)
            if found is not None:
                return found
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        for value in payload:
            found = _find_market_record(value, symbol)
            if found is not None:
                return found
    return None


def _first_text(row: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _first_number(row: Mapping[str, Any], keys: Sequence[str]) -> float | None:
    for key in keys:
        value = _number(row.get(key))
        if value is not None:
            return value
    return None


def _daily_change_percent(record: Mapping[str, Any]) -> float | None:
    direct = _first_number(record, (
        "daily_change_percent", "daily_change_pct", "day_change_percent", "day_change_pct",
        "change_percent", "percent_change", "regularMarketChangePercent",
    ))
    if direct is not None:
        return direct
    current = _first_number(record, ("price", "last_price", "current_price", "regularMarketPrice", "close"))
    previous = _first_number(record, ("previous_close", "prev_close", "regularMarketPreviousClose"))
    if current is None or previous in (None, 0):
        return None
    return ((current - previous) / previous) * 100.0


def enrich_holdings_with_position_analytics(
    holdings: Sequence[Mapping[str, Any]],
    trade_rows: Sequence[Mapping[str, Any]],
    market_snapshot: Any = None,
) -> list[dict[str, Any]]:
    """Return enriched copies of holdings without fabricating unavailable metrics."""
    lots = _open_lots(trade_rows)
    enriched: list[dict[str, Any]] = []
    for raw in holdings:
        item = dict(raw)
        symbol = str(item.get("symbol") or "").strip().upper()
        sleeve = str(item.get("sleeve") or "").strip().upper()
        status = str(item.get("position_status") or item.get("status") or "").strip().upper()
        is_reserve = symbol == "SGOV" or sleeve in {"RESERVE", "CASH"} or status in RESERVE_STATUSES

        market_record = _find_market_record(market_snapshot, symbol) if symbol and market_snapshot is not None else None
        if market_record is not None:
            name = _first_text(market_record, ("name", "security_name", "display_name", "instrument_name", "shortName", "longName"))
            if name and not item.get("name"):
                item["name"] = name
            daily_change = _daily_change_percent(market_record)
            if daily_change is not None:
                item["daily_change_percent"] = round(daily_change, 4)

        if not is_reserve:
            lot = lots.get(symbol)
            current_shares = _number(item.get("shares"))
            market_value = _number(item.get("market_value"))
            if lot and lot["shares"] > 0 and current_shares is not None and current_shares > 0:
                avg_cost = lot["cost_basis"] / lot["shares"]
                cost_basis = avg_cost * current_shares
                item["average_cost"] = round(avg_cost, 6)
                item["cost_basis"] = round(cost_basis, 2)
                purchase_date = lot.get("purchase_date")
                if purchase_date:
                    item["purchase_date"] = str(purchase_date)
                    item["purchase_date_source"] = "paper_trade_log.csv"
                    item["purchase_date_method"] = "CURRENT_OPEN_POSITION_FIRST_BUY"
                if market_value is not None:
                    unrealized = market_value - cost_basis
                    item["unrealized_pnl"] = round(unrealized, 2)
                    if cost_basis > 0:
                        item["total_return_percent"] = round((unrealized / cost_basis) * 100.0, 4)
                item["analytics_source"] = "paper_trade_log.csv"
        enriched.append(item)
    return enriched


def total_unrealized_pnl(holdings: Sequence[Mapping[str, Any]]) -> float | None:
    values = [_number(item.get("unrealized_pnl")) for item in holdings]
    reported = [value for value in values if value is not None]
    return round(sum(reported), 2) if reported else None
