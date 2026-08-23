"""Reconstruct read-only Dividend position lifecycle evidence from the paper ledger.

The lifecycle is audit evidence, not execution. Duplicate initialization rows are
collapsed, and candidates that were initialized directly into SGOV are classified
NEVER_ENTERED rather than being presented as zero-return completed trades.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

PAPER_TRADE_MODE = True
REPORTING_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

_BUY_ACTIONS = {"PAPER_BUY_OPEN", "PAPER_BUY", "BUY", "PAPER_BUY_FROM_SGOV"}
_PARK_ACTIONS = {"PAPER_SELL_TO_SGOV", "PAPER_PARK_IN_SGOV", "PARK_IN_SGOV"}
_WAIT_ACTIONS = {"PAPER_WAIT_IN_SGOV", "PAPER_A_WAIT_IN_SGOV", "PAPER_B_WAIT_IN_SGOV"}
_CLOSE_ACTIONS = {
    "PAPER_SELL_CLOSE", "PAPER_SELL", "PAPER_FULL_EXIT",
    "PAPER_CLOSE_POSITION", "SELL", "CLOSE",
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


def _reason(row: Mapping[str, Any]) -> str:
    value = _first(row, "Reason", "reason")
    return str(value or "").strip()


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
    if action not in (_PARK_ACTIONS | _WAIT_ACTIONS) or symbol != "SGOV":
        return symbol
    pair_symbols = _pair_symbols(_pair(row))
    sleeve = _sleeve(row)
    if sleeve == "A" and pair_symbols:
        return pair_symbols[0]
    if sleeve == "B" and len(pair_symbols) > 1:
        return pair_symbols[1]
    return symbol


def _event_value(event: Mapping[str, Any]) -> float | None:
    paper_value = event.get("paper_value")
    if paper_value is not None:
        try:
            return round(float(paper_value), 2)
        except (TypeError, ValueError):
            return None
    shares = event.get("shares")
    price = event.get("price")
    if shares is None or price is None:
        return None
    try:
        return round(float(shares) * float(price), 2)
    except (TypeError, ValueError):
        return None


def _event_fingerprint(event: Mapping[str, Any]) -> tuple[Any, ...]:
    """Identify duplicate economic ledger rows created by repeated initialization.

    Reason text is intentionally excluded. The legacy initializer and the later
    signal-aware initializer could record the same economic opening transaction
    with different descriptive reasons. Counting both doubles historical cost.
    """
    return (
        event.get("date"), event.get("action"), event.get("pair"), event.get("sleeve"),
        event.get("shares"), event.get("price"), event.get("paper_value"),
    )


def _deduplicate_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []
    for event in rows:
        fingerprint = _event_fingerprint(event)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        result.append(event)
    return result


def _is_never_entered(symbol_events: list[dict[str, Any]], is_current: bool) -> bool:
    """Recognize explicit or legacy initialization that intentionally stayed in SGOV."""
    if is_current:
        return False
    if any(event.get("action") in _WAIT_ACTIONS for event in symbol_events):
        return True
    initialization_parks = [
        event for event in symbol_events
        if event.get("action") in _PARK_ACTIONS
        and "initialization" in str(event.get("reason") or "").lower()
        and "sell" in str(event.get("reason") or "").lower()
    ]
    if initialization_parks:
        latest_park = initialization_parks[-1]
        later_buys = [
            event for event in symbol_events
            if event.get("action") in _BUY_ACTIONS
            and str(event.get("date") or "") > str(latest_park.get("date") or "")
        ]
        return not later_buys
    return False


def _completed_cycle_entry_value(
    symbol_events: list[dict[str, Any]],
    latest_exit: Mapping[str, Any] | None,
) -> tuple[float | None, str | None]:
    """Return cost basis for the shares represented by the completed exit.

    Enterprise paper-capital normalization scales live state quantities but, by
    design, does not rewrite historical trade rows. For a position opened before
    such a resize, the exit can therefore contain more shares than the historical
    entry. In that case the authoritative economic cost is the weighted entry cost
    per share multiplied by the actual exit shares.
    """
    if latest_exit is None:
        return None, None
    try:
        latest_exit_index = max(
            index for index, event in enumerate(symbol_events) if event is latest_exit
        )
    except ValueError:
        return None, None

    previous_exit_index = -1
    for index in range(latest_exit_index - 1, -1, -1):
        if symbol_events[index].get("action") in (_PARK_ACTIONS | _CLOSE_ACTIONS):
            previous_exit_index = index
            break

    buy_events = [
        event for event in symbol_events[previous_exit_index + 1 : latest_exit_index + 1]
        if event.get("action") in _BUY_ACTIONS
    ]
    values = [_event_value(event) for event in buy_events]
    reported_values = [value for value in values if value is not None]
    if not reported_values:
        return None, None

    recorded_cost = float(sum(reported_values))
    entry_shares = [
        float(event["shares"])
        for event in buy_events
        if event.get("shares") is not None and float(event["shares"]) > 0
    ]
    exit_shares = latest_exit.get("shares")
    try:
        exit_shares_number = float(exit_shares) if exit_shares is not None else None
    except (TypeError, ValueError):
        exit_shares_number = None

    if entry_shares and exit_shares_number is not None and exit_shares_number > 0:
        total_entry_shares = sum(entry_shares)
        if total_entry_shares > 0:
            unit_cost = recorded_cost / total_entry_shares
            return round(unit_cost * exit_shares_number, 2), "ENTRY_UNIT_COST_X_EXIT_SHARES"

    return round(recorded_cost, 2), "RECORDED_ENTRY_VALUE"


def _reentry_count(symbol_events: list[dict[str, Any]]) -> int:
    has_ever_opened = False
    position_open = False
    count = 0
    for event in symbol_events:
        action = event.get("action")
        if action in _BUY_ACTIONS:
            if not position_open:
                if has_ever_opened:
                    count += 1
                has_ever_opened = True
                position_open = True
            continue
        if action in (_PARK_ACTIONS | _CLOSE_ACTIONS):
            if position_open:
                position_open = False
    return count


def build_position_lifecycle(
    log_rows: Iterable[Mapping[str, Any]],
    current_holdings: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
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
            "paper_value": _number(
                row, "Paper_Value", "paper_value", "Value", "value",
                "Market_Value", "market_value", "Amount", "amount",
            ),
            "reason": _reason(row),
        })

    events = defaultdict(list, {
        symbol: _deduplicate_events(symbol_events)
        for symbol, symbol_events in events.items()
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
        never_entered = _is_never_entered(symbol_events, is_current)
        reentry_count = _reentry_count(symbol_events)

        if never_entered:
            lifecycle_status = "NEVER_ENTERED"
            current_open_date = None
            first_purchase = None
        elif is_current:
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

        if never_entered:
            entry_value, cost_basis_method = None, None
        else:
            entry_value, cost_basis_method = _completed_cycle_entry_value(symbol_events, latest_exit)
        exit_value = None if never_entered else (_event_value(latest_exit) if latest_exit else None)
        realized_gain_loss = None
        if entry_value is not None and exit_value is not None:
            realized_gain_loss = round(exit_value - entry_value, 2)

        records.append({
            "symbol": symbol,
            "lifecycle_status": lifecycle_status,
            "is_current_holding": is_current,
            "first_purchase_date": first_purchase,
            "current_open_date": current_open_date,
            "last_exit_date": None if never_entered else (latest_exit.get("date") if latest_exit else None),
            "last_exit_action": None if never_entered else (latest_exit.get("action") if latest_exit else None),
            "last_exit_reason": None if never_entered else (latest_exit.get("reason") if latest_exit else None),
            "entry_value": entry_value,
            "last_exit_value": exit_value,
            "realized_gain_loss": realized_gain_loss,
            "realized_cost_basis_method": cost_basis_method,
            "pair": (current.get(symbol) or {}).get("pair") or (symbol_events[-1].get("pair") if symbol_events else None),
            "sleeve": (current.get(symbol) or {}).get("sleeve") or (symbol_events[-1].get("sleeve") if symbol_events else None),
            "reentry_count": 0 if never_entered else reentry_count,
            "event_count": len(symbol_events),
            "raw_event_count": len(symbol_events),
            "never_entered_reason": (
                "ENTRY_GATE_WAIT_IN_SGOV" if any(e.get("action") in _WAIT_ACTIONS for e in symbol_events)
                else "LEGACY_SIGNAL_AWARE_INITIALIZATION_ON_SELL" if never_entered else None
            ),
            "evidence_source": "paper_trade_log.csv",
        })

    if reserve_value > 0:
        records.append({
            "symbol": "SGOV", "lifecycle_status": "RESERVE", "is_current_holding": True,
            "first_purchase_date": None, "current_open_date": None, "last_exit_date": None,
            "last_exit_action": None, "last_exit_reason": None, "entry_value": None, "last_exit_value": None,
            "realized_gain_loss": None, "realized_cost_basis_method": None,
            "pair": "CASH RESERVE", "sleeve": "RESERVE",
            "reentry_count": 0, "event_count": 0, "raw_event_count": 0,
            "reserve_value": round(reserve_value, 2), "never_entered_reason": None,
            "evidence_source": "paper_state.json",
        })

    return sorted(records, key=lambda item: (item["symbol"], item["lifecycle_status"]))


def enrich_current_holdings_with_lifecycle(
    holdings: Iterable[Mapping[str, Any]],
    lifecycle: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_symbol = {
        str(item.get("symbol") or "").strip().upper(): item
        for item in lifecycle if isinstance(item, Mapping)
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
