from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.dividend_paper_trade_performance import (
    build_dividend_paper_trade_performance,
    write_dividend_paper_trade_performance,
)


def test_reconstructs_closed_round_trips_and_realized_win_rate() -> None:
    rows = [
        {"Date": "2026-06-18", "Pair": "AAA / BBB", "Sleeve": "A", "Action": "PAPER_BUY_OPEN", "Ticker": "AAA", "Paper_Value": "42.0"},
        {"Date": "2026-06-18", "Pair": "CCC / DDD", "Sleeve": "A", "Action": "PAPER_BUY_OPEN", "Ticker": "CCC", "Paper_Value": "40.0"},
        {"Date": "2026-06-20", "Pair": "CCC / DDD", "Sleeve": "A", "Action": "PAPER_DIVIDEND_RECEIVED", "Ticker": "CCC", "Paper_Value": "4.0"},
        {"Date": "2026-06-26", "Pair": "AAA / BBB", "Sleeve": "A", "Action": "PAPER_SELL_TO_SGOV", "Ticker": "AAA", "Paper_Value": "35.0"},
        {"Date": "2026-06-26", "Pair": "CCC / DDD", "Sleeve": "A", "Action": "PAPER_SELL_TO_SGOV", "Ticker": "CCC", "Paper_Value": "39.0"},
    ]

    report = build_dividend_paper_trade_performance(rows, generated_at_utc="2026-08-07T00:00:00Z")

    assert report["strategy_id"] == "DIVIDEND-001"
    assert report["closed_trade_count"] == 2
    assert report["win_count"] == 0
    assert report["loss_count"] == 2
    assert report["win_rate_percent"] == 0.0

    dividend_trade = report["closed_trades"][1]
    assert dividend_trade["income_received"] == 2.0
    assert dividend_trade["entry_value"] == 40.0
    assert dividend_trade["exit_value"] == 39.0
    assert dividend_trade["realized_value"] == 39.0
    assert dividend_trade["pnl"] == -1.0
    assert dividend_trade["outcome"] == "LOSS"
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False


def test_reentry_is_new_open_round_trip() -> None:
    rows = [
        {"Date": "2026-06-18", "Pair": "AAA / BBB", "Sleeve": "A", "Action": "PAPER_BUY_OPEN", "Ticker": "AAA", "Paper_Value": "42.0"},
        {"Date": "2026-06-26", "Pair": "AAA / BBB", "Sleeve": "A", "Action": "PAPER_SELL_TO_SGOV", "Ticker": "AAA", "Paper_Value": "35.0"},
        {"Date": "2026-08-06", "Pair": "AAA / BBB", "Sleeve": "A", "Action": "PAPER_BUY_FROM_SGOV", "Ticker": "AAA", "Paper_Value": "36.0"},
    ]

    report = build_dividend_paper_trade_performance(rows)
    assert report["closed_trade_count"] == 1
    assert report["open_trade_count"] == 1
    assert report["win_rate_percent"] == 0.0


def test_no_closed_trades_does_not_fabricate_win_rate() -> None:
    rows = [
        {"Date": "2026-08-06", "Pair": "AAA / BBB", "Sleeve": "A", "Action": "PAPER_BUY_FROM_SGOV", "Ticker": "AAA", "Paper_Value": "36.0"},
    ]
    report = build_dividend_paper_trade_performance(rows)
    assert report["closed_trade_count"] == 0
    assert report["win_rate_percent"] is None
    assert report["evidence_status"] == "INSUFFICIENT_DATA"


