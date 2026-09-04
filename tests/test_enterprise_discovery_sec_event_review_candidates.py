from enterprise_discovery_sec_event_review_candidates import (
    attach_sec_event_review_candidates,
    enrich_report_with_sec_event_review_candidates,
)


def _evidence(codes):
    return {
        "source": "SEC EDGAR Targeted Submissions",
        "source_class": "PRIMARY_COMPANY",
        "mentioned_on": "2026-09-03",
        "story_id": "SEC:0001045810-26-000078",
        "form": "8-K",
        "filing_date": "2026-09-03",
        "accession_number": "0001045810-26-000078",
        "primary_document": "nvda-20260902.htm",
        "sec_item_codes": codes,
    }


def test_item_code_creates_review_required_candidate_not_event():
    result = attach_sec_event_review_candidates(_evidence(["8.01"]))
    candidate = result["sec_event_review_candidates"][0]
    assert candidate["status"] == "REVIEW_REQUIRED"
    assert candidate["sec_item_code"] == "8.01"
    assert candidate["possible_families_are_scoring"] is False
    assert candidate["favorable"] is None
    assert candidate["company_specific"] is None
    assert "catalyst_events" not in result
    assert "reviewed_catalyst_events" not in result
    assert "sec_reviewed_events" not in result
    assert result["sec_event_review_candidate_metadata"]["scoring_event_count"] == 0


def test_item_9_01_is_supporting_metadata_only():
    result = attach_sec_event_review_candidates(_evidence(["5.02", "7.01", "9.01"]))
    assert [row["sec_item_code"] for row in result["sec_event_review_candidates"]] == ["5.02", "7.01"]
    assert result["sec_event_review_candidate_metadata"]["item_9_01_supporting_metadata_only"] is True


def test_unknown_item_code_can_be_reviewed_without_family_guess():
    result = attach_sec_event_review_candidates(_evidence(["6.99"]))
    candidate = result["sec_event_review_candidates"][0]
    assert candidate["status"] == "REVIEW_REQUIRED"
    assert candidate["possible_catalyst_families"] == []
    assert candidate["possible_families_are_scoring"] is False


def test_non_primary_source_is_unchanged():
    item = {"source_class": "PROFESSIONAL_MEDIA", "sec_item_codes": ["8.01"]}
    assert attach_sec_event_review_candidates(item) == item


def test_report_layer_preserves_nomination_and_creates_no_scoring_events():
    report = {
        "observations": [{
            "underlying_symbol": "NVDA",
            "nomination_eligible": False,
            "source_evidence": [_evidence(["8.01"])],
        }],
        "warnings": [],
    }
    result = enrich_report_with_sec_event_review_candidates(report)
    row = result["observations"][0]
    evidence = row["source_evidence"][0]
    assert row["nomination_eligible"] is False
    assert result["sec_event_review_candidate_count"] == 1
    assert len(evidence["sec_event_review_candidates"]) == 1
    assert "catalyst_events" not in evidence
    assert "reviewed_catalyst_events" not in evidence
