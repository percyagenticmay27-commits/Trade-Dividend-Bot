from enterprise_discovery_theme_strength import (
    CATALYST_FAMILIES,
    THEME_STRENGTH_COMPONENTS,
    attach_candidate_theme_strength,
    build_theme_strength_block,
)
from enterprise_weekly_market_discovery import build_swing_projection, build_weekly_discovery
from scripts.collect_enterprise_discovery_sources import _hydrate_retained_theme_context


def _row(**overrides):
    payload = {
        "underlying_symbol": "NVDA",
        "discovery_status": "RISING",
        "themes": ["Semiconductors"],
        "source_evidence": [
            {"source": "Reuters", "producer": "Reuters", "source_class": "PROFESSIONAL_MEDIA", "mentioned_on": "2026-09-04", "story_id": "nvda-1", "earnings_growth_related": True, "analyst_upgrade_related": False},
            {"source": "SEC EDGAR", "producer": "U.S. Securities and Exchange Commission", "source_class": "PRIMARY_COMPANY", "mentioned_on": "2026-09-03", "story_id": "nvda-2", "earnings_growth_related": False, "analyst_upgrade_related": False},
            {"source": "Research Desk", "producer": "Research Desk", "source_class": "INSTITUTIONAL_RESEARCH", "mentioned_on": "2026-09-02", "story_id": "nvda-3", "earnings_growth_related": False, "analyst_upgrade_related": True},
        ],
        "market_evidence": {"status": "AVAILABLE", "relative_strength_vs_benchmark_percent": 2.0, "volume_expansion_ratio": 1.2, "latest_session": "2026-09-04", "benchmark_symbol": "SPY", "is_stale": False},
        "financial_health": {
            "components": {"sector_strength": 70.0},
            "evidence_timestamp": "2026-09-04T16:35:35Z",
            "evidence": {"revenue_growth": 0.25, "eps_growth": 0.30, "analyst_upgrades_90d": 2.0, "analyst_downgrades_90d": 1.0},
        },
    }
    payload.update(overrides)
    return payload


def test_complete_theme_strength_block_has_all_components_and_provenance():
    block = build_theme_strength_block(_row(), generated_at="2026-09-04T16:40:00Z")
    assert block is not None
    assert set(block["components"]) == set(THEME_STRENGTH_COMPONENTS)
    assert all(0.0 <= value <= 100.0 for value in block["components"].values())
    assert 0.0 <= block["score"] <= 100.0
    assert block["evidence_timestamp"] == "2026-09-04T16:40:00Z"
    assert "AI_CIO_ENTERPRISE_DISCOVERY" in block["provenance"]
    assert block["evidence"]["catalyst_family_count"] == 10
    assert set(block["evidence"]["catalysts"]) == set(CATALYST_FAMILIES)


def test_theme_strength_fails_closed_when_market_evidence_is_partial():
    row = _row(); row["market_evidence"]["status"] = "PARTIAL"
    assert build_theme_strength_block(row, generated_at="2026-09-04T16:40:00Z") is None


def test_theme_strength_fails_closed_without_sector_confirmation():
    row = _row(); row["financial_health"]["components"].pop("sector_strength")
    assert build_theme_strength_block(row, generated_at="2026-09-04T16:40:00Z") is None


def test_theme_strength_fails_closed_without_fundamental_catalyst_inputs():
    row = _row(); row["financial_health"]["evidence"].pop("eps_growth")
    assert build_theme_strength_block(row, generated_at="2026-09-04T16:40:00Z") is None


def test_one_confirmed_family_gets_first_diminishing_slot_only():
    row = _row(source_evidence=[{"source": "Creator", "producer": "Creator", "source_class": "CREATOR_INTELLIGENCE", "mentioned_on": "2026-09-04", "story_id": "creator-1"}])
    row["financial_health"]["evidence"].update({"revenue_growth": 1.059, "eps_growth": 1.278, "analyst_upgrades_90d": 0.0, "analyst_downgrades_90d": 0.0})
    block = build_theme_strength_block(row, generated_at="2026-09-04T16:40:00Z")
    assert block is not None
    assert block["components"]["catalyst_support"] == 35.0
    assert block["evidence"]["confirmed_catalyst_families"] == ["earnings_fundamental_growth"]


