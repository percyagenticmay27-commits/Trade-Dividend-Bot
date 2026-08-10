"""Read-only audit for Dividend positions created before strategy ownership existed.

The audit never mutates ``paper_state.json`` and never assigns an owner. It reconstructs
Strategy A/B evidence at the open-position entry date from the shared historical market
snapshot so legacy open positions can be reviewed without rewriting history.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from paper_portfolio_config import PAIR_MANAGED, PAPER_PAIRS
from .dividend_entry_strategy_signals import build_strategy_signals
from .dividend_strategy_ownership import resolve_strategy_ownership

PAPER_TRADE_MODE = True
REPORTING_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False

_BUY_ACTIONS = {"PAPER_BUY_OPEN", "PAPER_BUY", "BUY", "PAPER_BUY_FROM_SGOV"}
_EXIT_ACTIONS = {
    "PAPER_SELL_TO_SGOV", "PAPER_PARK_IN_SGOV", "PARK_IN_SGOV",
    "PAPER_SELL_CLOSE", "PAPER_SELL", "PAPER_FULL_EXIT", "PAPER_CLOSE_POSITION",
    "SELL", "CLOSE",
}


def _first(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _action(row: Mapping[str, Any]) -> str:
    return str(_first(row, "Action", "action", "Trade_Action", "trade_action") or "").strip().upper()


def _symbol(row: Mapping[str, Any]) -> str:
    return str(_first(row, "Ticker", "ticker", "Symbol", "symbol") or "").strip().upper()


def _date(row: Mapping[str, Any]) -> str | None:
    value = _first(row, "Date", "date", "Trade_Date", "trade_date", "timestamp")
    if value in (None, ""):
        return None
    return str(value).strip()[:10] or None


def _current_open_dates(log_rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """Return the first BUY date of the currently open cycle for each symbol."""
    state: dict[str, dict[str, Any]] = {}
    for row in log_rows:
        if not isinstance(row, Mapping):
            continue
        symbol = _symbol(row)
        action = _action(row)
        date = _date(row)
        if not symbol or not date:
            continue
        item = state.setdefault(symbol, {"open": False, "date": None})
        if action in _BUY_ACTIONS:
            if not item["open"]:
                item["open"] = True
                item["date"] = date
        elif action in _EXIT_ACTIONS and item["open"]:
            item["open"] = False
            item["date"] = None
    return {symbol: str(item["date"]) for symbol, item in state.items() if item["open"] and item["date"]}


def _records(snapshot: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    rows = snapshot.get("records") if isinstance(snapshot, Mapping) else None
    if not isinstance(rows, list):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        if symbol:
            result[symbol] = row
    return result


def _history_frame(record: Mapping[str, Any], through_date: str) -> pd.DataFrame:
    history = record.get("history") if isinstance(record.get("history"), Mapping) else {}
    rows = history.get("rows") if isinstance(history, Mapping) else None
    if not isinstance(rows, list):
        return pd.DataFrame()
    values: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        raw_date = row.get("date") or row.get("Date") or row.get("timestamp")
        date = str(raw_date or "")[:10]
        if not date or date > through_date:
            continue
        values.append({
            "Date": date,
            "Close": row.get("close", row.get("Close")),
            "High": row.get("high", row.get("High")),
            "Low": row.get("low", row.get("Low")),
        })
    frame = pd.DataFrame(values)
    if frame.empty:
        return frame
    frame = frame.sort_values("Date").reset_index(drop=True)
    for column in ("Close", "High", "Low"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["Close", "High", "Low"]).reset_index(drop=True)


def _pair_symbols(pair: str) -> tuple[str | None, str | None]:
    parts = [item.strip().upper() for item in str(pair or "").split("/") if item.strip()]
    return (parts[0] if parts else None, parts[1] if len(parts) > 1 else None)


def build_legacy_strategy_ownership_audit(
    *,
    state: Mapping[str, Any] | None,
    log_rows: Iterable[Mapping[str, Any]],
    market_snapshot: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Audit unowned currently-open positions against entry-date strategy evidence."""
    pairs = state.get("pairs") if isinstance(state, Mapping) else None
    if not isinstance(pairs, Mapping):
        pairs = {}
    open_dates = _current_open_dates(log_rows)
    market = _records(market_snapshot)
    results: list[dict[str, Any]] = []

    for pair_name, raw in pairs.items():
        if not isinstance(raw, Mapping):
            continue
        config = PAPER_PAIRS.get(str(pair_name))
        if not isinstance(config, Mapping):
            continue
        symbol_a, symbol_b = _pair_symbols(str(pair_name))
        open_sides = []
        for side, symbol in (("A", symbol_a), ("B", symbol_b)):
            if not symbol:
                continue
            shares = raw.get(f"{side.lower()}_shares")
            try:
                is_open = float(shares or 0.0) > 0.0
            except (TypeError, ValueError):
                is_open = False
            if is_open:
                open_sides.append((side, symbol))
        if not open_sides:
            continue

        if config.get("architecture") == PAIR_MANAGED:
            existing_owner = str(raw.get("strategy_owner") or "").strip().upper() or None
            if existing_owner:
                continue
            entry_dates = {open_dates.get(symbol) for _side, symbol in open_sides if open_dates.get(symbol)}
            entry_date = min(entry_dates) if entry_dates else None
            signal_symbol = str(config.get("a_signal") or config.get("a") or "").strip().upper()
            record = market.get(signal_symbol)
            frame = _history_frame(record, entry_date) if record is not None and entry_date else pd.DataFrame()
            signals = build_strategy_signals(frame) if not frame.empty else {"available": False, "reason": "ENTRY_DATE_MARKET_HISTORY_UNAVAILABLE"}
            resolution = resolve_strategy_ownership(signals)
            results.append({
                "pair": str(pair_name),
                "sleeve": "PAIR",
                "symbols": [symbol for _side, symbol in open_sides],
                "signal_symbol": signal_symbol,
                "entry_date": entry_date,
                "history_rows_through_entry": len(frame),
                "strategy_signals": signals,
                "reconstruction": resolution,
                "migration_recommendation": (
                    "ELIGIBLE_FOR_EXPLICIT_BACKFILL" if resolution.get("resolved")
                    else "KEEP_LEGACY_UNASSIGNED"
                ),
                "state_mutated": False,
            })
            continue

        for side, symbol in open_sides:
            existing_owner = str(raw.get(f"{side.lower()}_strategy_owner") or "").strip().upper() or None
            if existing_owner:
                continue
            entry_date = open_dates.get(symbol)
            signal_symbol = str(config.get(f"{side.lower()}_signal") or symbol).strip().upper()
            record = market.get(signal_symbol)
            frame = _history_frame(record, entry_date) if record is not None and entry_date else pd.DataFrame()
            signals = build_strategy_signals(frame) if not frame.empty else {"available": False, "reason": "ENTRY_DATE_MARKET_HISTORY_UNAVAILABLE"}
            resolution = resolve_strategy_ownership(signals)
            results.append({
                "pair": str(pair_name),
                "sleeve": side,
                "symbols": [symbol],
                "signal_symbol": signal_symbol,
                "entry_date": entry_date,
                "history_rows_through_entry": len(frame),
                "strategy_signals": signals,
                "reconstruction": resolution,
                "migration_recommendation": (
                    "ELIGIBLE_FOR_EXPLICIT_BACKFILL" if resolution.get("resolved")
                    else "KEEP_LEGACY_UNASSIGNED"
                ),
                "state_mutated": False,
            })

    return {
        "paper_trade_mode": True,
        "reporting_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "audit_type": "LEGACY_STRATEGY_OWNERSHIP_RECONSTRUCTION",
        "state_mutated": False,
        "audited_position_count": len(results),
        "eligible_for_explicit_backfill_count": sum(
            1 for row in results if row["migration_recommendation"] == "ELIGIBLE_FOR_EXPLICIT_BACKFILL"
        ),
        "positions": results,
    }


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    if not source.is_file():
        return []
    with source.open("r", newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]
