from __future__ import annotations

import json
from pathlib import Path

import institutional_context_pattern_intelligence as icpi


def request(**overrides):
    data = dict(
        symbol="QROB",
        as_of_date="2026-07-15",
        lifecycle_stage="IPO",
        archetype_candidates=("EMERGING_DISRUPTOR",),
        current_features={"growth": 90, "profitability": 30, "volatility": 85},
        ipo_profile=icpi.IPOProfile(
            months_public=5,
            insider_ownership_pct=60,
            institutional_ownership_pct=20,
            liquidity_score=65,
            volatility_score=85,
            earnings_reports_available=1,
            financial_history_score=35,
        ),
        opportunity_quality_score=84,
        research_conviction_score=78,
        evidence_confidence=70,
    )
    data.update(overrides)
    return icpi.ContextRequest(**data)


def case(name="Comparable", **overrides):
    data = dict(
        case_id="CASE-1",
        name=name,
        lifecycle_stage="IPO",
        archetypes=("EMERGING_DISRUPTOR",),
        features={"growth": 88, "profitability": 28, "volatility": 87},
        observed_outcome="High volatility followed by evidence-dependent stabilization.",
        lessons=("Observe lock-up and earnings progression.",),
        market_pattern="Emerging Technology Expansion",
    )
    data.update(overrides)
    return icpi.HistoricalCase(**data)


def pattern(name="Expansion", **overrides):
    data = dict(
        pattern_id="PATTERN-1",
        name=name,
        features={"growth": 85, "profitability": 35, "volatility": 75},
        observed_outcomes=("Winners separated from imitators through earnings execution.",),
        lessons=("Current evidence mattered more than theme popularity.",),
    )
    data.update(overrides)
    return icpi.MarketPattern(**data)


def test_module_identity_and_safety():
    assert icpi.MODULE_NAME == "institutional_context_pattern_intelligence"
    assert icpi.MODULE_VERSION == "1.0.0"
    assert icpi.PAPER_TRADE_MODE is True
    assert icpi.LIVE_TRADING_ENABLED is False
    assert icpi.BROKER_EXECUTION_ENABLED is False


def test_ipo_profile_not_applicable():
    result = icpi.calculate_ipo_stability(None)
    assert result["applicable"] is False
    assert result["status"] == "NOT_APPLICABLE"


def test_young_ipo_is_observation_only():
    result = icpi.calculate_ipo_stability(request().ipo_profile)
    assert result["applicable"] is True
    assert result["status"] == "OBSERVATION_ONLY"
    assert result["risk_flags"]


def test_more_mature_ipo_scores_higher():
    young = icpi.calculate_ipo_stability(request().ipo_profile)
    mature_profile = icpi.IPOProfile(
        months_public=24,
        insider_ownership_pct=18,
        institutional_ownership_pct=62,
        liquidity_score=92,
        volatility_score=28,
        earnings_reports_available=6,
        financial_history_score=90,
    )
    mature = icpi.calculate_ipo_stability(mature_profile)
    assert mature["score"] > young["score"]
    assert mature["status"] == "STABLE"


def test_invalid_lockup_date_is_warning_not_failure():
    profile = icpi.IPOProfile(lockup_expiration="not-a-date")
    result = icpi.calculate_ipo_stability(profile)
    assert result["applicable"] is True
    assert any("invalid" in item.lower() for item in result["risk_flags"])


def test_historical_similarity_exact_match():
    req = request(current_features={"growth": 88, "profitability": 28, "volatility": 87})
    twins = icpi.find_historical_twins(req, [case()])
    assert twins[0]["similarity_score"] == 100.0


def test_historical_twin_limit():
    cases = [case(name=f"Case {i}", case_id=f"C-{i}") for i in range(10)]
    assert len(icpi.find_historical_twins(request(), cases, limit=3)) == 3


def test_historical_twins_sorted_best_first():
    strong = case(name="Strong", features={"growth": 90, "profitability": 30, "volatility": 85})
    weak = case(name="Weak", case_id="CASE-2", features={"growth": 5, "profitability": 90, "volatility": 10})
    twins = icpi.find_historical_twins(request(), [weak, strong])
    assert twins[0]["name"] == "Strong"


def test_market_pattern_matching():
    matches = icpi.match_market_patterns(request(), [pattern()])
    assert matches[0]["pattern_id"] == "PATTERN-1"
    assert 0 <= matches[0]["pattern_match_score"] <= 100


def test_market_pattern_limit_zero():
    assert icpi.match_market_patterns(request(), [pattern()], limit=0) == []


def test_report_contains_core_context():
    report = icpi.build_context_report(request(), [case()], [pattern()])
    assert report["symbol"] == "QROB"
    assert report["lifecycle_stage"] == "IPO"
    assert report["historical_twins"]
    assert report["market_pattern_matches"]
    assert 0 <= report["context_confidence_score"] <= 100


def test_context_has_no_allocation_authority():
    report = icpi.build_context_report(request(), [case()], [pattern()])
    assert report["allocation_authority"] is False
    assert report["ranking_authority"] is False
    assert report["watchlist_promotion_authority"] is False