def test_multiple_distinct_catalyst_families_use_diminishing_returns():
    evidence = [{
        "source": "Reviewed Professional",
        "producer": "Reviewed Professional",
        "source_class": "PROFESSIONAL_MEDIA",
        "mentioned_on": "2026-09-04",
        "story_id": "story-1",
        "product_innovation_related": True,
        "contracts_customer_wins_related": True,
        "capex_infrastructure_demand_related": True,
    }]
    row = _row(source_evidence=evidence)
    row["financial_health"]["evidence"].update({"revenue_growth": 0.2, "eps_growth": 0.2, "analyst_upgrades_90d": 0.0, "analyst_downgrades_90d": 0.0})
    block = build_theme_strength_block(row, generated_at="2026-09-04T16:40:00Z")
    assert block is not None
    # Earnings + product + contracts + infrastructure = 35 + 25 + 15 + 10.
    assert block["components"]["catalyst_support"] == 85.0
    assert block["evidence"]["confirmed_catalyst_count"] == 4


def test_repeated_same_catalyst_family_does_not_inflate_score():
    evidence = [
        {"source": "A", "producer": "A", "source_class": "PROFESSIONAL_MEDIA", "mentioned_on": "2026-09-04", "story_id": "a", "product_innovation_related": True},
        {"source": "B", "producer": "B", "source_class": "PRIMARY_COMPANY", "mentioned_on": "2026-09-04", "story_id": "b", "product_innovation_related": True},
    ]
    row = _row(source_evidence=evidence)
    row["financial_health"]["evidence"].update({"revenue_growth": -0.1, "eps_growth": -0.1, "analyst_upgrades_90d": 0.0, "analyst_downgrades_90d": 0.0})
    block = build_theme_strength_block(row, generated_at="2026-09-04T16:40:00Z")
    assert block is not None
    assert block["components"]["catalyst_support"] == 35.0
    assert block["evidence"]["confirmed_catalyst_families"] == ["product_innovation"]


def test_unclassified_title_does_not_create_product_or_contract_catalyst():
    row = _row(source_evidence=[{"source": "Creator", "producer": "Creator", "source_class": "CREATOR_INTELLIGENCE", "mentioned_on": "2026-09-04", "story_id": "x", "title": "Huge AI product and contract coming"}])
    row["financial_health"]["evidence"].update({"revenue_growth": -0.1, "eps_growth": -0.1, "analyst_upgrades_90d": 0.0, "analyst_downgrades_90d": 0.0})
    block = build_theme_strength_block(row, generated_at="2026-09-04T16:40:00Z")
    assert block is not None
    assert block["components"]["catalyst_support"] == 0.0


def test_attach_adds_block_without_changing_nomination_state():
    row = _row(nomination_eligible=False); report = {"observations": [row], "warnings": []}
    result = attach_candidate_theme_strength(report, generated_at="2026-09-04T16:40:00Z")
    assert result["observations"][0]["nomination_eligible"] is False
    assert "theme_strength" in result["observations"][0]
    assert result["theme_strength_policy"] == "GOVERNED_CATALYST_TAXONOMY_FAIL_CLOSED"


def test_retained_active_theme_is_reused_when_current_research_row_omits_theme():
    report = {"observations": [{"underlying_symbol": "NVDA", "nomination_eligible": False, "themes": []}]}
    active = {"NVDA": {"underlying_symbol": "NVDA", "nomination_eligible": True, "themes": ["Semiconductors"]}}
    result = _hydrate_retained_theme_context(report, active)
    assert result["observations"][0]["themes"] == ["Semiconductors"]
    assert result["observations"][0]["nomination_eligible"] is False


def test_exact_approved_market_industry_restores_theme_when_legacy_retention_lost_it():
    report = {"observations": [{"underlying_symbol": "NVDA", "nomination_eligible": False, "themes": [], "market_evidence": {"industry": "Semiconductors"}}]}
    active = {"NVDA": {"underlying_symbol": "NVDA", "nomination_eligible": True, "themes": []}}
    result = _hydrate_retained_theme_context(report, active)
    assert result["observations"][0]["themes"] == ["Semiconductors"]
    assert result["observations"][0]["nomination_eligible"] is False


def test_unapproved_market_industry_does_not_create_theme():
    report = {"observations": [{"underlying_symbol": "POOL", "nomination_eligible": False, "themes": [], "market_evidence": {"industry": "Home Improvement Retail"}}]}
    active = {"POOL": {"underlying_symbol": "POOL", "themes": []}}
    result = _hydrate_retained_theme_context(report, active)
    assert result["observations"][0]["themes"] == []


def test_weekly_and_swing_projection_preserve_theme_strength():
    row = _row(); row["theme_strength"] = build_theme_strength_block(row, generated_at="2026-09-04T16:40:00Z")
    report = build_weekly_discovery([row], generated_at="2026-09-04T16:45:00Z")
    swing = build_swing_projection(report)
    assert swing["candidates"][0]["theme_strength"] == row["theme_strength"]
