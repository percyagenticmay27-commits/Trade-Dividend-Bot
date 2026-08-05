"""Build a simple Executive Daily Change Summary from paper evidence.

Each business row describes one stock and one event. Pair-level state strings are
intentionally avoided because they can mix two different sleeve activities and
make BUY, SELL, and SGOV transitions ambiguous. This module is reporting-only.
"""
from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.dividend_bot.executive_reporting_framework import executive_framework_rows

MODULE_NAME = "executive_daily_change_summary"
MODULE_VERSION = "3.1.0"
PAPER_TRADE_MODE = True
LEGACY_STARTING_CAPITAL = 500.0

DAILY_CHANGE_FIELDS = [
    "activity_date",
    "days_since",
    "report_section",
    "event",
    "original_pair",
    "current_pair",
    "stock",
    "from_location",
    "to_location",
    "amount",
    "signal",
    "next_action",
    "reason",
    "source",
    "paper_trade_mode",
]

_ACTION_EVENT = {
    "PAPER_BUY_OPEN": "BOUGHT",
    "PAPER_BUY_FROM_SGOV": "BOUGHT FROM SGOV",
    "PAPER_SELL_TO_SGOV": "SOLD TO SGOV",
    "PAPER_PARK_IN_SGOV": "MOVED TO SGOV",
    "PAPER_DIVIDEND_RECEIVED": "DIVIDEND RECEIVED",
    "EARNINGS_EXIT": "EARNINGS EXIT TO SGOV",
    "PAPER_EARNINGS_EXIT": "EARNINGS EXIT TO SGOV",
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _scale_for(state: dict[str, Any]) -> float:
    return 100.0 if abs(_number(state.get("starting_capital")) - LEGACY_STARTING_CAPITAL) < 1e-6 else 1.0


def _blank_row(section: str, **values: Any) -> dict[str, Any]:
    row = {field: "" for field in DAILY_CHANGE_FIELDS}
    row["report_section"] = section
    row["paper_trade_mode"] = True
    row.update(values)
    return row


def _load_json(path: Path, *, required: bool = False) -> dict[str, Any]:
    if not path.is_file():
        if required:
            raise RuntimeError(f"Required paper state is missing: {path}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Paper evidence is unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Paper evidence must be a JSON object: {path}")
    return value


def _load_log(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _days_since(value: str, trading_date: date) -> str:
    parsed = _parse_date(value)
    return "" if parsed is None else str(max(0, (trading_date - parsed).days))


def _pair_name(entry: dict[str, Any], fallback: str) -> str:
    if not entry:
        return fallback
    return f"{str(entry.get('a_ticker') or 'A').strip()} / {str(entry.get('b_ticker') or 'B').strip()}"


def _side_details(entry: dict[str, Any], side: str, scale: float) -> dict[str, Any]:
    key = side.lower()
    ticker = str(entry.get(f"{key}_ticker") or side).strip()
    shares = _number(entry.get(f"{key}_shares")) * scale
    in_sgov = bool(entry.get(f"{key}_in_sgov", shares == 0))
    prices = entry.get("last_prices") if isinstance(entry.get("last_prices"), dict) else {}
    price = _number(prices.get(side))
    market_value = shares * price if not in_sgov else 0.0
    signals = entry.get("last_signal") if isinstance(entry.get("last_signal"), dict) else {}
    signal = str(signals.get(side) or "UNKNOWN").upper()
    return {
        "ticker": ticker,
        "in_sgov": in_sgov,
        "market_value": market_value,
        "signal": signal,
    }


def _next_action(*, in_sgov: bool, signal: str) -> str:
    signal = signal.upper()
    if in_sgov:
        return "WAIT FOR BUY CONFIRMATION" if signal == "BUY" else "REMAIN IN SGOV"
    if signal == "SELL":
        return "REVIEW SALE"
    return "CONTINUE HOLDING"


def _current_values(state: dict[str, Any], scale: float) -> tuple[float, float]:
    stock = 0.0
    sgov = 0.0
    for value in (state.get("pairs") or {}).values():
        if not isinstance(value, dict):
            continue
        stock += _side_details(value, "A", scale)["market_value"]
        stock += _side_details(value, "B", scale)["market_value"]
        sgov += _number(value.get("sgov_balance")) * scale
    return stock, sgov


def _replacement_rows(
    *,
    previous: dict[str, Any],
    current: dict[str, Any],
    trading_date: date,
    current_scale: float,
) -> list[dict[str, Any]]:
    """Expose removed and added stocks whenever a pair member changes."""
    rows: list[dict[str, Any]] = []
    previous_pairs = previous.get("pairs") if isinstance(previous.get("pairs"), dict) else {}
    current_pairs = current.get("pairs") if isinstance(current.get("pairs"), dict) else {}
    previous_scale = _scale_for(previous)

    for original_pair, current_entry in current_pairs.items():
        if not isinstance(current_entry, dict):
            continue
        prior_entry = previous_pairs.get(original_pair)
        if not isinstance(prior_entry, dict):
            continue
        current_pair = _pair_name(current_entry, original_pair)
        for side in ("A", "B"):
            prior = _side_details(prior_entry, side, previous_scale)
            now = _side_details(current_entry, side, current_scale)
            if prior["ticker"] == now["ticker"]:
                continue
            removed_amount = prior["market_value"]
            rows.append(_blank_row(
                "Pair Changes",
                activity_date=trading_date.isoformat(),
                days_since="0",
                event="REMOVED FROM PAIR AND MOVED TO SGOV",
                original_pair=original_pair,
                current_pair=current_pair,
                stock=prior["ticker"],
                from_location="STOCK POSITION" if removed_amount else "PAIR ASSIGNMENT",
                to_location="SGOV",
                amount=f"{removed_amount:.2f}",
                signal="SELL",
                next_action=f"REPLACED BY {now['ticker']}",
                reason=f"{prior['ticker']} was removed when the {side}-sleeve changed to {now['ticker']}.",
                source="paper_state_previous.json -> paper_state.json",
            ))
            rows.append(_blank_row(
                "Pair Changes",
                activity_date=trading_date.isoformat(),
                days_since="0",
                event="ADDED AS REPLACEMENT",
                original_pair=original_pair,
                current_pair=current_pair,
                stock=now["ticker"],
                from_location="NOT IN CURRENT PAIR",
                to_location="SGOV" if now["in_sgov"] else "STOCK POSITION",
                amount=f"{now['market_value']:.2f}",
                signal=now["signal"],
                next_action=_next_action(in_sgov=now["in_sgov"], signal=now["signal"]),
                reason=f"{now['ticker']} replaced {prior['ticker']} in the {side}-sleeve.",
                source="paper_state_previous.json -> paper_state.json",
            ))
    return rows


def build_daily_change_rows(
    *, root_dir: str | Path, trading_date: date, generated_at: datetime | None = None
) -> list[dict[str, Any]]:
    root = Path(root_dir)
    state = _load_json(root / "paper_state.json", required=True)
    previous = _load_json(root / "paper_state_previous.json")
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    scale = _scale_for(state)

    rows: list[dict[str, Any]] = []
    for item in executive_framework_rows(
        source_name="daily_change_summary.md", trading_date=trading_date, generated_at=generated
    ):
        rows.append(_blank_row(
            item["section"], event=item["field"], reason=str(item["value"])
        ))

    current_stock, current_sgov = _current_values(state, scale)
    previous_stock, previous_sgov = _current_values(previous, _scale_for(previous)) if previous else (0.0, 0.0)
    for event, prior, current in (
        ("STOCK VALUE CHANGE", previous_stock, current_stock),
        ("SGOV VALUE CHANGE", previous_sgov, current_sgov),
        ("TOTAL TRACKED CAPITAL CHANGE", previous_stock + previous_sgov, current_stock + current_sgov),
    ):
        amount = current - prior if previous else 0.0
        rows.append(_blank_row(
            "Portfolio Changes",
            activity_date=trading_date.isoformat(),
            days_since="0",
            event=event,
            from_location=f"${prior:,.2f}" if previous else "NOT AVAILABLE",
            to_location=f"${current:,.2f}",
            amount=f"{amount:.2f}" if previous else "NOT AVAILABLE",
            reason="Compared with the previous authoritative snapshot." if previous else "No previous snapshot was available; no change was inferred.",
            source="paper_state.json",
        ))

    rows.extend(_replacement_rows(
        previous=previous,
        current=state,
        trading_date=trading_date,
        current_scale=scale,
    ))

    pairs = state.get("pairs") if isinstance(state.get("pairs"), dict) else {}
    log_rows = _load_log(root / "paper_trade_log.csv")
    todays_events = [row for row in log_rows if _parse_date(row.get("Date")) == trading_date]
    for activity in todays_events:
        original_pair = str(activity.get("Pair") or "").strip()
        entry = pairs.get(original_pair) if isinstance(pairs.get(original_pair), dict) else {}
        current_pair = _pair_name(entry, original_pair)
        side = str(activity.get("Sleeve") or "").strip().upper()
        details = _side_details(entry, side, scale) if entry and side in {"A", "B"} else {}
        action = str(activity.get("Action") or "").strip().upper()
        stock = str(activity.get("Ticker") or details.get("ticker") or "").strip()
        event = _ACTION_EVENT.get(action, action.replace("_", " ") or "RECORDED EVENT")
        amount = _number(activity.get("Paper_Value")) * scale
        if action in {"PAPER_SELL_TO_SGOV", "PAPER_PARK_IN_SGOV", "EARNINGS_EXIT", "PAPER_EARNINGS_EXIT"}:
            from_location, to_location = "STOCK POSITION", "SGOV"
            next_action = "REMAIN IN SGOV"
        elif action in {"PAPER_BUY_OPEN", "PAPER_BUY_FROM_SGOV"}:
            from_location, to_location = "SGOV", "STOCK POSITION"
            next_action = "CONTINUE HOLDING"
        else:
            from_location = to_location = "STOCK POSITION" if details and not details.get("in_sgov") else "SGOV"
            next_action = _next_action(
                in_sgov=bool(details.get("in_sgov", False)),
                signal=str(details.get("signal") or activity.get("Signal") or "UNKNOWN"),
            )
        rows.append(_blank_row(
            "Today's Activity",
            activity_date=trading_date.isoformat(),
            days_since="0",
            event=event,
            original_pair=original_pair,
            current_pair=current_pair,
            stock=stock,
            from_location=from_location,
            to_location=to_location,
            amount=f"{amount:.2f}",
            signal=str(activity.get("Signal") or "").upper(),
            next_action=next_action,
            reason=str(activity.get("Reason") or "").strip(),
            source="paper_trade_log.csv",
        ))

    if not todays_events:
        rows.append(_blank_row(
            "Today's Activity",
            activity_date=trading_date.isoformat(),
            days_since="0",
            event="NO NEW TRANSACTION EVENTS",
            next_action="FOLLOW CURRENT HOLDING PLAN",
            reason="No dated paper-trade events were recorded for this trading date.",
            source="paper_trade_log.csv",
        ))

    for original_pair, entry in pairs.items():
        if not isinstance(entry, dict):
            continue
        current_pair = _pair_name(entry, original_pair)
        for side in ("A", "B"):
            details = _side_details(entry, side, scale)
            location = "SGOV" if details["in_sgov"] else "STOCK POSITION"
            rows.append(_blank_row(
                "Next Trading Day",
                activity_date=str(state.get("as_of_date") or trading_date.isoformat())[:10],
                days_since=_days_since(str(state.get("as_of_date") or ""), trading_date),
                event="NEXT-DAY PLAN",
                original_pair=original_pair,
                current_pair=current_pair,
                stock=details["ticker"],
                from_location=location,
                to_location=location,
                amount=f"{details['market_value']:.2f}",
                signal=details["signal"],
                next_action=_next_action(in_sgov=details["in_sgov"], signal=details["signal"]),
                reason="One stock, one location, and one next action are reported on this row.",
                source="paper_state.json",
            ))

    rows.append(_blank_row(
        "Final Assessment",
        activity_date=trading_date.isoformat(),
        days_since="0",
        event="SAFETY STATUS",
        to_location="PAPER ONLY",
        next_action="NO REAL TRADES",
        reason="No broker connection or real-order execution is used by this report.",
        source="executive_daily_change_summary.py",
    ))
    return rows
