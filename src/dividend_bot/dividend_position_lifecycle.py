"""Reconstruct read-only Dividend position lifecycle evidence from the paper ledger.

This module never changes portfolio state. It interprets the existing paper trade log
and reconciles it with current holdings so Enterprise reporting can distinguish
OPEN, REENTERED, PARKED_IN_SGOV, CLOSED, and RESERVE state without treating old
positions as current holdings.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

PAPER_TRADE_MODE = True
REPORTING_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

_BUY_ACTIONS = {"PAPER_BUY_OPEN", "PAPER_BUY", "BUY"}
_PARK_ACTIONS = {"PAPER_SELL_TO_SGOV", "PAPER_PARK_IN_SGOV", "PARK_IN_SGOV"}
_CLOSE_ACTIONS = {
    "PAPER_SELL_CLOSE",
    "PAPER_SELL",
    "PAPER_FULL_EXIT",
    "PAPER_CLOSE_POSITION",
    "SELL",
    "CLOSE",
}


def _first(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _symbol(row: Mapping[str, Any]) -> str:
    return str(_first(row, "Ticker", "ticker", "Symbol", "symbol") or "").strip().upper()


def _date(row: Mapping[str, Any]) -> str | None:
    value = _first(row, "Date", "date", "Trade_Date", "trade_date", "timestamp")
    text = str(value).strip() if value not in (None, "") else ""
    return text or None


def _action(row: Mapping[str, Any]) -> str:
    value = _first(row, "Action", "action", "Trade_Action", "trade_action")
    return str(value or "").strip().upper()


def _pair(row: Mapping[str, Any]) -> str | None:
    value = _first(row, "Pair", "pair")
    text = str(value).strip() if value not in (None, "") else ""
    return text or None


def _sleeve(row: Mapping[str, Any]) -> str | None:
    value = _first(row, "Sleeve", "sleeve")
    text = str(value).strip().upper() if value not in (None, "") else ""
    return text or None


def _number(row: Mapping[str, Any], *keys: str) -> float | None:
    value = _first(row, *keys)
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _pair_symbols(pair: str | None) -> list[str]:
    if not pair:
        return []
    normalized = pair.replace("|", "/").replace("-", "/")
    return [part.strip().upper() for part in normalized.split("/") if part.strip()]


def _parked_symbol(row: Mapping[str, Any], action: str, symbol: str) -> str:
    """Resolve the strategy symbol represented by a SGOV parking ledger row.

    Legacy signal-aware initialization writes ``Ticker=SGOV`` for
    ``PAPER_PARK_IN_SGOV`` and identifies the source position only through Pair and
    Sleeve. For lifecycle reporting that row belongs to the source position, not
    to the reserve ETF itself.
    """
    if action not in _PARK_ACTIONS or symbol != "SGOV":
        return symbol
    pair_symbols = _pair_symbols(_pair(row))
    sleeve = _sleeve(row)
    if sleeve == "A" and pair_symbols:
        return pair_symbols[0]
    if sleeve == "B" and len(pair_symbols) > 1:
        return pair_symbols[1]
    return symbol


def build_position_lifecycle(
    log_rows: Iterable[Mapping[str, Any]],
    current_holdings: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return deterministic lifecycle records for symbols observed in the paper ledger.

    Current holdings remain authoritative for whether a symbol is presently OPEN.
    Ledger exits are retained as historical lifecycle evidence rather than being
    reintroduced into the current holdings collection.
    """
    events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in log_rows:
        if not isinstance(row, Mapping):
            continue
        action = _action(row)
        symbol = _parked_symbol(row, action, _symbol(row))
        if not symbol or symbol == "SGOV" or not action:
            continue
        events[symbol].append({
            "date": _date(row),
            "action": action,
            "pair": _pair(row),
            "sleeve": _sleeve(row),
            "shares": _number(row, "Shares", "shares", "Quantity", "quantity"),
            "price": _number(row, "Price", "price", "Trade_Price", "trade_price"),
            "paper_value": _number(row, "Paper_Value", "paper_value", "Value", "value"),
        })

    current: dict[str, Mapping[str, Any]] = {}
    reserve_value = 0.0
    for holding in current_holdings:
        if not isinstance(holding, Mapping):
            continue
        symbol = str(holding.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        if symbol == "SGOV" or str(holding.get("sleeve") or "").upper() == "RESERVE":
            try:
                reserve_value += float(holding.get("market_value") or 0.0)
            except (TypeError, ValueError):
                pass
            continue
        current[symbol] = holding

    records: list[dict[str, Any]] = []
    for symbol in sorted(set(events) | set(current)):
        symbol_events = events.get(symbol, [])
        buy_events = [event for event in symbol_events if event["action"] in _BUY_ACTIONS]
        exit_events = [event for event in symbol_events if event["action"] in (_PARK_ACTIONS | _CLOSE_ACTIONS)]
        first_purchase = buy_events[0]["date"] if buy_events else None
        latest_buy = buy_events[-1] if buy_events else None
        latest_exit = exit_events[-1] if exit_events else None
        is_current = symbol in current

        reentry_count = 0
        for buy in buy_events:
            if any(
                exit_event.get("date") and buy.get("date") and exit_event["date"] < buy["date"]
                for exit_event in exit_events
            ):
                reentry_count += 1

        if is_current:
            latest_exit_date = latest_exit.get("date") if latest_exit else None
            latest_buy_date = latest_buy.get("date") if latest_buy else None
            is_reentered = bool(latest_exit_date and latest_buy_date and latest_buy_date > latest_exit_date)
            lifecycle_status = "REENTERED" if is_reentered else "OPEN"
            current_open_date = latest_buy_date or current[symbol].get("purchase_date")
        elif latest_exit and latest_exit["action"] in _PARK_ACTIONS:
            lifecycle_status = "PARKED_IN_SGOV"
            current_open_date = None
        elif latest_exit:
            lifecycle_status = "CLOSED"
            current_open_date = None
        else:
            lifecycle_status = "CLOSED"
            current_open_date = None

        records.append({
            "symbol": symbol,
            "lifecycle_status": lifecycle_status,
            "is_current_holding": is_current,
            "first_purchase_date": first_purchase,
            "current_open_date": current_open_date,
            "last_exit_date": latest_exit.get("date") if latest_exit else None,
            "last_exit_action": latest_exit.get("action") if latest_exit else None,
            "last_exit_value": latest_exit.get("paper_value") if latest_exit else None,
            "pair": (current.get(symbol) or {}).get("pair") or (symbol_events[-1].get("pair") if symbol_events else None),
            "sleeve": (current.get(symbol) or {}).get("sleeve") or (symbol_events[-1].get("sleeve") if symbol_events else None),
            "reentry_count": reentry_count,
            "event_count": len(symbol_events),
            "evidence_source": "paper_trade_log.csv",
        })

    if reserve_value > 0:
        records.append({
            "symbol": "SGOV",
            "lifecycle_status": "RESERVE",
            "is_current_holding": True,
            "first_purchase_date": None,
            "current_open_date": None,
            "last_exit_date": None,
            "last_exit_action": None,
            "last_exit_value": None,
            "pair": "CASH RESERVE",
            "sleeve": "RESERVE",
            "reentry_count": 0,
            "event_count": 0,
            "reserve_value": round(reserve_value, 2),
            "evidence_source": "paper_state.json",
        })

    return sorted(records, key=lambda item: (item["symbol"], item["lifecycle_status"]))


def enrich_current_holdings_with_lifecycle(
    holdings: Iterable[Mapping[str, Any]],
    lifecycle: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Attach lifecycle metadata to current holdings without adding historical rows."""
    by_symbol = {
        str(item.get("symbol") or "").strip().upper(): item
        for item in lifecycle
        if isinstance(item, Mapping)
    }
    enriched: list[dict[str, Any]] = []
    for raw in holdings:
        row = dict(raw)
        symbol = str(row.get("symbol") or "").strip().upper()
        life = by_symbol.get(symbol)
        if life:
            row["lifecycle_status"] = life.get("lifecycle_status")
            row["lifecycle_first_purchase_date"] = life.get("first_purchase_date")
            row["lifecycle_current_open_date"] = life.get("current_open_date")
            row["lifecycle_last_exit_date"] = life.get("last_exit_date")
            row["lifecycle_reentry_count"] = life.get("reentry_count")
            row["lifecycle_evidence_source"] = life.get("evidence_source")
        enriched.append(row)
    return enriched
