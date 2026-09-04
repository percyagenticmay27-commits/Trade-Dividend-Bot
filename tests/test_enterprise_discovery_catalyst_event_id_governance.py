from enterprise_discovery_catalyst_evidence import attach_candidate_catalyst_classification


def _source(story_id, source="Reuters", **extra):
    row = {
        "source": source,
        "source_class": "PROFESSIONAL_MEDIA",
        "story_id": story_id,
        "mentioned_on": "2026-09-04",
        "credibility_reviewed": True,
        "authority": "PROFESSIONAL_MEDIA",
    }
    row.update(extra)
    return row


def _event(event_id="event-1", family="product_innovation", **extra):
    row = {
        "event_id": event_id,
        "family": family,
        "status": "CONFIRMED",
        "event_date": "2026-09-04",
        "reason": "Reviewed structured evidence confirms the event.",
        "favorable": True,
        "company_specific": True,
        "source": "Reuters",
        "source_url": "https://example.test/event-1",
        "provenance": "PROFESSIONAL_MEDIA",
    }
    row.update(extra)
    return row


def _report(evidence):
    return {
        "observations": [{
            "underlying_symbol": "NVDA",
            "nomination_eligible": False,
            "source_evidence": evidence,
        }],
        "warnings": [],
    }


def test_identical_event_id_across_evidence_keeps_first_only():
    result = attach_candidate_catalyst_classification(_report([
        _source("story-a", catalyst_events=[_event()]),
        _source("story-b", catalyst_events=[_event()]),
    ]))
    evidence = result["observations"][0]["source_evidence"]
    assert [len(item["catalyst_events"]) for item in evidence] == [1, 0]
    assert "DUPLICATE_CATALYST_EVENT_ACROSS_EVIDENCE:event-1" in result["warnings"]
    assert evidence[0]["catalyst_classification"]["accepted_event_count"] == 1
    assert evidence[1]["catalyst_classification"]["accepted_event_count"] == 0


def test_conflicting_event_family_for_same_id_fails_closed_everywhere():
    result = attach_candidate_catalyst_classification(_report([
        _source("story-a", catalyst_events=[_event()]),
        _source("story-b", catalyst_events=[_event(family="contracts_customer_wins")]),
    ]))
    evidence = result["observations"][0]["source_evidence"]
    assert all(item["catalyst_events"] == [] for item in evidence)
    assert all(item["catalyst_families"] == [] for item in evidence)
    assert "CONFLICTING_CATALYST_EVENT_ID:event-1" in result["warnings"]


def test_conflicting_provenance_for_same_id_fails_closed():
    result = attach_candidate_catalyst_classification(_report([
        _source("story-a", catalyst_events=[_event(provenance="SEC:0001")]),
        _source("story-b", catalyst_events=[_event(provenance="MEDIA:abc")]),
    ]))
    evidence = result["observations"][0]["source_evidence"]
    assert all(item["catalyst_events"] == [] for item in evidence)
    assert "CONFLICTING_CATALYST_EVENT_ID:event-1" in result["warnings"]


def test_explicit_family_survives_conflicting_event_removal():
    result = attach_candidate_catalyst_classification(_report([
        _source(
            "story-a",
            catalyst_families=["product_innovation"],
            catalyst_events=[_event()],
        ),
        _source("story-b", catalyst_events=[_event(family="contracts_customer_wins")]),
    ]))
    evidence = result["observations"][0]["source_evidence"]
    assert evidence[0]["catalyst_events"] == []
    assert evidence[0]["catalyst_families"] == ["product_innovation"]
    assert evidence[0]["product_innovation_related"] is True
    assert evidence[1]["catalyst_families"] == []


def test_duplicate_governance_does_not_change_nomination_state():
    report = _report([
        _source("story-a", catalyst_events=[_event()]),
        _source("story-b", catalyst_events=[_event()]),
    ])
    result = attach_candidate_catalyst_classification(report)
    assert result["observations"][0]["nomination_eligible"] is False
