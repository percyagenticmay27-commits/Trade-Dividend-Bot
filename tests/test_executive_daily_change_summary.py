"""Regression tests for the final simplified Daily Change Summary."""
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


def test_fields_match_final_nine_column_design(tmp_path: Path):
    _write_evidence(tmp_path)
    assert DAILY_CHANGE_FIELDS == [
        "activity_date", "original_pair", "pair", "event", "stock",
        "from_location", "to_location", "amount", "next_action",
    ]


def test_replacement_records_old_and_new_pair_rows(tmp_path: Path):
    _write_evidence(tmp_path)
    rows = build_daily_change_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    removed = next(row for row in rows if row["event"] == "Removed from pair and moved to SGOV")
    added = next(row for row in rows if row["event"] == "Added as replacement")

    assert removed == {
        "activity_date": "2026-08-05",
        "original_pair": "AMDW/AMDL",
        "pair": "AMDW/AMDL",
        "event": "Removed from pair and moved to SGOV",
        "stock": "AMDL",
        "from_location": "Stock Position",
        "to_location": "SGOV",
        "amount": "$2,000.00",
        "next_action": "Replaced by BEX",
    }
    assert added == {
        "activity_date": "2026-08-05",
        "original_pair": "AMDW/AMDL",
        "pair": "AMDW/BEX",
        "event": "Added as replacement",
        "stock": "BEX",
        "from_location": "Not in Current Pair",
        "to_location": "SGOV",
        "amount": "$0.00",
        "next_action": "Remain in SGOV",
    }


def test_replacement_sale_is_not_duplicated(tmp_path: Path):
    _write_evidence(tmp_path)
    rows = build_daily_change_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    amdl_rows = [row for row in rows if row["stock"] == "AMDL"]
    assert len(amdl_rows) == 1
    assert amdl_rows[0]["event"] == "Removed from pair and moved to SGOV"


def test_unrelated_dividend_remains_a_separate_simple_event(tmp_path: Path):
    _write_evidence(tmp_path)
    rows = build_daily_change_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    dividend = next(row for row in rows if row["event"] == "Dividend received")
    assert dividend["stock"] == "AMDW"
    assert dividend["pair"] == "AMDW/BEX"
    assert dividend["from_location"] == "Stock Position"
    assert dividend["to_location"] == "Stock Position"
    assert dividend["amount"] == "$100.00"
    assert dividend["next_action"] == "Continue Holding"


def test_no_changes_produces_one_clear_status_row(tmp_path: Path):
    _write_evidence(tmp_path)
    (tmp_path / "paper_state_previous.json").unlink()
    (tmp_path / "paper_trade_log.csv").unlink()
    rows = build_daily_change_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    status = next(row for row in rows if row["event"] == "No portfolio changes")
    assert status["activity_date"] == "2026-08-05"
    assert status["next_action"] == "No Action Required"
