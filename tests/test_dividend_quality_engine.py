from src.dividend_bot.dividend_quality_engine import build_dividend_quality_report


def _snapshot(quote):
    return {"records": [{"symbol": "TEST", "quote": quote}]}


def test_scores_complete_quality_evidence():
    report = build_dividend_quality_report(_snapshot({
        "returnOnEquity": 0.28,
        "profitMargins": 0.22,
        "operatingMargins": 0.24,
        "freeCashflow": 1_000_000,
    }))
    row = report["entries"][0]
    assert row["quality_score"] == 100.0
    assert row["missing_metrics"] == []
    assert row["evidence_status"] == "AVAILABLE"


def test_missing_evidence_is_zero_and_disclosed():
    report = build_dividend_quality_report(_snapshot({"returnOnEquity": 0.15}))
    row = report["entries"][0]
    assert row["quality_score"] == 21.25
    assert set(row["missing_metrics"]) == {"profit_margin", "operating_margin", "free_cash_flow"}
    assert row["evidence_status"] == "PARTIAL"
    assert report["warnings"]


def test_percent_style_ratios_are_normalized():
    report = build_dividend_quality_report(_snapshot({
        "return_on_equity": 25,
        "profit_margins": 20,
        "operating_margins": 20,
        "free_cashflow": 1,
    }))
    assert report["entries"][0]["quality_score"] == 100.0


def test_empty_snapshot_is_valid_and_does_not_fabricate_entries():
    report = build_dividend_quality_report({"records": []})
    assert report["entries"] == []
    assert report["entry_count"] == 0


def test_governance_and_execution_locks_remain_enforced():
    report = build_dividend_quality_report(_snapshot({}))
    assert report["paper_trade_mode"] is True
    assert report["reporting_only"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["order_placement_enabled"] is False
    assert report["capital_movement_enabled"] is False
    assert report["automatic_activation_allowed"] is False
