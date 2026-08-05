"""Build the Step 3 Executive Daily Change Summary from paper evidence.

Reporting only: this module never places orders, moves capital, or changes strategy
state. It summarizes changes recorded in the paper trade log and the current pair
ledger, then produces explicit next-day actions.
"""
from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.dividend_bot.executive_reporting_framework import executive_framework_rows

MODULE_NAME = "executive_daily_change_summary"
MODULE_VERSION = "3.0.0"
PAPER_TRADE_MODE = True
APPROVED_STARTING_CAPITAL = 50_000.0
LEGACY_STARTING_CAPITAL = 500.0

DAILY_CHANGE_FIELDS = [
    "activity_date",
    "days_since",
    "report_section",
    "change_category",
    "current_pair",
    "original_pair",
    "pair_type",
    "stock",
    "stock_moved",
    "previous_state",
    "current_state",
    "signal",
    "required_action",
    "amount",
    "previous_value",
    "current_value",
    "change_value",
    "change_pct",
    "reason",
    "next_day_action",
    "priority",
    "source",
    "paper_trade_mode",
]

_ACTION_CATEGORY = {
    "PAPER_BUY_OPEN": "PURCHASE",
    "PAPER_BUY_FROM_SGOV": "REENTRY",
    "PAPER_SELL_TO_SGOV": "SGOV MOVEMENT",
    "PAPER_PARK_IN_SGOV": "SGOV MOVEMENT",
    "PAPER_DIVIDEND_RECEIVED": "DIVIDEND",
    "PAIR_REPLACED": "PAIR REPLACEMENT",
    "PAPER_REPLACEMENT": "PAIR REPLACEMENT",
    "EARNINGS_EXIT": "EARNINGS EVENT",
    "PAPER_EARNINGS_EXIT": "EARNINGS EVENT",
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


def _pair_identity(original_pair: str, entry: dict[str, Any]) -> tuple[str, str]:
    a = str(entry.get("a_ticker") or "A").strip()
    b = str(entry.get("b_ticker") or "B").strip()
    return f"{a} / {b}", "ORIGINAL" if f"{a} / {b}" == original_pair else "REPLACEMENT"


def _position_state(entry: dict[str, Any]) -> str:
    a = str(entry.get("a_ticker") or "A").strip()
    b = str(entry.get("b_ticker") or "B").strip()
    a_sgov = bool(entry.get("a_in_sgov", _number(entry.get("a_shares")) == 0))
    b_sgov = bool(entry.get("b_in_sgov", _number(entry.get("b_shares")) == 0))
    if a_sgov and b_sgov:
        return "MOVED_TO_SGOV"
    if not a_sgov and not b_sgov:
        return f"INVESTED_IN_{a}_AND_{b}"
    if a_sgov:
        return f"A_MOVED_TO_SGOV_B_INVESTED_IN_{b}"
    return f"A_INVESTED_IN_{a}_B_MOVED_TO_SGOV"


def _next_action(entry: dict[str, Any]) -> str:
    state = _position_state(entry)
    signals = entry.get("last_signal") if isinstance(entry.get("last_signal"), dict) else {}
    values = {str(v).upper() for v in signals.values()}
    if state == "MOVED_TO_SGOV":
        return "WAIT_FOR_ENTRY_CONFIRMATION" if "BUY" in values else "REMAIN_IN_SGOV"
    if "SELL" in values:
        return "SELL_REVIEW"
    if "BUY" in values and state.startswith("INVESTED_IN_"):
        return "CONTINUE_HOLDING"
    return "MONITOR_NEXT_SESSION"


def _current_values(state: dict[str, Any], scale: float) -> tuple[float, float]:
    stock = 0.0
    sgov = 0.0
    for value in (state.get("pairs") or {}).values():
        if not isinstance(value, dict):
            continue
        prices = value.get("last_prices") if isinstance(value.get("last_prices"), dict) else {}
        for side in ("A", "B"):
            key = side.lower()
            in_sgov = bool(value.get(f"{key}_in_sgov", _number(value.get(f"{key}_shares")) == 0))
            if not in_sgov:
                stock += _number(value.get(f"{key}_shares")) * scale * _number(prices.get(side))
        sgov += _number(value.get("sgov_balance")) * scale
    return stock, sgov


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
        rows.append(_blank_row(item["section"], change_category=item["field"], current_value=str(item["value"])))

    current_stock, current_sgov = _current_values(state, scale)
    previous_stock, previous_sgov = _current_values(previous, _scale_for(previous)) if previous else (0.0, 0.0)
    for category, prior, current in (
        ("CURRENT STOCK MARKET VALUE", previous_stock, current_stock),
        ("SGOV VALUE", previous_sgov, current_sgov),
        ("TOTAL TRACKED CAPITAL", previous_stock + previous_sgov, current_stock + current_sgov),
    ):
        delta = current - prior if previous else 0.0
        pct = (delta / prior * 100.0) if previous and prior else 0.0
        rows.append(_blank_row(
            "Portfolio Changes", activity_date=trading_date.isoformat(), days_since="0",
            change_category=category, previous_value=f"{prior:.2f}" if previous else "NOT AVAILABLE",
            current_value=f"{current:.2f}", change_value=f"{delta:.2f}" if previous else "NOT AVAILABLE",
            change_pct=f"{pct:.2f}%" if previous else "NOT AVAILABLE",
            reason="Compared with paper_state_previous.json." if previous else "No prior authoritative snapshot was available; no change was inferred.",
            source="paper_state.json", priority="INFO",
        ))

    pairs = state.get("pairs") if isinstance(state.get("pairs"), dict) else {}
    log_rows = _load_log(root / "paper_trade_log.csv")
    todays_events = [r for r in log_rows if _parse_date(r.get("Date")) == trading_date]
    for event in todays_events:
        original_pair = str(event.get("Pair") or "").strip()
        entry = pairs.get(original_pair) if isinstance(pairs.get(original_pair), dict) else {}
        current_pair, pair_type = _pair_identity(original_pair, entry) if entry else (original_pair, "UNKNOWN")
        action = str(event.get("Action") or "").strip().upper()
        ticker = str(event.get("Ticker") or "").strip()
        category = _ACTION_CATEGORY.get(action, "TRADING EVENT")
        amount = _number(event.get("Paper_Value")) * scale
        state_now = _position_state(entry) if entry else "UNKNOWN"
        required = _next_action(entry) if entry else "REVIEW_EVENT"
        rows.append(_blank_row(
            "Daily Events", activity_date=trading_date.isoformat(), days_since="0",
            change_category=category, current_pair=current_pair, original_pair=original_pair,
            pair_type=pair_type, stock=ticker, stock_moved=ticker if "SGOV" in action or "EXIT" in action else "",
            previous_state="", current_state=state_now, signal=str(event.get("Signal") or "").upper(),
            required_action=required, amount=f"{amount:.2f}", reason=str(event.get("Reason") or "").strip(),
            next_day_action=required, priority="HIGH" if category in {"PURCHASE", "SGOV MOVEMENT", "PAIR REPLACEMENT", "EARNINGS EVENT"} else "NORMAL",
            source="paper_trade_log.csv",
        ))

    if not todays_events:
        rows.append(_blank_row(
            "Daily Events", activity_date=trading_date.isoformat(), days_since="0",
            change_category="NO NEW TRANSACTION EVENTS", current_state="UNCHANGED",
            required_action="NO_ACTION", reason="No dated paper-trade events were recorded for this trading date.",
            next_day_action="FOLLOW_CURRENT_PAIR_RECOMMENDATIONS", priority="INFO", source="paper_trade_log.csv",
        ))

    for original_pair, value in pairs.items():
        if not isinstance(value, dict):
            continue
        current_pair, pair_type = _pair_identity(original_pair, value)
        signals = value.get("last_signal") if isinstance(value.get("last_signal"), dict) else {}
        signal = f"A={signals.get('A', 'UNKNOWN')}; B={signals.get('B', 'UNKNOWN')}"
        next_action = _next_action(value)
        rows.append(_blank_row(
            "Next Trading Day", activity_date=str(state.get("as_of_date") or trading_date.isoformat())[:10],
            days_since=_days_since(str(state.get("as_of_date") or ""), trading_date),
            change_category="PAIR RECOMMENDATION", current_pair=current_pair, original_pair=original_pair,
            pair_type=pair_type, current_state=_position_state(value), signal=signal,
            required_action=next_action, reason="Derived from current paper state and latest validated signals.",
            next_day_action=next_action, priority="HIGH" if next_action == "SELL_REVIEW" else "NORMAL",
            source="paper_state.json",
        ))

    rows.append(_blank_row(
        "Final Assessment", activity_date=trading_date.isoformat(), days_since="0",
        change_category="SAFETY STATUS", current_state="PAPER ONLY",
        required_action="NO_REAL_TRADES", reason="No broker connection or real-order execution is used by this report.",
        next_day_action="PAPER_VALIDATION_ONLY", priority="LOCKED", source="executive_daily_change_summary.py",
    ))
    return rows
