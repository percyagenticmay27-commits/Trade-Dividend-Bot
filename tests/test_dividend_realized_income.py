from src.dividend_bot.dividend_realized_income import build_realized_income_evidence


def test_realized_income_separates_gross_adjustments_and_net() -> None:
    rows = [
        {"Date": "2026-08-01", "Action": "PAPER_DIVIDEND_RECEIVED", "Ticker": "AVGW", "Paper_Value": "2.50"},
        {"Date": "2026-08-02", "Action": "PAPER_DIVIDEND_RECEIVED", "Ticker": "NVDW", "Paper_Value": "1.75"},
        {"Date": "2026-08-03", "Action": "PAPER_DIVIDEND_ADJUSTMENT", "Ticker": "AVGW", "Paper_Value": "-0.25"},
    ]
    report = build_realized_income_evidence(rows)
    assert report["gross_distribution_income"] == 4.25
    assert report["income_adjustments"] == -0.25
    assert report["net_income_received"] == 4.00
    assert report["realized_income_event_count"] == 3
    assert report["positive_income_event_count"] == 2
    assert report["negative_income_event_count"] == 1


def test_positive_reversal_amount_is_normalized_negative() -> None:
    report = build_realized_income_evidence([
        {"Date": "2026-08-04", "Action": "PAPER_DIVIDEND_REVERSAL", "Ticker": "AVGW", "Paper_Value": "1.20"},
    ])
    assert report["gross_distribution_income"] == 0.0
    assert report["income_adjustments"] == -1.20
    assert report["net_income_received"] == -1.20
    assert report["income_events"][0]["amount"] == -1.20
    assert report["income_events"][0]["event_type"] == "DISTRIBUTION_REVERSAL"


def test_non_income_trade_rows_are_ignored() -> None:
    report = build_realized_income_evidence([
        {"Action": "PAPER_BUY_FROM_SGOV", "Ticker": "AVGW", "Paper_Value": "25.00"},
        {"Action": "PAPER_SELL_TO_SGOV", "Ticker": "AVGW", "Paper_Value": "30.00"},
    ])
    assert report["net_income_received"] == 0.0
    assert report["income_events"] == []


def test_negative_receipt_is_treated_as_income_adjustment() -> None:
    report = build_realized_income_evidence([
        {"Action": "PAPER_DIVIDEND_RECEIVED", "Ticker": "AVGW", "Paper_Value": "-0.75"},
    ])
    assert report["gross_distribution_income"] == 0.0
    assert report["income_adjustments"] == -0.75
    assert report["net_income_received"] == -0.75


def test_governance_flags_remain_locked() -> None:
    report = build_realized_income_evidence([])
    assert report["paper_trade_mode"] is True
    assert report["reporting_only"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
