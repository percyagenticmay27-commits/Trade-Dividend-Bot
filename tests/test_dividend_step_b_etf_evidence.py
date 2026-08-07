from __future__ import annotations

from src.dividend_bot.dividend_growth_engine import build_dividend_growth_report
from src.dividend_bot.dividend_quality_engine import build_dividend_quality_report
from src.dividend_bot.dividend_safety_engine import build_dividend_safety_report
from src.dividend_bot.valuation_engine import build_valuation_report


def _snapshot():
    return {
        "records": [
            {
                "symbol": "ETF1",
                "quote_type": "ETF",
                "price": 95.0,
                "fifty_two_week_low": 80.0,
                "fifty_two_week_high": 120.0,
                "dividend_record_count": 24,
                "derived_dividend_growth": 0.08,
                "quote": {
                    "quote_type": "ETF",
                    "three_year_average_return": 0.09,
                    "five_year_average_return": 0.08,
                    "ytd_return": 0.07,
                    "annual_report_expense_ratio": 0.005,
                    "total_assets": 3_000_000_000,
                    "beta_3y": 0.85,
                    "dividend_yield": 0.055,
                    "price_to_book": 2.2,
                    "dividend_growth": 0.08,
                },
            }
        ]
    }


def test_etf_quality_uses_fund_evidence_not_company_nulls() -> None:
    row = build_dividend_quality_report(_snapshot())["entries"][0]
    assert row["evidence_model"] == "ETF_FUND_QUALITY"
    assert row["quality_score"] > 0
    assert row["missing_metrics"] == []


def test_etf_growth_uses_distribution_and_return_evidence() -> None:
    row = build_dividend_growth_report(_snapshot())["entries"][0]
    assert row["evidence_model"] == "ETF_DISTRIBUTION_AND_RETURN_GROWTH"
    assert row["growth_score"] > 0
    assert row["missing_metrics"] == []


def test_etf_safety_uses_fund_risk_cost_size_and_dividend_history() -> None:
    row = build_dividend_safety_report(_snapshot())["entries"][0]
    assert row["evidence_model"] == "ETF_FUND_SAFETY"
    assert row["safety_score"] > 0
    assert row["missing_metrics"] == []


def test_etf_valuation_uses_income_cost_and_price_position() -> None:
    row = build_valuation_report(_snapshot())["entries"][0]
    assert row["evidence_model"] == "ETF_INCOME_VALUATION"
    assert row["valuation_score"] > 0
    assert row["missing_metrics"] == []


def test_all_step_b_components_keep_execution_locked() -> None:
    for report in (
        build_dividend_quality_report(_snapshot()),
        build_dividend_growth_report(_snapshot()),
        build_dividend_safety_report(_snapshot()),
        build_valuation_report(_snapshot()),
    ):
        assert report["paper_trade_mode"] is True
        assert report["live_trading_enabled"] is False
        assert report["broker_execution_enabled"] is False
        assert report["order_placement_enabled"] is False
        assert report["capital_movement_enabled"] is False
        assert report["automatic_activation_allowed"] is False
