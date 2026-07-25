import json
from pathlib import Path
import sys

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "dividend_bot"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import enterprise_investor_dashboard_integration as mod


def sample_inputs():
    return {
        "portfolio_summary": {
            "portfolio_value": 10000,
            "cost_basis": 9000,
            "projected_annual_income": 600,
            "cash_value": 500,
        },
        "holdings": [
            {
                "symbol": "aaa",
                "market_value": 3000,
                "allocation_percent": 30,
                "annual_income": 180,
                "sector": "Utilities",
            },
            {
                "symbol": "bbb",
                "market_value": 2500,
                "allocation_percent": 25,
                "annual_income": 150,
                "sector": "Utilities",
            },
            {
                "symbol": "sgov",
                "market_value": 500,
                "allocation_percent": 5,
                "annual_income": 25,
                "sector": "Reserve",
            },
        ],
        "payment_history": [
            {"symbol": "AAA", "status": "PAID"},
            {"symbol": "BBB", "status": "LATE"},
            {"symbol": "AAA", "status": "MISSED"},
        ],
        "upcoming_payments": [
            {"symbol": "AAA", "payable_date": "2026-08-15", "expected_amount": 45.0}
        ],
        "confidence_report": {"score": 88, "label": "HIGH"},
        "generated_at_utc": "2026-07-25T12:00:00Z",
    }


def test_safety_constants():
    assert mod.PAPER_TRADE_MODE is True
    assert mod.LIVE_TRADING_ENABLED is False
    assert mod.BROKER_EXECUTION_ENABLED is False
    assert mod.REPORTING_ONLY is True


def test_build_dashboard_metadata_and_safety():
    report = mod.build_enterprise_investor_dashboard(**sample_inputs())
    assert report["module_name"] == "enterprise_investor_dashboard_integration"
    assert report["module_version"] == "1.0.0"
    assert report["schema_version"] == "1.0"
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["reporting_only"] is True


def test_investor_summary_calculations():
    report = mod.build_enterprise_investor_dashboard(**sample_inputs())
    summary = report["investor_summary"]
    assert summary["portfolio_value"] == 10000.0
    assert summary["cost_basis"] == 9000.0
    assert summary["capital_appreciation"] == 1000.0
    assert summary["projected_annual_dividend_income"] == 600.0
    assert summary["projected_monthly_dividend_income"] == 50.0
    assert summary["current_yield_percent"] == 6.0
    assert summary["yield_on_cost_percent"] == pytest.approx(6.6667)
    assert summary["cash_or_reserve_percent"] == 5.0


def test_explicit_yield_values_are_preserved():
    inputs = sample_inputs()
    inputs["portfolio_summary"]["current_yield_percent"] = 7.25
    inputs["portfolio_summary"]["yield_on_cost_percent"] = 8.5
    report = mod.build_enterprise_investor_dashboard(**inputs)
    assert report["investor_summary"]["current_yield_percent"] == 7.25
    assert report["investor_summary"]["yield_on_cost_percent"] == 8.5


def test_holdings_are_normalized_and_sorted():
    report = mod.build_enterprise_investor_dashboard(**sample_inputs())
    holdings = report["allocation"]["holdings"]
    assert [row["symbol"] for row in holdings] == ["AAA", "BBB", "SGOV"]
    assert report["allocation"]["largest_position_symbol"] == "AAA"
    assert report["allocation"]["largest_position_percent"] == 30.0


def test_sector_allocation_is_aggregated():
    report = mod.build_enterprise_investor_dashboard(**sample_inputs())
    sectors = report["allocation"]["sector_allocation"]
    assert sectors[0] == {"sector": "Utilities", "allocation_percent": 55.0}


def test_income_consistency_metrics():
    report = mod.build_enterprise_investor_dashboard(**sample_inputs())
    reliability = report["income_reliability"]
    assert reliability["expected_payment_count"] == 3
    assert reliability["received_payment_count"] == 1
    assert reliability["late_payment_count"] == 1
    assert reliability["missed_payment_count"] == 1
    assert reliability["consistency_score"] == 50.0
    assert reliability["consistency_label"] == "WATCH"


def test_missing_payment_history_defaults_safely():
    inputs = sample_inputs()
    inputs["payment_history"] = []
    report = mod.build_enterprise_investor_dashboard(**inputs)
    assert report["income_reliability"]["consistency_score"] == 100.0
    assert any("Payment history" in warning for warning in report["warnings"])


def test_position_concentration_flag():
    report = mod.build_enterprise_investor_dashboard(**sample_inputs())
    codes = {item["code"] for item in report["risk_flags"]}
    assert "POSITION_CONCENTRATION" in codes


def test_sector_concentration_flag():
    report = mod.build_enterprise_investor_dashboard(**sample_inputs())
    codes = {item["code"] for item in report["risk_flags"]}
    assert "SECTOR_CONCENTRATION" in codes


