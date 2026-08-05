"""Regression tests for Step 2 executive Daily Paper Report accounting."""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from src.dividend_bot.executive_daily_paper_report import (
    DAILY_PAPER_FIELDS,
    build_daily_paper_rows,
)


def _write_state(root: Path) -> None:
    state = {
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
                "last_action": "NO_PAPER_TRADE",
                "total_dividends_received": 1.0,
            }
        },
    }
    (root / "paper_state.json").write_text(json.dumps(state), encoding="utf-8")
    with (root / "paper_trade_log.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Date", "Pair", "Sleeve", "Signal", "Action", "Ticker", "Shares", "Price", "Paper_Value", "Reason"],
        )
        writer.writeheader()
        writer.writerow({
            "Date": "2026-08-01", "Pair": "AMDW / AMDL", "Sleeve": "A",
            "Signal": "BUY", "Action": "PAPER_BUY_OPEN", "Ticker": "AMDW",
            "Shares": "2", "Price": "25", "Paper_Value": "50", "Reason": "test",
        })
        writer.writerow({
            "Date": "2026-08-04", "Pair": "AMDW / AMDL", "Sleeve": "B",
            "Signal": "SELL", "Action": "PAPER_SELL_TO_SGOV", "Ticker": "BEX",
            "Shares": "0", "Price": "10", "Paper_Value": "20", "Reason": "test sale",
        })


def test_legacy_ledger_is_presented_on_approved_fifty_thousand_basis(tmp_path: Path):
    _write_state(tmp_path)
    rows = build_daily_paper_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    summary = {row["metric"]: row["value"] for row in rows if row["report_section"] == "Portfolio Summary"}
    assert summary["Starting Capital"] == "$50,000.00"
    assert summary["Current Stock Market Value"] == "$6,000.00"
    assert summary["SGOV Value"] == "$2,000.00"
    assert summary["Cash / Reserved Funds"] == "$42,000.00"
    assert summary["Total Portfolio Value"] == "$50,000.00"
    assert summary["Accounting Reconciliation"] == "RECONCILED"
    assert summary["Legacy Ledger Reporting Scale"] == "100x"


def test_pair_rows_show_original_replacement_and_real_position_state(tmp_path: Path):
    _write_state(tmp_path)
    rows = build_daily_paper_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    holdings = [row for row in rows if row["report_section"] == "Current Pair Holdings"]
    assert len(holdings) == 2
    assert {row["pair"] for row in holdings} == {"AMDW / BEX"}
    assert {row["original_pair"] for row in holdings} == {"AMDW / AMDL"}
    assert {row["pair_type"] for row in holdings} == {"REPLACEMENT"}
    assert {row["position_state"] for row in holdings} == {"A_INVESTED_IN_AMDW_B_MOVED_TO_SGOV"}
    assert {row["recommendation"] for row in holdings} == {"SELL_REVIEW"}


def test_invested_leg_has_cost_basis_and_uninvested_leg_is_not_hold(tmp_path: Path):
    _write_state(tmp_path)
    rows = build_daily_paper_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    holdings = [row for row in rows if row["report_section"] == "Current Pair Holdings"]
    invested = next(row for row in holdings if row["active_leg"] == "AMDW")
    parked = next(row for row in holdings if row["active_leg"] == "SGOV")
    assert invested["invested_capital"] == "5000.00"
    assert invested["market_value"] == "6000.00"
    assert invested["unrealized_gain_loss"] == "1000.00"
    assert parked["invested_capital"] == "0.00"
    assert parked["recommendation"] != "CONTINUE_HOLDING"


def test_last_activity_is_first_and_expanded_audit_fields_are_reported(tmp_path: Path):
    _write_state(tmp_path)
    rows = build_daily_paper_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    holdings = [row for row in rows if row["report_section"] == "Current Pair Holdings"]
    invested = next(row for row in holdings if row["active_leg"] == "AMDW")
    parked = next(row for row in holdings if row["active_leg"] == "SGOV")

    assert DAILY_PAPER_FIELDS[0] == "last_activity"
    assert DAILY_PAPER_FIELDS[1] == "days_since"
    assert invested["last_activity"] == "2026-08-01"
    assert invested["days_since"] == "4"
    assert invested["last_event"] == "POSITION CREATED"
    assert parked["last_activity"] == "2026-08-04"
    assert parked["days_since"] == "1"
    assert parked["last_event"] == "SOLD AND MOVED TO SGOV"
    assert invested["portfolio_pct"] == "12.00%"
    assert parked["portfolio_pct"] == "4.00%"
    assert "todays_dividend" in invested
    assert "total_dividends" in invested
