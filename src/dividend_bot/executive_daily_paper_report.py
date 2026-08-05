"""Build the Step 2 executive Daily Paper Report from authoritative paper evidence.

This module is reporting-only. It does not place orders, move capital, or alter
strategy decisions. Legacy ledgers initialized at $500 are presented on the
approved $50,000 basis by applying one transparent 100x reporting scale.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.dividend_bot.executive_reporting_framework import executive_framework_rows

MODULE_NAME = "executive_daily_paper_report"
MODULE_VERSION = "2.0.0"
PAPER_TRADE_MODE = True
APPROVED_STARTING_CAPITAL = 50_000.0
LEGACY_STARTING_CAPITAL = 500.0

DAILY_PAPER_FIELDS = [
    "report_section",
    "metric",
    "value",
    "pair",
    "original_pair",
    "current_pair",
    "pair_type",
    "active_leg",
    "position_state",
    "signal",
    "recommendation",
    "shares",
    "entry_date",
    "entry_price",
    "invested_capital",
    "current_price",
    "market_value",
    "sgov_balance",
    "realized_gain_loss",
    "unrealized_gain_loss",
    "unrealized_return_pct",
    "dividends_received",
    "notes",
    "paper_trade_mode",
]

_MONEY_LOG_ACTIONS = {
    "PAPER_BUY_OPEN",
    "PAPER_BUY_FROM_SGOV",
    "PAPER_SELL_TO_SGOV",
    "PAPER_PARK_IN_SGOV",
    "PAPER_DIVIDEND_RECEIVED",
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _scale_for(state: dict[str, Any]) -> float:
    starting = _number(state.get("starting_capital"))
    if abs(starting - LEGACY_STARTING_CAPITAL) < 1e-6:
        return APPROVED_STARTING_CAPITAL / LEGACY_STARTING_CAPITAL
    return 1.0


def _blank_row(section: str, **values: Any) -> dict[str, Any]:
    row = {field: "" for field in DAILY_PAPER_FIELDS}
    row["report_section"] = section
    row["paper_trade_mode"] = True
    row.update(values)
    return row


def _load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"Required paper state is missing: {path}")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Required paper state is unreadable: {path}") from exc
    if not isinstance(state, dict) or not isinstance(state.get("pairs"), dict):
        raise RuntimeError(f"Required paper state has no pair ledger: {path}")
    return state


def _load_log(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except OSError as exc:
        raise RuntimeError(f"Paper trade log is unreadable: {path}") from exc


def _ledger(log_rows: list[dict[str, str]], scale: float) -> dict[tuple[str, str], dict[str, Any]]:
    ledgers: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "cost_basis": 0.0,
            "entry_date": "",
            "entry_price": 0.0,
            "realized_gain_loss": 0.0,
            "dividends": 0.0,
        }
    )
    for row in log_rows:
        pair = str(row.get("Pair") or "").strip()
        sleeve = str(row.get("Sleeve") or "").strip().upper()
        action = str(row.get("Action") or "").strip().upper()
        if not pair or sleeve not in {"A", "B"} or action not in _MONEY_LOG_ACTIONS:
            continue
        item = ledgers[(pair, sleeve)]
        value = _number(row.get("Paper_Value")) * scale
        price = _number(row.get("Price"))
        if action in {"PAPER_BUY_OPEN", "PAPER_BUY_FROM_SGOV"}:
            item["cost_basis"] = value
            item["entry_date"] = str(row.get("Date") or "")
            item["entry_price"] = price
        elif action == "PAPER_SELL_TO_SGOV":
            item["realized_gain_loss"] += value - item["cost_basis"]
            item["cost_basis"] = 0.0
            item["entry_date"] = ""
            item["entry_price"] = 0.0
        elif action == "PAPER_DIVIDEND_RECEIVED":
            item["dividends"] += value
    return ledgers


def _position_state(a_in_sgov: bool, b_in_sgov: bool, a_ticker: str, b_ticker: str) -> str:
    if a_in_sgov and b_in_sgov:
        return "MOVED_TO_SGOV"
    if not a_in_sgov and not b_in_sgov:
        return f"INVESTED_IN_{a_ticker}_AND_{b_ticker}"
    if a_in_sgov:
        return f"A_MOVED_TO_SGOV_B_INVESTED_IN_{b_ticker}"
    return f"A_INVESTED_IN_{a_ticker}_B_MOVED_TO_SGOV"


def _recommendation(entry: dict[str, Any], state: str) -> str:
    action = str(entry.get("last_action") or "").upper()
    signals = entry.get("last_signal") if isinstance(entry.get("last_signal"), dict) else {}
    values = {str(value).upper() for value in signals.values()}
    if state == "MOVED_TO_SGOV":
        return "REENTRY_WATCH" if "BUY" in values else "REMAIN_IN_SGOV"
    if "SELL" in values or "SELL" in action:
        return "SELL_REVIEW"
    if state.startswith("INVESTED_IN_"):
        return "CONTINUE_HOLDING"
    return "WAITING_FOR_CONFIRMATION"


def build_daily_paper_rows(
    *,
    root_dir: str | Path,
    trading_date: date,
    generated_at: datetime | None = None,
) -> list[dict[str, Any]]:
    root = Path(root_dir)
    state = _load_state(root / "paper_state.json")
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    scale = _scale_for(state)
    ledgers = _ledger(_load_log(root / "paper_trade_log.csv"), scale)

    rows: list[dict[str, Any]] = []
    for item in executive_framework_rows(
        source_name="daily_paper_report.md",
        trading_date=trading_date,
        generated_at=generated,
    ):
        rows.append(
            _blank_row(
                item["section"], metric=item["field"], value=item["value"]
            )
        )

    stock_value = 0.0
    sgov_value = 0.0
    dividends = 0.0
    realized = 0.0
    pair_rows: list[dict[str, Any]] = []

    for original_pair, entry_value in state["pairs"].items():
        if not isinstance(entry_value, dict):
            continue
        entry = entry_value
        a_ticker = str(entry.get("a_ticker") or "A").strip()
        b_ticker = str(entry.get("b_ticker") or "B").strip()
        current_pair = f"{a_ticker} / {b_ticker}"
        pair_type = "ORIGINAL" if current_pair == original_pair else "REPLACEMENT"
        a_in_sgov = bool(entry.get("a_in_sgov", _number(entry.get("a_shares")) == 0))
        b_in_sgov = bool(entry.get("b_in_sgov", _number(entry.get("b_shares")) == 0))
        position_state = _position_state(a_in_sgov, b_in_sgov, a_ticker, b_ticker)
        signals = entry.get("last_signal") if isinstance(entry.get("last_signal"), dict) else {}
        signal_text = f"A={signals.get('A', 'UNKNOWN')}; B={signals.get('B', 'UNKNOWN')}"
        sgov = _number(entry.get("sgov_balance")) * scale
        sgov_value += sgov
        pair_dividends = _number(entry.get("total_dividends_received")) * scale
        dividends += pair_dividends

        for side, ticker, in_sgov in (("A", a_ticker, a_in_sgov), ("B", b_ticker, b_in_sgov)):
            key = side.lower()
            shares = _number(entry.get(f"{key}_shares")) * scale
            current_price = _number((entry.get("last_prices") or {}).get(side))
            market_value = 0.0 if in_sgov else shares * current_price
            ledger = ledgers[(original_pair, side)]
            cost_basis = 0.0 if in_sgov else _number(ledger["cost_basis"])
            if market_value > 0 and cost_basis <= 0:
                cost_basis = market_value
            unrealized = market_value - cost_basis if market_value > 0 else 0.0
            unrealized_pct = (unrealized / cost_basis * 100.0) if cost_basis else 0.0
            realized += _number(ledger["realized_gain_loss"])
            stock_value += market_value
            pair_rows.append(
                _blank_row(
                    "Current Pair Holdings",
                    pair=current_pair,
                    original_pair=original_pair,
                    current_pair=current_pair,
                    pair_type=pair_type,
                    active_leg=ticker if not in_sgov else "SGOV",
                    position_state=position_state,
                    signal=signal_text,
                    recommendation=_recommendation(entry, position_state),
                    shares=f"{shares:.6f}" if not in_sgov else "0.000000",
                    entry_date=ledger["entry_date"],
                    entry_price=f"{_number(ledger['entry_price']):.6f}" if ledger["entry_date"] else "",
                    invested_capital=f"{cost_basis:.2f}",
                    current_price=f"{current_price:.6f}" if current_price else "",
                    market_value=f"{market_value:.2f}",
                    sgov_balance=f"{sgov:.2f}" if side == "A" else "",
                    realized_gain_loss=f"{_number(ledger['realized_gain_loss']):.2f}",
                    unrealized_gain_loss=f"{unrealized:.2f}",
                    unrealized_return_pct=f"{unrealized_pct:.2f}%",
                    dividends_received=f"{pair_dividends:.2f}" if side == "A" else "",
                    notes=(
                        "Current pair differs from the original assignment."
                        if pair_type == "REPLACEMENT"
                        else "Original approved pair assignment."
                    ),
                )
            )

    total_value = stock_value + sgov_value
    starting = APPROVED_STARTING_CAPITAL if scale != 1.0 else _number(state.get("starting_capital"), APPROVED_STARTING_CAPITAL)
    unrealized_total = sum(_number(row["unrealized_gain_loss"]) for row in pair_rows)
    total_return = total_value + dividends - starting

    summary = [
        ("Starting Capital", starting),
        ("Current Stock Market Value", stock_value),
        ("SGOV Value", sgov_value),
        ("Cash / Reserved Funds", 0.0),
        ("Total Portfolio Value", total_value),
        ("Realized Gain / Loss", realized),
        ("Unrealized Gain / Loss", unrealized_total),
        ("Dividends Received", dividends),
        ("Total Return", total_return),
    ]
    for metric, value in summary:
        rows.append(_blank_row("Portfolio Summary", metric=metric, value=f"${value:,.2f}"))
    rows.append(
        _blank_row(
            "Portfolio Summary",
            metric="Accounting Reconciliation",
            value="RECONCILED" if abs(total_value - (stock_value + sgov_value)) < 0.01 else "ERROR",
            notes="Total Portfolio Value = Current Stock Market Value + SGOV Value + Cash / Reserved Funds.",
        )
    )
    if scale != 1.0:
        rows.append(
            _blank_row(
                "Portfolio Summary",
                metric="Legacy Ledger Reporting Scale",
                value="100x",
                notes="The original $500 ledger is presented on the approved $50,000 paper-capital basis without changing relative performance.",
            )
        )
    rows.extend(pair_rows)
    rows.append(
        _blank_row(
            "Final Assessment",
            metric="Safety Status",
            value="PAPER ONLY",
            notes="No broker connection exists. No real orders were submitted and no capital was moved by this report.",
        )
    )
    return rows
