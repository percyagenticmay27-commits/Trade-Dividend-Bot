import json

from src.dividend_bot.dividend_enterprise_capital_contract import (
    read_enterprise_dividend_allocation,
    scale_paper_state_to_allocation,
)
from src.dividend_bot.dividend_income_analytics import enrich_holdings_with_income_analytics
from src.dividend_bot.dividend_position_lifecycle import build_position_lifecycle
from src.dividend_bot.enterprise_position_history_ui import render_position_history_panel


def test_enterprise_capital_contract_reads_dividend_allocation_and_scales_state(tmp_path):
    cash = tmp_path / "paper_cash_account.json"
    cash.write_text(json.dumps({"strategy_allocations": {"DIVIDEND-001": 5000.0}}), encoding="utf-8")
    assert read_enterprise_dividend_allocation(cash) == 5000.0

    state = {
        "starting_capital": 500.0,
        "pairs": {
            "AMDW / AMDL": {
                "a_shares": 0.5,
                "b_shares": 0.3,
                "sgov_balance": 40.0,
                "a_sgov_balance": 0.0,
                "b_sgov_balance": 0.0,
                "pending_dividend_a": 1.0,
                "pending_dividend_b": 2.0,
                "total_dividends_received": 3.0,
                "capital_bucket": 75.0,
            }
        },
    }
    scaled, factor = scale_paper_state_to_allocation(state, 5000.0)
    assert factor == 10.0
    assert scaled["starting_capital"] == 5000.0
    assert scaled["pairs"]["AMDW / AMDL"]["a_shares"] == 5.0
    assert scaled["pairs"]["AMDW / AMDL"]["sgov_balance"] == 400.0
    assert scaled["pairs"]["AMDW / AMDL"]["capital_bucket"] == 750.0
    assert scaled["enterprise_capital_contract_strategy_id"] == "DIVIDEND-001"


def test_duplicate_initialization_buy_rows_do_not_double_entry_value():
    rows = [
        {"Date": "2026-06-18", "Action": "PAPER_BUY_OPEN", "Ticker": "AVGW", "Pair": "AVGW / AVGX", "Sleeve": "A", "Paper_Value": "42.00", "Reason": "init"},
        {"Date": "2026-06-18", "Action": "PAPER_BUY_OPEN", "Ticker": "AVGW", "Pair": "AVGW / AVGX", "Sleeve": "A", "Paper_Value": "42.00", "Reason": "init"},
        {"Date": "2026-06-26", "Action": "PAPER_SELL_TO_SGOV", "Ticker": "AVGW", "Pair": "AVGW / AVGX", "Sleeve": "A", "Paper_Value": "35.89", "Reason": "Underlying SELL signal"},
    ]
    record = build_position_lifecycle(rows, [])[0]
    assert record["entry_value"] == 42.0
    assert record["last_exit_value"] == 35.89
    assert record["realized_gain_loss"] == -6.11
    assert record["event_count"] == 2


def test_legacy_initialization_direct_to_sgov_is_never_entered_and_not_sales_history():
    rows = [
        {"Date": "2026-06-18", "Action": "PAPER_BUY_OPEN", "Ticker": "PLTW", "Pair": "PLTW / PLTU", "Sleeve": "A", "Paper_Value": "28.00", "Reason": "Signal-aware Strength Weighted initialization"},
        {"Date": "2026-06-18", "Action": "PAPER_PARK_IN_SGOV", "Ticker": "SGOV", "Pair": "PLTW / PLTU", "Sleeve": "A", "Paper_Value": "28.00", "Reason": "PAPER ONLY - NO REAL TRADES EXECUTED: Signal-aware initialization on SELL"},
    ]
    record = build_position_lifecycle(rows, [])[0]
    assert record["symbol"] == "PLTW"
    assert record["lifecycle_status"] == "NEVER_ENTERED"
    assert record["entry_value"] is None
    assert record["last_exit_value"] is None
    assert record["realized_gain_loss"] is None

    html = render_position_history_panel({"performance_detail": {"position_lifecycle": [record]}})
    assert "PLTW" not in html
    assert "Historical Positions</span><strong>0" in html


def test_explicit_wait_in_sgov_is_never_entered():
    rows = [
        {"Date": "2026-08-08", "Action": "PAPER_WAIT_IN_SGOV", "Ticker": "SGOV", "Pair": "NVDW / NVDX", "Sleeve": "A", "Paper_Value": "385.00", "Reason": "Entry gate blocked initialization: TECHNICAL_SIGNAL_HOLD"},
    ]
    record = build_position_lifecycle(rows, [])[0]
    assert record["symbol"] == "NVDW"
    assert record["lifecycle_status"] == "NEVER_ENTERED"
    assert record["never_entered_reason"] == "ENTRY_GATE_WAIT_IN_SGOV"


def test_yearly_distribution_yield_uses_displayed_holding_current_price():
    holdings = [{
        "symbol": "AMDW",
        "sleeve": "A",
        "position_status": "OPEN",
        "shares": 0.4809013546,
        "price": 103.010002,
    }]
    market = {
        "records": [{
            "symbol": "AMDW",
            "price": 85.160004,
            "history": {"rows": [{"date": "2026-08-07", "close": 103.010002}]},
            "dividends": {"payments": [
                {"date": "2026-08-03", "amount": 46.621},
            ]},
        }]
    }
    row = enrich_holdings_with_income_analytics(holdings, market_snapshot=market)[0]
    expected = round((46.621 / 103.010002) * 100.0, 4)
    assert row["yearly_distribution_yield_percent"] == expected
    assert row["yearly_distribution_yield_price"] == 103.010002
    assert row["yearly_distribution_yield_price_source"] == "HOLDING_CURRENT_PRICE"
    assert row["yearly_distribution_yield_method"] == "TRAILING_365D_DISTRIBUTIONS_DIVIDED_BY_CURRENT_HOLDING_PRICE"
