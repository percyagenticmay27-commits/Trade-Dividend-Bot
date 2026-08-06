"""Regression tests for the executive Live Readiness Report."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src.dividend_bot.executive_live_readiness_report import build_live_readiness_rows


def _write_inputs(root: Path) -> None:
    state = {
        "paper_only": True,
        "as_of_date": "2026-08-05",
        "starting_capital": 500.0,
        "pairs": {
            "AMDW / BEX": {
                "original_pair": "AMDW / AMDL",
                "a_ticker": "AMDW",
                "b_ticker": "BEX",
                "a_shares": 2.0,
                "b_shares": 0.0,
                "a_in_sgov": False,
                "b_in_sgov": True,
                "sgov_balance": 20.0,
                "last_prices": {"A": 30.0, "B": 10.0},
                "last_signal": {"A": "BUY", "B": "SELL"},
                "last_action": "PAPER_SELL_TO_SGOV",
                "total_dividends_received": 1.0,
            },
            "MSTY / NVDY": {
                "a_ticker": "MSTY",
                "b_ticker": "NVDY",
                "a_shares": 0.0,
                "b_shares": 0.0,
                "a_in_sgov": True,
                "b_in_sgov": True,
                "sgov_balance": 20.0,
                "last_prices": {"A": 10.0, "B": 10.0},
                "last_signal": {"A": "SELL", "B": "SELL"},
                "last_action": "PAPER_SELL_TO_SGOV",
                "total_dividends_received": 0.0,
            },
        },
    }
    (root / "paper_state.json").write_text(json.dumps(state), encoding="utf-8")
    (root / "paper_trade_log.csv").write_text(
        "Date,Pair,Sleeve,Ticker,Action,Shares,Price,Paper_Value\n"
        "2026-08-01,AMDW / BEX,A,AMDW,PAPER_BUY_OPEN,2,25,50\n"
        "2026-08-04,AMDW / BEX,B,BEX,PAPER_SELL_TO_SGOV,0,10,20\n"
        "2026-08-01,MSTY / NVDY,A,MSTY,PAPER_BUY_OPEN,1,10,10\n"
        "2026-08-01,MSTY / NVDY,B,NVDY,PAPER_BUY_OPEN,1,10,10\n"
        "2026-08-04,MSTY / NVDY,A,MSTY,PAPER_SELL_TO_SGOV,0,10,10\n"
        "2026-08-04,MSTY / NVDY,B,NVDY,PAPER_SELL_TO_SGOV,0,10,10\n",
        encoding="utf-8",
    )
    (root / "live_readiness_report.md").write_text(
        "# Live Readiness Report\n"
        "- Overall Readiness: 78.00%\n"
        "- Status: IN PROGRESS\n"
        "- Paper Trading Days: 47\n"
        "- Required Paper Days: 90\n"
        "- Days Remaining: 43\n"
        "- Maximum Drawdown: 3.18%\n"
        "- Accounting Status: RECONCILED\n",
        encoding="utf-8",
    )


def _governance(rows: list[dict]) -> dict[str, dict]:
    return {
        row["metric"]: row
        for row in rows
        if row["report_section"] == "Governance Readiness"
    }


def test_only_active_incomplete_pair_counts_for_veto_and_next_man_up(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    rows = build_live_readiness_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    governance = _governance(rows)

    assert governance["Pairs Requiring Investor Veto"]["value"] == "1"
    assert governance["Next Man Up Candidates"]["value"] == "1"
    assert governance["Incomplete Income + Growth Pairs"]["value"] == "1"
    assert "fully parked pairs are excluded" in governance["Incomplete Income + Growth Pairs"]["notes"]


def test_governance_allocation_reconciles_to_one_hundred_percent(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    rows = build_live_readiness_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    governance = _governance(rows)

    assert governance["Current Active Stock Allocation"]["value"] == "12.00%"
    assert governance["Current SGOV Allocation"]["value"] == "8.00%"
    assert governance["Capital Allocation"]["value"] == "80.00%"
    assert governance["Total Accounted Allocation"]["value"] == "100.00%"


def test_current_readiness_summary_includes_total_percent_return(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    rows = build_live_readiness_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    summary = {
        row["metric"]: row["value"]
        for row in rows
        if row["report_section"] == "Current Readiness Summary"
    }

    assert "Total % Return" in summary
    assert "Maximum Gain/Loss Percent" not in summary
