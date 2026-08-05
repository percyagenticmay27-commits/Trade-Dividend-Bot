"""Regression tests for the Step 3 Executive Daily Change Summary."""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from src.dividend_bot.executive_daily_change_summary import (
    DAILY_CHANGE_FIELDS,
    build_daily_change_rows,
)


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
                "b_ticker": "BEX",
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
            "Signal": "SELL", "Action": "PAPER_SELL_TO_SGOV", "Ticker": "BEX",
            "Shares": "1", "Price": "20", "Paper_Value": "20", "Reason": "signal exit",
        })
        writer.writerow({
            "Date": "2026-08-05", "Pair": "AMDW / AMDL", "Sleeve": "A",
            "Signal": "BUY", "Action": "PAPER_DIVIDEND_RECEIVED", "Ticker": "AMDW",
            "Shares": "2", "Price": "30", "Paper_Value": "1", "Reason": "distribution received",
        })


def test_step3_fields_begin_with_activity_audit_columns(tmp_path: Path):
    _write_evidence(tmp_path)
    assert DAILY_CHANGE_FIELDS[:4] == [
        "activity_date", "days_since", "report_section", "change_category"
    ]


def test_portfolio_changes_compare_current_and_previous_snapshots(tmp_path: Path):
    _write_evidence(tmp_path)
    rows = build_daily_change_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    changes = {row["change_category"]: row for row in rows if row["report_section"] == "Portfolio Changes"}
    assert changes["CURRENT STOCK MARKET VALUE"]["previous_value"] == "7600.00"
    assert changes["CURRENT STOCK MARKET VALUE"]["current_value"] == "6000.00"
    assert changes["SGOV VALUE"]["previous_value"] == "0.00"
    assert changes["SGOV VALUE"]["current_value"] == "2000.00"


def test_daily_events_distinguish_sell_to_sgov_and_dividend(tmp_path: Path):
    _write_evidence(tmp_path)
    rows = build_daily_change_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    events = [row for row in rows if row["report_section"] == "Daily Events"]
    sold = next(row for row in events if row["change_category"] == "SGOV MOVEMENT")
    dividend = next(row for row in events if row["change_category"] == "DIVIDEND")
    assert sold["current_pair"] == "AMDW / BEX"
    assert sold["original_pair"] == "AMDW / AMDL"
    assert sold["stock_moved"] == "BEX"
    assert sold["amount"] == "2000.00"
    assert sold["required_action"] == "SELL_REVIEW"
    assert dividend["stock"] == "AMDW"
    assert dividend["amount"] == "100.00"


def test_next_day_rows_use_full_pair_and_noncontradictory_action(tmp_path: Path):
    _write_evidence(tmp_path)
    rows = build_daily_change_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    next_rows = [row for row in rows if row["report_section"] == "Next Trading Day"]
    assert len(next_rows) == 1
    row = next_rows[0]
    assert row["current_pair"] == "AMDW / BEX"
    assert row["original_pair"] == "AMDW / AMDL"
    assert row["signal"] == "A=BUY; B=SELL"
    assert row["required_action"] == "SELL_REVIEW"
    assert row["next_day_action"] == "SELL_REVIEW"
    assert row["current_state"] == "A_INVESTED_IN_AMDW_B_MOVED_TO_SGOV"


def test_missing_previous_snapshot_is_disclosed_not_inferred(tmp_path: Path):
    _write_evidence(tmp_path)
    (tmp_path / "paper_state_previous.json").unlink()
    rows = build_daily_change_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    changes = [row for row in rows if row["report_section"] == "Portfolio Changes"]
    assert changes
    assert {row["previous_value"] for row in changes} == {"NOT AVAILABLE"}
    assert all("no change was inferred" in row["reason"].lower() for row in changes)
