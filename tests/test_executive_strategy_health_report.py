"""Regression tests for the Step 4 executive Strategy Health Report."""
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
            }
        },
    }
    (root / "paper_state.json").write_text(json.dumps(state), encoding="utf-8")
    (root / "paper_trade_log.csv").write_text(
        "Date,Pair,Sleeve,Ticker,Action,Shares,Price,Paper_Value\n"
        "2026-08-01,AMDW / BEX,A,AMDW,PAPER_BUY_OPEN,2,25,50\n"
        "2026-08-04,AMDW / BEX,B,BEX,PAPER_SELL_TO_SGOV,0,10,20\n"
        "2026-08-05,AMDW / BEX,A,AMDW,PAPER_DIVIDEND_RECEIVED,0,0,1\n",
        encoding="utf-8",
    )


def _portfolio_metrics(rows: list[dict]) -> dict[str, str]:
    return {
        row["metric"]: row["value"]
        for row in rows
        if row["report_section"] == "Portfolio Health"
    }


def test_strategy_health_fields_are_stable() -> None:
    assert STRATEGY_HEALTH_FIELDS == [
        "activity_date",
        "report_section",
        "metric",
        "value",
        "pair",
        "active_stock",
        "event",
        "position_status",
        "portfolio_pct",
        "stock_value",
        "sgov_value",
        "total_pair_value",
        "total_return_amount",
        "total_return_pct",
        "days_invested",
        "dividends_received",
        "health_status",
        "explanation",
        "paper_trade_mode",
    ]


def test_strategy_health_reports_total_capital_pair_status_and_units(tmp_path: Path) -> None:
    _write_state(tmp_path)
    rows = build_strategy_health_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))

    metrics = _portfolio_metrics(rows)
    assert metrics["Starting Capital"] == "$50,000.00"
    assert metrics["Dividends Received"] == "$100.00"
    assert metrics["Total Return Amount"] == "$3,100.00"
    assert metrics["Total Return Percent"] == "6.20%"
    assert metrics["Total Portfolio Value"] == "$53,100.00"

    legend = next(row for row in rows if row["report_section"] == "Current Pair Legend")
    assert legend["activity_date"] == "2026-08-05"
    assert legend["pair"] == "AMDW / BEX"
    assert legend["portfolio_pct"] == "16.00%"
    assert legend["total_pair_value"] == "$8,000.00"
    assert legend["active_stock"] == ""
    assert legend["position_status"] == ""

    history = [row for row in rows if row["report_section"] == "Pair Performance"]
    assert [row["activity_date"] for row in history] == [
        "2026-08-01",
        "2026-08-04",
        "2026-08-05",
    ]
    assert history[0]["pair"] == "AMDW / BEX"
    assert history[0]["active_stock"] == "AMDW"
    assert history[1]["active_stock"] == "SGOV"
    assert history[2]["active_stock"] == "AMDW"
    assert all(row["paper_trade_mode"] is True for row in history)


def test_legend_is_concise_and_history_has_no_state_column(tmp_path: Path) -> None:
    _write_state(tmp_path)
    rows = build_strategy_health_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    legend = next(row for row in rows if row["report_section"] == "Current Pair Legend")

    populated = {
        key for key, value in legend.items()
        if value not in {"", False}
    }
    assert populated == {
        "activity_date",
        "report_section",
        "pair",
        "portfolio_pct",
        "total_pair_value",
        "paper_trade_mode",
    }
    assert "state" not in STRATEGY_HEALTH_FIELDS


def test_blank_rows_separate_executive_sections_and_pair_groups(tmp_path: Path) -> None:
    _write_state(tmp_path)
    rows = build_strategy_health_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    separators = [row for row in rows if not any(str(value) for value in row.values())]
    assert len(separators) >= 5


def test_deployment_gates_are_plain_english(tmp_path: Path) -> None:
    _write_state(tmp_path)
    rows = build_strategy_health_rows(root_dir=tmp_path, trading_date=date(2026, 8, 5))
    gates = [row for row in rows if row["report_section"] == "Deployment Gates"]

    assert {row["metric"] for row in gates} == {
        "Accounting Reconciliation",
        "Paper-Trading Safety",
        "Minimum Observation History",
        "Risk and Drawdown Review",
    }
    assert all(row["explanation"] for row in gates)
    assert all(row["value"] in {"PASS", "IN PROGRESS", "REVIEW REQUIRED"} for row in gates)