def test_sector_or_archetype_has_no_entitlement():
    report = icpi.build_context_report(request(), [case()], [pattern()])
    assert report["governance"]["sector_or_archetype_creates_no_entitlement"] is True


def test_current_evidence_must_still_prove_opportunity():
    report = icpi.build_context_report(request(), [case()], [pattern()])
    assert report["governance"]["current_evidence_must_still_prove_opportunity"] is True


def test_prediction_language_is_prohibited():
    report = icpi.build_context_report(request(), [case()], [pattern()])
    assert report["governance"]["prediction_language_prohibited"] is True


def test_young_ipo_recommends_observation():
    report = icpi.build_context_report(request(), [case()], [pattern()])
    assert report["recommended_research_action"] == "CONTINUE_OBSERVATION"


def test_low_context_confidence_requests_evidence():
    req = request(ipo_profile=None, evidence_confidence=0, research_conviction_score=0, current_features={})
    report = icpi.build_context_report(req, [], [])
    assert report["recommended_research_action"] == "COLLECT_MORE_EVIDENCE"


def test_established_evidence_continues_qualification():
    req = request(
        lifecycle_stage="ESTABLISHED",
        ipo_profile=None,
        evidence_confidence=92,
        research_conviction_score=85,
        current_features={"growth": 80, "profitability": 85, "volatility": 30},
    )
    strong_case = case(lifecycle_stage="ESTABLISHED", features={"growth": 78, "profitability": 84, "volatility": 32})
    strong_pattern = pattern(features={"growth": 75, "profitability": 80, "volatility": 35})
    report = icpi.build_context_report(req, [strong_case], [strong_pattern])
    assert report["recommended_research_action"] == "CONTINUE_QUALIFICATION"


def test_unknown_lifecycle_is_normalized():
    report = icpi.build_context_report(request(lifecycle_stage="NOT_REAL"), [], [])
    assert report["lifecycle_stage"] == "UNKNOWN"


def test_unknown_archetype_is_normalized():
    report = icpi.build_context_report(request(archetype_candidates=("NOT_REAL",)), [], [])
    assert report["archetypes"] == ["UNKNOWN"]


def test_missing_case_library_creates_warning():
    report = icpi.build_context_report(request(), [], [pattern()])
    assert any("historical case" in item.lower() for item in report["warnings"])


def test_missing_pattern_library_creates_warning():
    report = icpi.build_context_report(request(), [case()], [])
    assert any("market-pattern" in item.lower() for item in report["warnings"])


def test_missing_opportunity_quality_creates_warning():
    report = icpi.build_context_report(request(opportunity_quality_score=0), [case()], [pattern()])
    assert any("opportunity quality" in item.lower() for item in report["warnings"])


def test_opportunity_quality_is_display_only():
    report = icpi.build_context_report(request(opportunity_quality_score=91), [case()], [pattern()])
    assert report["opportunity_quality_score_display_only"] == 91.0


def test_research_conviction_is_display_only():
    report = icpi.build_context_report(request(research_conviction_score=88), [case()], [pattern()])
    assert report["research_conviction_score_display_only"] == 88.0


def test_markdown_contains_governance():
    report = icpi.build_context_report(request(), [case()], [pattern()])
    markdown = icpi.render_markdown(report)
    assert "# Institutional Context & Pattern Intelligence" in markdown
    assert "Historical similarity provides context only" in markdown


def test_html_escapes_markdown():
    report = icpi.build_context_report(request(symbol="A&B"), [case()], [pattern()])
    html = icpi.render_html(report)
    assert "<!doctype html>" in html
    assert "A&amp;B" in html


def test_write_reports(tmp_path: Path):
    report = icpi.build_context_report(request(), [case()], [pattern()])
    paths = icpi.write_reports(report, tmp_path)
    assert set(paths) == {"json", "markdown", "html"}
    for path in paths.values():
        assert Path(path).exists()


def test_written_json_is_valid(tmp_path: Path):
    report = icpi.build_context_report(request(), [case()], [pattern()])
    paths = icpi.write_reports(report, tmp_path)
    loaded = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert loaded["symbol"] == "QROB"


def test_sample_report_is_valid():
    report = icpi.sample_report()
    assert report["paper_trade_mode"] is True
    assert report["symbol"] == "QROB"
    assert report["historical_twins"]


def test_no_broker_or_order_execution_language_in_public_api():
    public_names = set(dir(icpi))
    forbidden = {"send_order", "place_order", "execute_trade", "connect_broker"}
    assert not (public_names & forbidden)


def test_empty_symbol_is_handled_without_exception():
    report = icpi.build_context_report(request(symbol=""), [], [])
    assert report["symbol"] == ""
    assert report["warnings"]


def test_nonfinite_scores_are_safely_clamped():
    req = request(opportunity_quality_score=float("inf"), research_conviction_score=float("nan"), evidence_confidence=float("inf"))
    report = icpi.build_context_report(req, [case()], [pattern()])
    assert report["opportunity_quality_score_display_only"] == 0.0
    assert report["research_conviction_score_display_only"] == 0.0
    assert 0 <= report["context_confidence_score"] <= 100
