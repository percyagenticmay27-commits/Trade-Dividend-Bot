from enterprise_discovery_catalyst_evidence import (
    CATALYST_EVIDENCE_POLICY,
    CATALYST_EVENT_POLICY,
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


def _event(event_id="event-1", family="product_innovation", **overrides):
    event = {
        "event_id": event_id,
        "family": family,
        "status": "CONFIRMED",
        "event_date": "2026-09-04",
        "reason": "Explicit reviewed provider metadata confirms the event.",
        "favorable": True,
        "company_specific": True,
    }
    event.update(overrides)
    return event


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


def test_confirmed_favorable_company_specific_event_is_accepted():
    normalized, warnings = classify_evidence_item(
        _professional(catalyst_events=[_event()])
    )
    assert warnings == []
    assert normalized["catalyst_families"] == ["product_innovation"]
    assert normalized["product_innovation_related"] is True
    assert normalized["catalyst_events"][0]["event_id"] == "event-1"
    assert normalized["catalyst_events"][0]["event_date"] == "2026-09-04T00:00:00Z"
    assert normalized["catalyst_classification"]["event_policy"] == CATALYST_EVENT_POLICY
    assert normalized["catalyst_classification"]["accepted_event_count"] == 1


def test_duplicate_event_id_is_deduplicated():
    normalized, warnings = classify_evidence_item(
        _professional(catalyst_events=[_event(), _event(family="contracts_customer_wins")])
    )
    assert len(normalized["catalyst_events"]) == 1
    assert normalized["catalyst_families"] == ["product_innovation"]
    assert any(value == "DUPLICATE_CATALYST_EVENT:event-1" for value in warnings)


def test_nonfavorable_ma_event_is_rejected_from_scoring():
    normalized, warnings = classify_evidence_item(
        _professional(
            catalyst_events=[
                _event("ma-1", "ma_strategic_activity", favorable=False)
            ]
        )
    )
    assert normalized["catalyst_events"] == []
    assert normalized["ma_strategic_activity_related"] is False
    assert any(value == "NONFAVORABLE_CATALYST_EVENT_REJECTED:ma-1" for value in warnings)


def test_developing_event_is_retained_fail_closed_as_warning_but_not_scored():
    normalized, warnings = classify_evidence_item(
        _professional(catalyst_events=[_event(status="DEVELOPING")])
    )
    assert normalized["catalyst_events"] == []
    assert normalized["product_innovation_related"] is False
    assert any(value == "NONCONFIRMED_CATALYST_EVENT_REJECTED:event-1:DEVELOPING" for value in warnings)


def test_unreviewed_professional_event_is_rejected():
    normalized, warnings = classify_evidence_item(
        _professional(
            credibility_reviewed=False,
            authority="DISCOVERY_ONLY",
            catalyst_events=[_event()],
        )
    )
    assert normalized["catalyst_events"] == []
    assert normalized["product_innovation_related"] is False
    assert any(value == "UNREVIEWED_CATALYST_EVENT_REJECTED:event-1" for value in warnings)


def test_event_requires_explicit_id_date_reason_and_company_specific_state():
    normalized, warnings = classify_evidence_item(
        _professional(
            catalyst_events=[
                _event(event_id=""),
                _event("bad-date", event_date="not-a-date"),
                _event("no-reason", reason=""),
                _event("sector-only", company_specific=False),
            ]
        )
    )
    assert normalized["catalyst_events"] == []
    assert len(warnings) == 4


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
    assert result["catalyst_event_policy"] == CATALYST_EVENT_POLICY
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


def test_structured_events_raise_theme_strength_without_headline_inference():
    evidence = [
        _professional(
            title="Generic company update",
            catalyst_events=[
                _event("product-1", "product_innovation"),
                _event("contract-1", "contracts_customer_wins"),
            ],
        )
    ]
    report = {"observations": [_theme_row(evidence)], "warnings": []}
    attach_candidate_catalyst_classification(report)
    block = build_theme_strength_block(report["observations"][0], generated_at="2026-09-04T18:00:00Z")
    assert block is not None
    assert block["components"]["catalyst_support"] == 60.0
    assert block["evidence"]["confirmed_catalyst_families"] == [
        "product_innovation",
        "contracts_customer_wins",
    ]