"""Regression tests for the executive Strategy Health Report."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src.dividend_bot.executive_strategy_health_report import (
    STRATEGY_HEALTH_FIELDS,
    build_strategy_health_rows,
)


def _write_state(root: Path) -> None:
    state = {
        "paper_only": True,
        "as_of_date": "2026-08-05",
        "starting_capital": 500.0,
        "pairs": {
            "AMDW / BEX": {
                "original_pair": "AMDW / AMDL",
                "a_ticker": "AMDW", "b_ticker": "BEX",
                "a_shares": 2.0, "b_shares": 0.0,
                "a_in_sgov": False, "b_in_sgov": True,
                "sgov_balance": 20.0,
                "last_prices": {"A": 30.0, "B": 10.0},
                "last_signal": {"A": "BUY", "B": "SELL"},
                "last_action": "PAPER_SELL_TO_SGOV",
                "total_dividends_received": 1.0,
            },
            "MSTY / NVDY": {
                "a_ticker": "MSTY", "b_ticker": "NVDY",
                "a_shares": 0.0, "b_shares": 0.0,
                "a_in_sgov": True, "b_in_sgov": True,
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
        "2026-08-05,AMDW / BEX,A,AMDW,PAPER_DIVIDEND_RECEIVED,0,0,1\n"
        "2026-08-01,MSTY / NVDY,A,MSTY,PAPER_BUY_OPEN,1,10,10\n"
        "2026-08-01,MSTY / NVDY,B,NVDY,PAPER_BUY_OPEN,1,10,10\n"
        "2026-08-04,MSTY / NVDY,A,MSTY,PAPER_SELL_TO_SGOV,0,10,10\n"
        "2026-08-04,MSTY / NVDY,B,NVDY,PAPER_SELL_TO_SGOV,0,10,10\n",
        encoding="utf-8",
    )


def test_strategy_health_fields_are_stable() -> None:
    assert STRATEGY_HEALTH_FIELDS == [
        "activity_date", "report_section", "metric", "value", "pair",
        "active_stock", "event", "position_status", "portfolio_pct",
        "stock_value", "sgov_value", "total_pair_value",
        "total_return_amount", "total_return_pct", "days_invested",
        "dividends_received", "health_status", "explanation",
        "paper_trade_mode",
    ]


def test_current_legend_shows_active_symbol_warning_and_consolidated_sgov(tmp_path: Path) -> None:
    _write_state(tmp_path)
    rows = build_strategy_health_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    legends = [row for row in rows if row["report_section"] == "Current Pair Legend"]

    assert {row["pair"] for row in legends} == {"AMDW", "SGOV"}

    amd = next(row for row in legends if row["pair"] == "AMDW")
    assert amd["portfolio_pct"] == "12.00%"
    assert amd["total_pair_value"] == "$6,000.00"
    assert amd["value"] == "GROWTH PAIR REQUIRED — NEXT MAN UP"

    sgov = next(row for row in legends if row["pair"] == "SGOV")
    assert sgov["portfolio_pct"] == "8.00%"
    assert sgov["total_pair_value"] == "$4,000.00"
    assert sgov["value"] == "PARKED CAPITAL — AWAITING NEXT MAN UP"

    assert all(row["pair"] != "MSTY / NVDY" for row in legends)
    assert all("BEX" not in row["pair"] for row in legends)


def test_next_man_up_governance_flags_partial_and_fully_parked_pairs(tmp_path: Path) -> None:
    _write_state(tmp_path)
    rows = build_strategy_health_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    governance = [row for row in rows if row["report_section"] == "Pair Governance"]

    amd = next(row for row in governance if row["pair"] == "AMDW")
    assert amd["event"] == "NEXT MAN UP REQUIRED"
    assert amd["value"] == "GROWTH PAIR REQUIRED"
    assert amd["position_status"] == "INCOMPLETE INCOME + GROWTH PAIR"

    closed = next(row for row in governance if row["pair"] == "MSTY / NVDY")
    assert closed["active_stock"] == "SGOV"
    assert closed["position_status"] == "PAIR FULLY PARKED IN SGOV"
    assert closed["value"] == "NEW INCOME + GROWTH PAIR REQUIRED"


def test_fully_parked_pair_remains_in_grouped_history(tmp_path: Path) -> None:
    _write_state(tmp_path)
    rows = build_strategy_health_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    history = [row for row in rows if row["report_section"] == "Pair Performance"]
    msty = [row for row in history if row["pair"] == "MSTY / NVDY"]

    assert msty
    assert [row["activity_date"] for row in msty] == sorted(
        row["activity_date"] for row in msty
    )
    assert any(row["event"] == "MOVED INTO SGOV" for row in msty)


def test_income_growth_gate_requires_action(tmp_path: Path) -> None:
    _write_state(tmp_path)
    rows = build_strategy_health_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    gate = next(
        row for row in rows
        if row["report_section"] == "Deployment Gates"
        and row["metric"] == "Income + Growth Pair Governance"
    )
    assert gate["value"] == "ACTION REQUIRED"
    assert "Next Man Up" in gate["explanation"]


def test_blank_rows_separate_sections_and_pair_groups(tmp_path: Path) -> None:
    _write_state(tmp_path)
    rows = build_strategy_health_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    separators = [row for row in rows if not any(str(value) for value in row.values())]
    assert len(separators) >= 6
