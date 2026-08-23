from __future__ import annotations

from src.dividend_bot.dividend_paper_trade_performance import (
    build_dividend_paper_trade_performance,
)
from src.dividend_bot.dividend_position_lifecycle import build_position_lifecycle


def _scaled_exit_rows() -> list[dict[str, str]]:
    return [
        {
            "Date": "2026-06-18",
            "Pair": "AMDW / AMDL",
            "Sleeve": "A",
            "Action": "PAPER_BUY_OPEN",
            "Ticker": "AMDW",
            "Shares": "0.4809013546",
            "Price": "109.169998",
            "Paper_Value": "52.5",
            "Reason": "Initial Strength Weighted allocation",
        },
        # Same economic initialization emitted by the later signal-aware pass.
        {
            "Date": "2026-06-18",
            "Pair": "AMDW / AMDL",
            "Sleeve": "A",
            "Action": "PAPER_BUY_OPEN",
            "Ticker": "AMDW",
            "Shares": "0.4809013546",
            "Price": "109.169998",
            "Paper_Value": "52.5",
            "Reason": "Signal-aware Strength Weighted initialization",
        },
        {
            "Date": "2026-08-18",
            "Pair": "AMDW / AMDL",
            "Sleeve": "A",
            "Action": "PAPER_SELL_TO_SGOV",
            "Ticker": "AMDW",
            "Shares": "4.809013546",
            "Price": "88.499",
            "Paper_Value": "425.59",
            "Reason": "Owner-authorized paper exit",
        },
    ]


def test_performance_uses_exit_share_quantity_to_reconcile_scaled_cost_basis() -> None:
    report = build_dividend_paper_trade_performance(_scaled_exit_rows())

    assert report["closed_trade_count"] == 1
    trade = report["closed_trades"][0]

    # $52.50 bought 0.4809013546 shares. Enterprise allocation later scaled
    # paper state 10x without rewriting that historical ledger row, so the
    # 4.809013546-share exit carries a $525.00 economic cost basis.
    assert round(trade["entry_value"], 2) == 525.00
    assert trade["cost_basis_method"] == "ENTRY_UNIT_COST_X_EXIT_SHARES"
    assert round(trade["exit_value"], 2) == 425.59
    assert round(trade["pnl"], 2) == -99.41
    assert trade["outcome"] == "LOSS"


def test_lifecycle_collapses_duplicate_initialization_and_reconciles_scaled_exit() -> None:
    lifecycle = build_position_lifecycle(_scaled_exit_rows(), [])
    record = lifecycle[0]

    assert record["symbol"] == "AMDW"
    assert record["lifecycle_status"] == "PARKED_IN_SGOV"
    assert record["event_count"] == 2
    assert record["entry_value"] == 525.00
    assert record["last_exit_value"] == 425.59
    assert record["realized_gain_loss"] == -99.41
    assert record["realized_cost_basis_method"] == "ENTRY_UNIT_COST_X_EXIT_SHARES"


def test_unscaled_trade_keeps_identical_economic_result() -> None:
    rows = [
        {
            "Date": "2026-06-18", "Pair": "AAA / BBB", "Sleeve": "A",
            "Action": "PAPER_BUY_OPEN", "Ticker": "AAA",
            "Shares": "1", "Price": "100", "Paper_Value": "100",
        },
        {
            "Date": "2026-06-26", "Pair": "AAA / BBB", "Sleeve": "A",
            "Action": "PAPER_SELL_TO_SGOV", "Ticker": "AAA",
            "Shares": "1", "Price": "125", "Paper_Value": "125",
        },
    ]

    performance = build_dividend_paper_trade_performance(rows)
    lifecycle = build_position_lifecycle(rows, [])

    assert performance["closed_trades"][0]["pnl"] == 25.0
    assert lifecycle[0]["realized_gain_loss"] == 25.0
