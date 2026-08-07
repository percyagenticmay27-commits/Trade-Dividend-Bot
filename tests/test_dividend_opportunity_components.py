from src.dividend_bot.dividend_growth_engine import build_dividend_growth_report
from src.dividend_bot.dividend_safety_engine import build_dividend_safety_report
from src.dividend_bot.valuation_engine import build_valuation_report


def _snapshot(record):
    return {"records": [record]}


def test_growth_scores_complete_evidence():
    report = build_dividend_growth_report(_snapshot({
        "symbol": "TEST",
        "quote": {
            "revenueGrowth": 0.16,
            "earningsGrowth": 0.12,
            "earningsQuarterlyGrowth": 0.10,
            "dividendGrowth": 0.08,
        },
    }))
    row = report["entries"][0]
    assert row["growth_score"] == 85.0
    assert row["missing_metrics"] == []


def test_growth_missing_evidence_defaults_to_zero():
    report = build_dividend_growth_report(_snapshot({"symbol": "TEST", "quote": {}}))
    row = report["entries"][0]
    assert row["growth_score"] == 0.0
    assert row["evidence_status"] == "NOT_REPORTED"


def test_safety_scores_real_declared_inputs():
    report = build_dividend_safety_report(_snapshot({
        "symbol": "TEST",
        "dividend_record_count": 20,
        "quote": {
            "payoutRatio": 0.55,
            "debtToEquity": 50.0,
            "currentRatio": 2.1,
        },
    }))
    row = report["entries"][0]
    assert row["safety_score"] == 100.0
    assert row["missing_metrics"] == []


def test_valuation_scores_price_and_multiples():
    report = build_valuation_report(_snapshot({
        "symbol": "TEST",
        "price": 40,
        "fifty_two_week_low": 20,
        "fifty_two_week_high": 100,
        "quote": {
            "trailingPE": 15,
            "forwardPE": 12,
            "priceToBook": 1.5,
        },
    }))
    row = report["entries"][0]
    assert row["valuation_score"] == 96.25
    assert row["missing_metrics"] == []


def test_all_component_engines_preserve_execution_locks():
    builders = (
        build_dividend_growth_report,
        build_dividend_safety_report,
        build_valuation_report,
    )
    for builder in builders:
        report = builder(_snapshot({"symbol": "TEST", "quote": {}}))
        assert report["paper_trade_mode"] is True
        assert report["reporting_only"] is True
        assert report["live_trading_enabled"] is False
        assert report["broker_execution_enabled"] is False
        assert report["order_placement_enabled"] is False
        assert report["capital_movement_enabled"] is False
        assert report["automatic_activation_allowed"] is False