def test_missed_payment_flag():
    report = mod.build_enterprise_investor_dashboard(**sample_inputs())
    codes = {item["code"] for item in report["risk_flags"]}
    assert "MISSED_DIVIDEND_PAYMENT" in codes
    assert report["portfolio_health"] == "ATTENTION_REQUIRED"


def test_source_review_flags_are_preserved():
    inputs = sample_inputs()
    inputs["review_flags"] = [
        {"severity": "medium", "code": "earnings_review", "message": "Review upcoming earnings."}
    ]
    report = mod.build_enterprise_investor_dashboard(**inputs)
    assert any(item["code"] == "EARNINGS_REVIEW" for item in report["risk_flags"])


def test_risk_flags_are_priority_sorted():
    report = mod.build_enterprise_investor_dashboard(**sample_inputs())
    severities = [item["severity"] for item in report["risk_flags"]]
    assert severities == sorted(severities, key={"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}.get)


def test_suggested_actions_follow_risks():
    report = mod.build_enterprise_investor_dashboard(**sample_inputs())
    actions = " ".join(item["action"] for item in report["suggested_actions"])
    assert "largest position" in actions
    assert "sector concentration" in actions
    assert "payment" in actions.lower()


def test_accepts_phase_one_dashboard_payload():
    report = mod.build_enterprise_investor_dashboard(
        dividend_dashboard={
            "portfolio_summary": sample_inputs()["portfolio_summary"],
            "holdings": sample_inputs()["holdings"],
            "payments": sample_inputs()["payment_history"],
            "upcoming_payments": sample_inputs()["upcoming_payments"],
            "confidence": {"score": 77},
        },
        generated_at_utc="2026-07-25T12:00:00Z",
    )
    assert report["dashboard_status"] == "READY"
    assert report["investor_summary"]["holding_count"] == 3
    assert report["confidence"]["score"] == 77


def test_missing_inputs_create_partial_dashboard_not_failure():
    report = mod.build_enterprise_investor_dashboard(generated_at_utc="2026-07-25T12:00:00Z")
    assert report["dashboard_status"] == "PARTIAL"
    assert report["errors"] == []
    assert len(report["warnings"]) == 3


def test_nonfinite_numbers_default_to_zero():
    report = mod.build_enterprise_investor_dashboard(
        portfolio_summary={"portfolio_value": float("inf"), "projected_annual_income": float("nan")},
        generated_at_utc="2026-07-25T12:00:00Z",
    )
    assert report["investor_summary"]["portfolio_value"] == 0.0
    assert report["investor_summary"]["projected_annual_dividend_income"] == 0.0


def test_markdown_contains_investor_sections_and_safety():
    report = mod.build_enterprise_investor_dashboard(**sample_inputs())
    text = mod.render_enterprise_investor_dashboard_markdown(report)
    assert "# Enterprise Investor Dashboard" in text
    assert "## Portfolio Overview" in text
    assert "## Income Reliability" in text
    assert "## Holdings" in text
    assert "## Risk Flags" in text
    assert "Paper-only" in text
    assert "$10,000.00" in text


def test_write_outputs(tmp_path):
    report = mod.build_enterprise_investor_dashboard(**sample_inputs())
    paths = mod.write_enterprise_investor_dashboard(report, tmp_path)
    assert Path(paths["json"]).exists()
    assert Path(paths["markdown"]).exists()


def test_written_json_is_valid(tmp_path):
    report = mod.build_enterprise_investor_dashboard(**sample_inputs())
    paths = mod.write_enterprise_investor_dashboard(report, tmp_path)
    loaded = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert loaded["module_name"] == mod.MODULE_NAME
    assert loaded["paper_trade_mode"] is True


def test_custom_output_names(tmp_path):
    report = mod.build_enterprise_investor_dashboard(**sample_inputs())
    paths = mod.write_enterprise_investor_dashboard(
        report,
        tmp_path,
        {"json": "investor.json", "markdown": "investor.md"},
    )
    assert Path(paths["json"]).name == "investor.json"
    assert Path(paths["markdown"]).name == "investor.md"


def test_write_rejects_non_mapping(tmp_path):
    with pytest.raises(ValueError):
        mod.write_enterprise_investor_dashboard([], tmp_path)


def test_build_and_write(tmp_path):
    report, paths = mod.build_and_write_enterprise_investor_dashboard(
        output_dir=tmp_path,
        **sample_inputs(),
    )
    assert report["dashboard_status"] == "READY"
    assert Path(paths["json"]).exists()
    assert Path(paths["markdown"]).exists()


def test_no_execution_interfaces_exposed():
    forbidden = {"place_order", "submit_order", "execute_trade", "connect_broker", "robinhood_login"}
    assert forbidden.isdisjoint(set(dir(mod)))