def test_writer_publishes_service_level_dividend_performance(tmp_path: Path) -> None:
    log = tmp_path / "paper_trade_log.csv"
    log.write_text(
        "Date,Pair,Sleeve,Signal,Action,Ticker,Shares,Price,Paper_Value,Reason\n"
        "2026-06-18,AAA / BBB,A,HOLD,PAPER_BUY_OPEN,AAA,1,42,42,open\n"
        "2026-06-26,AAA / BBB,A,SELL,PAPER_SELL_TO_SGOV,AAA,1,45,45,exit\n",
        encoding="utf-8",
    )
    path = write_dividend_paper_trade_performance(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["strategy_id"] == "DIVIDEND-001"
    assert data["win_rate_percent"] == 100.0
    assert data["order_placement_enabled"] is False
    assert data["capital_movement_enabled"] is False
    assert data["automatic_activation_allowed"] is False


def test_administrative_capital_scaling_does_not_create_fake_realized_profit():
    rows = [
        {
            "Date": "2026-06-18",
            "Pair": "AAA / BBB",
            "Sleeve": "A",
            "Action": "PAPER_BUY_OPEN",
            "Ticker": "AAA",
            "Paper_Value": "50.0",
        },
        {
            "Date": "2026-08-18",
            "Pair": "AAA / BBB",
            "Sleeve": "A",
            "Action": "PAPER_SELL_TO_SGOV",
            "Ticker": "AAA",
            "Paper_Value": "500.0",
        },
    ]

    state = {
        "starting_capital": 5000.0,
        "enterprise_capital_contract_amount": 5000.0,
        "enterprise_capital_scale_factor": 10.0,
        "enterprise_capital_contract_applied": True,
        "enterprise_capital_contract_effective_date": "2026-08-08",
        "pairs": {
            "AAA / BBB": {
                "a_shares": 0.0,
                "b_shares": 0.0,
                "sgov_balance": 500.0,
            }
        },
    }

    report = build_dividend_paper_trade_performance(
        rows,
        paper_state=state,
    )

    assert report["closed_trade_count"] == 1
    assert report["closed_trades"][0]["entry_value"] == 500.0
    assert report["closed_trades"][0]["exit_value"] == 500.0
    assert report["closed_trades"][0]["pnl"] == 0.0
    assert report["closed_trades"][0]["total_return_pct"] == 0.0


def test_authoritative_current_state_blocks_stale_historical_open_trade():
    rows = [
        {
            "Date": "2026-06-18",
            "Pair": "AAA / BBB",
            "Sleeve": "A",
            "Action": "PAPER_BUY_OPEN",
            "Ticker": "AAA",
            "Paper_Value": "50.0",
        },
    ]

    state = {
        "pairs": {
            "AAA / BBB": {
                "a_shares": 0.0,
                "b_shares": 0.0,
                "sgov_balance": 500.0,
            }
        },
    }

    report = build_dividend_paper_trade_performance(
        rows,
        paper_state=state,
    )

    assert report["open_trade_count"] == 0
    assert report["open_trades"] == []


def test_without_current_state_legacy_behavior_is_preserved():
    rows = [
        {
            "Date": "2026-08-20",
            "Pair": "AAA / BBB",
            "Sleeve": "A",
            "Action": "PAPER_BUY_FROM_SGOV",
            "Ticker": "AAA",
            "Paper_Value": "500.0",
        },
    ]

    report = build_dividend_paper_trade_performance(rows)

    assert report["open_trade_count"] == 1
    assert report["open_trades"][0]["entry_value"] == 500.0


def test_reinvested_dividend_is_reported_but_not_double_counted_in_realized_pnl():
    rows = [
        {
            "Date": "2026-06-18",
            "Pair": "AAA / BBB",
            "Sleeve": "A",
            "Action": "PAPER_BUY_OPEN",
            "Ticker": "AAA",
            "Paper_Value": "50.0",
        },
        {
            "Date": "2026-06-22",
            "Pair": "AAA / BBB",
            "Sleeve": "A",
            "Action": "PAPER_DIVIDEND_RECEIVED",
            "Ticker": "AAA",
            "Paper_Value": "10.0",
        },
        {
            "Date": "2026-08-18",
            "Pair": "AAA / BBB",
            "Sleeve": "A",
            "Action": "PAPER_SELL_TO_SGOV",
            "Ticker": "AAA",
            "Paper_Value": "450.0",
        },
    ]

    state = {
        "enterprise_capital_contract_applied": True,
        "enterprise_capital_scale_factor": 10.0,
        "enterprise_capital_contract_effective_date": "2026-08-08",
        "pairs": {
            "AAA / BBB": {
                "a_shares": 0.0,
                "b_shares": 0.0,
                "sgov_balance": 450.0,
            }
        },
    }

    report = build_dividend_paper_trade_performance(
        rows,
        paper_state=state,
    )

    trade = report["closed_trades"][0]

    assert trade["entry_value"] == 500.0
    assert trade["income_received"] == 5.0
    assert trade["exit_value"] == 450.0
    assert trade["realized_value"] == 450.0
    assert trade["pnl"] == -50.0
    assert trade["total_return_pct"] == -10.0


def test_trade_closed_before_capital_normalization_keeps_original_basis():
    rows = [
        {
            "Date": "2026-06-18",
            "Pair": "AAA / BBB",
            "Sleeve": "A",
            "Action": "PAPER_BUY_OPEN",
            "Ticker": "AAA",
            "Paper_Value": "42.0",
        },
        {
            "Date": "2026-06-26",
            "Pair": "AAA / BBB",
            "Sleeve": "A",
            "Action": "PAPER_SELL_TO_SGOV",
            "Ticker": "AAA",
            "Paper_Value": "35.0",
        },
    ]

    state = {
        "enterprise_capital_contract_applied": True,
        "enterprise_capital_scale_factor": 10.0,
        "enterprise_capital_contract_effective_date": "2026-08-08",
        "pairs": {
            "AAA / BBB": {
                "a_shares": 0.0,
                "b_shares": 0.0,
            }
        },
    }

    report = build_dividend_paper_trade_performance(
        rows,
        paper_state=state,
    )

    trade = report["closed_trades"][0]

    assert trade["entry_value"] == 42.0
    assert trade["exit_value"] == 35.0
    assert trade["pnl"] == -7.0
    assert trade["total_return_pct"] == -16.6667


def test_trade_crossing_capital_normalization_normalizes_legacy_entry_only():
    rows = [
        {
            "Date": "2026-06-18",
            "Pair": "AAA / BBB",
            "Sleeve": "A",
            "Action": "PAPER_BUY_OPEN",
            "Ticker": "AAA",
            "Paper_Value": "50.0",
        },
        {
            "Date": "2026-08-18",
            "Pair": "AAA / BBB",
            "Sleeve": "A",
            "Action": "PAPER_SELL_TO_SGOV",
            "Ticker": "AAA",
            "Paper_Value": "450.0",
        },
    ]

    state = {
        "enterprise_capital_contract_applied": True,
        "enterprise_capital_scale_factor": 10.0,
        "enterprise_capital_contract_effective_date": "2026-08-08",
        "pairs": {
            "AAA / BBB": {
                "a_shares": 0.0,
                "b_shares": 0.0,
            }
        },
    }

    report = build_dividend_paper_trade_performance(
        rows,
        paper_state=state,
    )

    trade = report["closed_trades"][0]

    assert trade["entry_value"] == 500.0
    assert trade["exit_value"] == 450.0
    assert trade["pnl"] == -50.0


def test_post_normalization_entry_is_not_scaled_again():
    rows = [
        {
            "Date": "2026-08-10",
            "Pair": "AAA / BBB",
            "Sleeve": "A",
            "Action": "PAPER_BUY_FROM_SGOV",
            "Ticker": "AAA",
            "Paper_Value": "500.0",
        },
        {
            "Date": "2026-08-18",
            "Pair": "AAA / BBB",
            "Sleeve": "A",
            "Action": "PAPER_SELL_TO_SGOV",
            "Ticker": "AAA",
            "Paper_Value": "550.0",
        },
    ]

    state = {
        "enterprise_capital_contract_applied": True,
        "enterprise_capital_scale_factor": 10.0,
        "enterprise_capital_contract_effective_date": "2026-08-08",
        "pairs": {
            "AAA / BBB": {
                "a_shares": 0.0,
                "b_shares": 0.0,
            }
        },
    }

    report = build_dividend_paper_trade_performance(
        rows,
        paper_state=state,
    )

    trade = report["closed_trades"][0]

    assert trade["entry_value"] == 500.0
    assert trade["exit_value"] == 550.0
    assert trade["pnl"] == 50.0
