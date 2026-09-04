from enterprise_discovery_catalyst_extractor import (
    CATALYST_EXTRACTION_POLICY,
    enrich_evidence_item,
    enrich_observations_with_catalyst_events,
)


def _event(event_id="contract-1", family="contracts_customer_wins", **overrides):
    row = {
        "event_id": event_id,
        "family": family,
        "status": "CONFIRMED",
        "event_date": "2026-09-04",
        "reason": "Reviewed structured source confirms the event.",
        "favorable": True,
        "company_specific": True,
    }
    row.update(overrides)
    return row


def test_generic_sec_8k_never_becomes_positive_catalyst_by_form_alone():
    item, warnings = enrich_evidence_item({
        "source": "SEC EDGAR",
        "source_class": "PRIMARY_COMPANY",
        "story_id": "SEC:0001",
        "form": "8-K",
        "mentioned_on": "2026-09-04",
        "title": "8-K",
    })
    assert warnings == []
    assert "catalyst_events" not in item
    assert item["catalyst_extraction"]["accepted_event_count"] == 0
    assert item["catalyst_extraction"]["free_text_inference_used"] is False


def test_provider_topics_are_preserved_but_do_not_confirm_catalyst():
    item, warnings = enrich_evidence_item({
        "source": "Professional News",
        "source_class": "PROFESSIONAL_MEDIA",
        "authority": "PROFESSIONAL_MEDIA",
        "credibility_reviewed": True,
        "story_id": "news-1",
        "topics": [{"topic": "Mergers & Acquisitions", "relevance_score": "0.9"}],
        "provider_sentiment_label": "Bullish",
        "title": "Company update",
    })
    assert warnings == []
    assert item["structured_provider_topics"][0]["topic"] == "Mergers & Acquisitions"
    assert "catalyst_events" not in item
    assert item["catalyst_extraction"]["structured_provider_topic_count"] == 1


def test_primary_company_reviewed_structured_event_can_cross_boundary():
    item, warnings = enrich_evidence_item({
        "source": "Company IR",
        "source_class": "PRIMARY_COMPANY",
        "story_id": "ir-contract-1",
        "mentioned_on": "2026-09-04",
        "reviewed_catalyst_events": [_event()],
    })
    assert warnings == []
    assert item["catalyst_events"][0]["family"] == "contracts_customer_wins"
    assert item["catalyst_events"][0]["event_date"] == "2026-09-04T00:00:00Z"


def test_reviewed_professional_event_requires_reviewed_authority():
    item, warnings = enrich_evidence_item({
        "source": "Professional News",
        "source_class": "PROFESSIONAL_MEDIA",
        "authority": "PROFESSIONAL_MEDIA",
        "credibility_reviewed": False,
        "story_id": "news-2",
        "reviewed_catalyst_events": [_event()],
    })
    assert "catalyst_events" not in item
    assert warnings == ["UNTRUSTED_REVIEWED_CATALYST_EVENTS:news-2"]


def test_developing_or_nonfavorable_event_remains_nonscoring():
    item, warnings = enrich_evidence_item({
        "source": "SEC EDGAR",
        "source_class": "PRIMARY_COMPANY",
        "story_id": "SEC:0002",
        "reviewed_catalyst_events": [
            _event("developing", status="DEVELOPING"),
            _event("adverse", "regulatory_government", favorable=False),
        ],
    })
    assert "catalyst_events" not in item
    assert len(warnings) == 2
    assert all("NONSCORING_REVIEWED_CATALYST_EVENT" in warning for warning in warnings)


def test_no_headline_keyword_inference_for_product_or_contract():
    item, _ = enrich_evidence_item({
        "source": "Professional News",
        "source_class": "PROFESSIONAL_MEDIA",
        "authority": "PROFESSIONAL_MEDIA",
        "credibility_reviewed": True,
        "story_id": "news-3",
        "title": "Company launches breakthrough product and wins major contract",
    })
    assert "catalyst_events" not in item
    assert item["catalyst_extraction"]["policy"] == CATALYST_EXTRACTION_POLICY


def test_observation_enrichment_preserves_nomination_and_attaches_contract():
    report = {
        "observations": [{
            "underlying_symbol": "NVDA",
            "nomination_eligible": False,
            "source_evidence": [{
                "source": "SEC EDGAR",
                "source_class": "PRIMARY_COMPANY",
                "story_id": "SEC:0003",
                "reviewed_catalyst_events": [_event("product-1", "product_innovation")],
            }],
        }],
        "warnings": [],
    }
    enriched = enrich_observations_with_catalyst_events(report)
    row = enriched["observations"][0]
    assert row["nomination_eligible"] is False
    assert row["source_evidence"][0]["catalyst_events"][0]["family"] == "product_innovation"
    assert enriched["catalyst_extraction_policy"] == CATALYST_EXTRACTION_POLICY
