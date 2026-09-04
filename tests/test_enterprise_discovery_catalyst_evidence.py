from enterprise_discovery_catalyst_evidence import (
    CATALYST_EVIDENCE_POLICY,
    attach_candidate_catalyst_classification,
    classify_evidence_item,
)
from enterprise_discovery_theme_strength import build_theme_strength_block


def _professional(**overrides):
    item = {
        "source": "Reuters",
        "producer": "Reuters",
        "source_class": "PROFESSIONAL_MEDIA",
        "story_id": "story-1",
        "mentioned_on": "2026-09-04",
        "credibility_reviewed": True,
        "authority": "PROFESSIONAL_MEDIA",
    }
    item.update(overrides)
    return item


def _theme_row(evidence):
    return {
        "underlying_symbol": "NVDA",
        "themes": ["Semiconductors"],
        "source_evidence": evidence,
        "market_evidence": {
            "status": "AVAILABLE",
            "relative_strength_vs_benchmark_percent": 2.0,
            "volume_expansion_ratio": 1.2,
            "latest_session": "2026-09-04",
            "benchmark_symbol": "SPY",
            "is_stale": False,
        },
        "financial_health": {
            "components": {"sector_strength": 70.0},
            "evidence_timestamp": "2026-09-04T16:35:35Z",
            "evidence": {
                "revenue_growth": -0.10,
                "eps_growth": -0.10,
                "analyst_upgrades_90d": 0.0,
                "analyst_downgrades_90d": 0.0,
            },
        },
    }


def test_reviewed_professional_explicit_family_is_accepted():
    normalized, warnings = classify_evidence_item(
        _professional(catalyst_families=["product_innovation"])
    )
    assert warnings == []
    assert normalized["catalyst_families"] == ["product_innovation"]
    assert normalized["product_innovation_related"] is True
    assert normalized["catalyst_classification"]["source_eligible"] is True


def test_unknown_family_is_ignored_fail_closed():
    normalized, warnings = classify_evidence_item(
        _professional(catalyst_families=["magic_momentum"])
    )
    assert normalized["catalyst_families"] == []
    assert any(value.startswith("UNKNOWN_CATALYST_FAMILY:") for value in warnings)


def test_headline_text_never_creates_a_catalyst():
    normalized, warnings = classify_evidence_item(
        _professional(title="Huge AI product launch and customer contract")
    )
    assert warnings == []
    assert normalized["catalyst_families"] == []
    assert normalized["product_innovation_related"] is False
    assert normalized["contracts_customer_wins_related"] is False


def test_unreviewed_creator_claim_is_rejected():
    item = {
        "source": "Creator",
        "producer": "Creator",
        "source_class": "CREATOR_INTELLIGENCE",
        "story_id": "video-1",
        "mentioned_on": "2026-09-04",
        "credibility_reviewed": False,
        "authority": "DISCOVERY_ONLY",
        "catalyst_families": ["capex_infrastructure_demand"],
    }
    normalized, warnings = classify_evidence_item(item)
    assert normalized["catalyst_families"] == []
    assert normalized["capex_infrastructure_demand_related"] is False
    assert any(value.startswith("UNREVIEWED_CATALYST_EVIDENCE_REJECTED:") for value in warnings)


def test_primary_company_explicit_claim_is_authoritative_without_review_flag():
    item = {
        "source": "SEC EDGAR",
        "producer": "U.S. Securities and Exchange Commission",
        "source_class": "PRIMARY_COMPANY",
        "story_id": "sec-1",
        "mentioned_on": "2026-09-04",
        "guidance_outlook_related": True,
    }
    normalized, warnings = classify_evidence_item(item)
    assert warnings == []
    assert normalized["catalyst_families"] == ["guidance_outlook"]
    assert normalized["guidance_outlook_related"] is True


def test_attach_preserves_nomination_state_and_sets_policy():
    row = {
        "underlying_symbol": "NVDA",
        "nomination_eligible": False,
        "source_evidence": [_professional(product_innovation_related=True)],
    }
    report = {"observations": [row], "warnings": []}
    result = attach_candidate_catalyst_classification(report)
    assert result["observations"][0]["nomination_eligible"] is False
    assert result["catalyst_evidence_policy"] == CATALYST_EVIDENCE_POLICY
    assert result["observations"][0]["source_evidence"][0]["product_innovation_related"] is True


def test_repeated_same_family_remains_one_theme_strength_family():
    evidence = [
        _professional(story_id="a", product_innovation_related=True),
        _professional(story_id="b", producer="Bloomberg", source="Bloomberg", product_innovation_related=True),
    ]
    report = {"observations": [_theme_row(evidence)], "warnings": []}
    attach_candidate_catalyst_classification(report)
    block = build_theme_strength_block(report["observations"][0], generated_at="2026-09-04T18:00:00Z")
    assert block is not None
    assert block["components"]["catalyst_support"] == 35.0
    assert block["evidence"]["confirmed_catalyst_families"] == ["product_innovation"]


def test_distinct_reviewed_families_raise_catalyst_support_with_diminishing_returns():
    evidence = [
        _professional(story_id="p", product_innovation_related=True),
        _professional(story_id="c", contracts_customer_wins_related=True),
        _professional(story_id="i", capex_infrastructure_demand_related=True),
    ]
    report = {"observations": [_theme_row(evidence)], "warnings": []}
    attach_candidate_catalyst_classification(report)
    block = build_theme_strength_block(report["observations"][0], generated_at="2026-09-04T18:00:00Z")
    assert block is not None
    assert block["components"]["catalyst_support"] == 75.0
    assert block["evidence"]["confirmed_catalyst_count"] == 3
