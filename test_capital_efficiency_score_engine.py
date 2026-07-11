"""Tests for capital_efficiency_score_engine.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import capital_efficiency_score_engine as engine


def strong_candidate(candidate_id: str = "QQQI+TQQQ", candidate_type: str = "PAIR") -> dict:
    return {
        "candidate_id": candidate_id,
        "candidate_type": candidate_type,
        "symbols": candidate_id.split("+"),
        "expected_capital_appreciation": 90,
        "expected_income": 80,
        "reinvestment_potential": 85,
        "momentum_trend_quality": 88,
        "fundamental_or_fund_quality": 82,
        "sector_leadership": 90,
        "market_regime_support": 85,
        "distribution_sustainability": 75,
        "evidence_confidence": 90,
        "volatility_risk": 45,
        "drawdown_risk": 50,
        "downside_risk": 40,
        "concentration_risk": 30,
        "correlation_risk": 35,
        "turnover_tax_friction": 10,
    }


def test_public_functions_exist():
    for name in [
        "score_capital_efficiency_candidate",
        "build_capital_efficiency_score_report",
        "compare_replacement_candidate",
        "validate_capital_efficiency_score_report",
        "format_capital_efficiency_score_markdown",
        "write_capital_efficiency_score_report",
    ]:
        assert callable(getattr(engine, name))


def test_single_pair_and_strategy_are_supported_and_ranked():
    single = strong_candidate("QQQI", "SINGLE_INSTRUMENT")
    single["expected_capital_appreciation"] = 72
    pair = strong_candidate()
    strategy = strong_candidate("SCHD+QQQI+TQQQ+SGOV", "PORTFOLIO_STRATEGY")
    strategy["expected_capital_appreciation"] = 82
    strategy["volatility_risk"] = 25
    strategy["drawdown_risk"] = 28
    report = engine.build_capital_efficiency_score_report([single, pair, strategy])
    assert report["candidate_count"] == 3
    assert len(report["results"]) == 3
    assert report["results"][0]["rank"] == 1
    assert report["top_candidate_id"] == report["results"][0]["candidate_id"]
    assert {row["candidate_type"] for row in report["results"]} == {
        "SINGLE_INSTRUMENT", "PAIR", "PORTFOLIO_STRATEGY"
    }


def test_growth_and_income_both_contribute_to_score():
    base = strong_candidate("BASE", "PORTFOLIO_STRATEGY")
    high_growth = dict(base, candidate_id="HIGH_GROWTH", expected_capital_appreciation=100, expected_income=20)
    high_income = dict(base, candidate_id="HIGH_INCOME", expected_capital_appreciation=20, expected_income=100)
    balanced = dict(base, candidate_id="BALANCED", expected_capital_appreciation=85, expected_income=85)
    report = engine.build_capital_efficiency_score_report([high_growth, high_income, balanced])
    scores = {row["candidate_id"]: row["capital_efficiency_score"] for row in report["results"]}
    assert scores["BALANCED"] > scores["HIGH_GROWTH"]
    assert scores["BALANCED"] > scores["HIGH_INCOME"]


def test_high_yield_cannot_hide_principal_and_risk_deterioration():
    healthy = strong_candidate("HEALTHY", "PORTFOLIO_STRATEGY")
    eroding = strong_candidate("ERODING", "PORTFOLIO_STRATEGY")
    eroding.update({
        "expected_capital_appreciation": 5,
        "expected_income": 100,
        "volatility_risk": 90,
        "drawdown_risk": 95,
        "downside_risk": 90,
    })
    report = engine.build_capital_efficiency_score_report([healthy, eroding])
    scores = {row["candidate_id"]: row["capital_efficiency_score"] for row in report["results"]}
    assert scores["HEALTHY"] > scores["ERODING"]


def test_missing_evidence_is_penalized_and_never_positive():
    complete = strong_candidate("COMPLETE", "PORTFOLIO_STRATEGY")
    incomplete = {
        "candidate_id": "INCOMPLETE",
        "candidate_type": "PORTFOLIO_STRATEGY",
        "expected_income": 95,
        "evidence_confidence": 50,
    }
    complete_result = engine.score_capital_efficiency_candidate(complete)
    incomplete_result = engine.score_capital_efficiency_candidate(incomplete)
    assert incomplete_result["missing_evidence_count"] > 0
    assert incomplete_result["penalty_breakdown"]["missing_evidence"] > 0
    assert incomplete_result["capital_efficiency_score"] < complete_result["capital_efficiency_score"]
    assert incomplete_result["warnings"]


def test_concentrated_opportunity_requires_stronger_confirmation():
    candidate = strong_candidate("AMDW", "SINGLE_INSTRUMENT")
    candidate["market_regime_support"] = 50
    result = engine.score_capital_efficiency_candidate(candidate)
    assert result["concentrated_confirmation_passed"] is False
    assert result["qualifying"] is False
    assert result["recommendation"] == "WATCHLIST"


def test_diversified_strategy_does_not_receive_automatic_preference():
    concentrated = strong_candidate("AMDW", "SINGLE_INSTRUMENT")
    diversified = strong_candidate("SPYI", "PORTFOLIO_STRATEGY")
    diversified.update({
        "expected_capital_appreciation": 55,
        "expected_income": 65,
        "momentum_trend_quality": 60,
        "sector_leadership": 55,
        "market_regime_support": 60,
    })
    report = engine.build_capital_efficiency_score_report([diversified, concentrated])
    assert report["top_candidate_id"] == "AMDW"


def test_risk_penalties_reduce_score_and_raise_flags():
    low_risk = strong_candidate("LOW_RISK", "PORTFOLIO_STRATEGY")
    high_risk = strong_candidate("HIGH_RISK", "PORTFOLIO_STRATEGY")
    high_risk.update({
        "volatility_risk": 90,
        "drawdown_risk": 95,
        "concentration_risk": 85,
    })
    low_result = engine.score_capital_efficiency_candidate(low_risk)
    high_result = engine.score_capital_efficiency_candidate(high_risk)
    assert high_result["capital_efficiency_score"] < low_result["capital_efficiency_score"]
    assert "HIGH_DRAWDOWN_RISK" in high_result["risk_flags"]
    assert "HIGH_CONCENTRATION_RISK" in high_result["risk_flags"]
    assert "HIGH_VOLATILITY_RISK" in high_result["risk_flags"]


def test_replacement_requires_sale_gate_and_minimum_improvement():
    assert engine.compare_replacement_candidate(70, 80, False)["replacement_approved"] is False
    assert engine.compare_replacement_candidate(70, 73, True)["replacement_approved"] is False
    approved = engine.compare_replacement_candidate(70, 76, True)
    assert approved["replacement_approved"] is True
    assert approved["decision"] == "REPLACE"


def test_empty_report_is_valid_and_warns():
    report = engine.build_capital_efficiency_score_report()
    assert report["candidate_count"] == 0
    assert report["qualifying_candidate_count"] == 0
    assert report["top_candidate_id"] is None
    assert report["warnings"]
    assert engine.validate_capital_efficiency_score_report(report)


def test_invalid_candidate_type_is_reported_without_crashing_other_candidates():
    bad = strong_candidate("BAD")
    bad["candidate_type"] = "UNKNOWN_TYPE"
    report = engine.build_capital_efficiency_score_report([bad, strong_candidate("GOOD")])
    assert report["candidate_count"] == 2
    assert len(report["results"]) == 1
    assert report["errors"]
    assert report["results"][0]["candidate_id"] == "GOOD"


def test_validation_rejects_wrong_safety_flags():
    report = engine.build_capital_efficiency_score_report([strong_candidate("GOOD")])
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(report)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_capital_efficiency_score_report(bad)


def test_write_outputs_json_and_markdown(tmp_path: Path):
    report = engine.write_capital_efficiency_score_report([strong_candidate()], root_path=str(tmp_path))
    json_path = tmp_path / "capital_efficiency_scores.json"
    markdown_path = tmp_path / "capital_efficiency_scores.md"
    assert json_path.exists()
    assert markdown_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8")) == report
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Capital Efficiency Score Report" in markdown
    assert "QQQI+TQQQ" in markdown


def test_scores_are_bounded_zero_to_one_hundred():
    extreme = strong_candidate("EXTREME", "PORTFOLIO_STRATEGY")
    extreme.update({
        "expected_capital_appreciation": 1000,
        "expected_income": 1000,
        "volatility_risk": -100,
    })
    result = engine.score_capital_efficiency_candidate(extreme)
    assert 0 <= result["capital_efficiency_score"] <= 100


def test_no_restricted_broker_or_order_calls_in_source():
    source = Path(engine.__file__).read_text(encoding="utf-8").lower()
    restricted = [
        "import robin" + "hood",
        "from robin" + "hood",
        "import robin" + "_stocks",
        "from robin" + "_stocks",
        "place" + "_order(",
        "submit" + "_order(",
        "execute" + "_order(",
    ]
    for token in restricted:
        assert token not in source
