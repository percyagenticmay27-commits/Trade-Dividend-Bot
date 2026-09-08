"""Build the simplified Executive Daily Change Summary event ledger.

Each row represents one clear portfolio event. The report never executes trades,
moves capital, or modifies paper state.
"""
from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.dividend_bot.executive_reporting_framework import executive_framework_rows

MODULE_NAME = "executive_daily_change_summary"
MODULE_VERSION = "3.2.0"
PAPER_TRADE_MODE = True
LEGACY_STARTING_CAPITAL = 500.0

DAILY_CHANGE_FIELDS = [
    "activity_date",
    "original_pair",
    "pair",
    "event",
    "stock",
    "from_location",
    "to_location",
    "amount",
    "next_action",
]

_ACTION_EVENT = {
    "PAPER_BUY_OPEN": "Purchased",
    "PAPER_BUY_FROM_SGOV": "Purchased from SGOV",
    "PAPER_SELL_TO_SGOV": "Moved to SGOV",
    "PAPER_PARK_IN_SGOV": "Moved to SGOV",
    "PAPER_DIVIDEND_RECEIVED": "Dividend received",
    "EARNINGS_EXIT": "Earnings exit",
    "PAPER_EARNINGS_EXIT": "Earnings exit",
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _scale_for(state: dict[str, Any]) -> float:
    return 100.0 if abs(_number(state.get("starting_capital")) - LEGACY_STARTING_CAPITAL) < 1e-6 else 1.0


def _row(**values: Any) -> dict[str, str]:
    row = {field: "" for field in DAILY_CHANGE_FIELDS}
    row.update({key: str(value) for key, value in values.items()})
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


def _pair_name(entry: dict[str, Any], fallback: str) -> str:
    if not entry:
        return fallback
    a = str(entry.get("a_ticker") or "A").strip()
    b = str(entry.get("b_ticker") or "B").strip()
    return f"{a}/{b}"


def _ticker(entry: dict[str, Any], side: str) -> str:
    return str(entry.get(f"{side.lower()}_ticker") or side).strip()


def _market_value(entry: dict[str, Any], side: str, scale: float) -> float:
    key = side.lower()
    if bool(entry.get(f"{key}_in_sgov", _number(entry.get(f"{key}_shares")) == 0)):
        return 0.0
    prices = entry.get("last_prices") if isinstance(entry.get("last_prices"), dict) else {}
    return _number(entry.get(f"{key}_shares")) * scale * _number(prices.get(side))


def _replacement_rows(
    *, previous: dict[str, Any], current: dict[str, Any], trading_date: date
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
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
        display_original = original_pair.replace(" ", "")
        for side in ("A", "B"):
            old_stock = _ticker(prior_entry, side)
            new_stock = _ticker(current_entry, side)
            if old_stock == new_stock:
                continue
            removed_amount = _market_value(prior_entry, side, previous_scale)
            rows.append(_row(
                activity_date=trading_date.isoformat(),
                original_pair=display_original,
                pair=display_original,
                event="Removed from pair and moved to SGOV",
                stock=old_stock,
                from_location="Stock Position" if removed_amount else "Pair Assignment",
                to_location="SGOV",
                amount=f"${removed_amount:,.2f}",
                next_action=f"Replaced by {new_stock}",
            ))
            rows.append(_row(
                activity_date=trading_date.isoformat(),
                original_pair=display_original,
                pair=current_pair,
                event="Added as replacement",
                stock=new_stock,
                from_location="Not in Current Pair",
                to_location="SGOV" if bool(current_entry.get(f"{side.lower()}_in_sgov", True)) else "Stock Position",
                amount="$0.00" if bool(current_entry.get(f"{side.lower()}_in_sgov", True)) else f"${_market_value(current_entry, side, _scale_for(current)):,.2f}",
                next_action="Remain in SGOV" if bool(current_entry.get(f"{side.lower()}_in_sgov", True)) else "Continue Holding",
            ))
    return rows


def build_daily_change_rows(
    *, root_dir: str | Path, trading_date: date, generated_at: datetime | None = None
) -> list[dict[str, str]]:
    root = Path(root_dir)
    state = _load_json(root / "paper_state.json", required=True)
    previous = _load_json(root / "paper_state_previous.json")
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)

    rows: list[dict[str, str]] = []
    for item in executive_framework_rows(
        source_name="daily_change_summary.md",
        trading_date=trading_date,
        generated_at=generated,
    ):
        rows.append(_row(event=item["field"], next_action=item["value"]))

    replacement_rows = _replacement_rows(
        previous=previous,
        current=state,
        trading_date=trading_date,
    )
    rows.extend(replacement_rows)

    pairs = state.get("pairs") if isinstance(state.get("pairs"), dict) else {}
    log_rows = _load_log(root / "paper_trade_log.csv")
    todays_events = [row for row in log_rows if _parse_date(row.get("Date")) == trading_date]

    replacement_sale_keys = {
        (row["stock"], row["original_pair"])
        for row in replacement_rows
        if row["event"] == "Removed from pair and moved to SGOV"
    }

    for activity in todays_events:
        original_raw = str(activity.get("Pair") or "").strip()
        original_pair = original_raw.replace(" ", "")
        entry = pairs.get(original_raw) if isinstance(pairs.get(original_raw), dict) else {}
        pair = _pair_name(entry, original_raw).replace(" ", "")
        action = str(activity.get("Action") or "").strip().upper()
        stock = str(activity.get("Ticker") or "").strip()

        if action == "PAPER_SELL_TO_SGOV" and (stock, original_pair) in replacement_sale_keys:
            continue

        event = _ACTION_EVENT.get(action, action.replace("_", " ").title() or "Recorded event")
        amount = _number(activity.get("Paper_Value")) * _scale_for(state)
        if action in {"PAPER_SELL_TO_SGOV", "PAPER_PARK_IN_SGOV", "EARNINGS_EXIT", "PAPER_EARNINGS_EXIT"}:
            from_location, to_location, next_action = "Stock Position", "SGOV", "Remain in SGOV"
        elif action in {"PAPER_BUY_OPEN", "PAPER_BUY_FROM_SGOV"}:
            from_location, to_location, next_action = "SGOV", "Stock Position", "Continue Holding"
        elif action == "PAPER_DIVIDEND_RECEIVED":
            from_location = to_location = "Stock Position"
            next_action = "Continue Holding"
        else:
            from_location = to_location = "Portfolio"
            next_action = "Review Event"

        rows.append(_row(
            activity_date=trading_date.isoformat(),
            original_pair=original_pair,
            pair=pair,
            event=event,
            stock=stock,
            from_location=from_location,
            to_location=to_location,
            amount=f"${amount:,.2f}",
            next_action=next_action,
        ))

    if not replacement_rows and not todays_events:
        rows.append(_row(
            activity_date=trading_date.isoformat(),
            event="No portfolio changes",
            next_action="No Action Required",
        ))

    return rows
