"""Regression tests for the simplified Executive Daily Change Summary."""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from src.dividend_bot.executive_daily_change_summary import DAILY_CHANGE_FIELDS, build_daily_change_rows


def _write_evidence(root: Path) -> None:
    current = {
        "paper_only": True,
        "as_of_date": "2026-08-05",
        "starting_capital": 500.0,
        "pairs": {
            "AMDW / AMDL": {
                "a_ticker": "AMDW",
                "b_ticker": "BEX",
                "a_shares": 2.0,
                "b_shares": 0.0,
                "a_in_sgov": False,
                "b_in_sgov": True,
                "sgov_balance": 20.0,
                "last_prices": {"A": 30.0, "B": 10.0},
                "last_signal": {"A": "BUY", "B": "SELL"},
            }
        },
    }
    previous = {
        "paper_only": True,
        "as_of_date": "2026-08-04",
        "starting_capital": 500.0,
        "pairs": {
            "AMDW / AMDL": {
                "a_ticker": "AMDW",
                "b_ticker": "AMDL",
                "a_shares": 2.0,
                "b_shares": 1.0,
                "a_in_sgov": False,
                "b_in_sgov": False,
                "sgov_balance": 0.0,
                "last_prices": {"A": 28.0, "B": 20.0},
                "last_signal": {"A": "BUY", "B": "HOLD"},
            }
        },
    }
    (root / "paper_state.json").write_text(json.dumps(current), encoding="utf-8")
    (root / "paper_state_previous.json").write_text(json.dumps(previous), encoding="utf-8")
    with (root / "paper_trade_log.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "Date", "Pair", "Sleeve", "Signal", "Action", "Ticker", "Shares", "Price", "Paper_Value", "Reason"
        ])
        writer.writeheader()
        writer.writerow({
            "Date": "2026-08-05", "Pair": "AMDW / AMDL", "Sleeve": "B",
            "Signal": "SELL", "Action": "PAPER_SELL_TO_SGOV", "Ticker": "AMDL",
            "Shares": "1", "Price": "20", "Paper_Value": "20", "Reason": "replacement exit",
        })
        writer.writerow({
            "Date": "2026-08-05", "Pair": "AMDW / AMDL", "Sleeve": "A",
            "Signal": "BUY", "Action": "PAPER_DIVIDEND_RECEIVED", "Ticker": "AMDW",
            "Shares": "2", "Price": "30", "Paper_Value": "1", "Reason": "distribution received",
        })


def test_fields_are_simple_and_stock_level(tmp_path: Path):
    _write_evidence(tmp_path)
    assert DAILY_CHANGE_FIELDS == [
        "activity_date", "days_since", "report_section", "event", "original_pair",
        "current_pair", "stock", "from_location", "to_location", "amount", "signal",
        "next_action", "reason", "source", "paper_trade_mode",
    ]


def test_replacement_records_removed_and_added_stocks(tmp_path: Path):
    _write_evidence(tmp_path)
    rows = build_daily_change_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    changes = [row for row in rows if row["report_section"] == "Pair Changes"]
    removed = next(row for row in changes if row["stock"] == "AMDL")
    added = next(row for row in changes if row["stock"] == "BEX")
    assert removed["event"] == "REMOVED FROM PAIR AND MOVED TO SGOV"
    assert removed["from_location"] == "STOCK POSITION"
    assert removed["to_location"] == "SGOV"
    assert removed["amount"] == "2000.00"
    assert removed["next_action"] == "REPLACED BY BEX"
    assert added["event"] == "ADDED AS REPLACEMENT"
    assert added["to_location"] == "SGOV"
    assert added["next_action"] == "REMAIN IN SGOV"


def test_activity_rows_do_not_mix_amdw_buy_with_amdl_sale(tmp_path: Path):
    _write_evidence(tmp_path)
    rows = build_daily_change_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    events = [row for row in rows if row["report_section"] == "Today's Activity"]
    sold = next(row for row in events if row["event"] == "SOLD TO SGOV")
    dividend = next(row for row in events if row["event"] == "DIVIDEND RECEIVED")
    assert sold["stock"] == "AMDL"
    assert sold["signal"] == "SELL"
    assert sold["from_location"] == "STOCK POSITION"
    assert sold["to_location"] == "SGOV"
    assert sold["next_action"] == "REMAIN IN SGOV"
    assert dividend["stock"] == "AMDW"
    assert dividend["signal"] == "BUY"
    assert dividend["next_action"] == "CONTINUE HOLDING"


def test_next_day_plan_has_one_clear_row_per_stock(tmp_path: Path):
    _write_evidence(tmp_path)
    rows = build_daily_change_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    plans = [row for row in rows if row["report_section"] == "Next Trading Day"]
    assert len(plans) == 2
    amdw = next(row for row in plans if row["stock"] == "AMDW")
    bex = next(row for row in plans if row["stock"] == "BEX")
    assert amdw["from_location"] == "STOCK POSITION"
    assert amdw["signal"] == "BUY"
    assert amdw["next_action"] == "CONTINUE HOLDING"
    assert bex["from_location"] == "SGOV"
    assert bex["signal"] == "SELL"
    assert bex["next_action"] == "REMAIN IN SGOV"


def test_missing_previous_snapshot_is_disclosed_not_inferred(tmp_path: Path):
    _write_evidence(tmp_path)
    (tmp_path / "paper_state_previous.json").unlink()
    rows = build_daily_change_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    changes = [row for row in rows if row["report_section"] == "Portfolio Changes"]
    assert changes
    assert {row["from_location"] for row in changes} == {"NOT AVAILABLE"}
    assert all("no change was inferred" in row["reason"].lower() for row in changes)
