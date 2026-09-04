from enterprise_discovery_catalyst_extractor import enrich_evidence_item
from enterprise_discovery_sec_catalyst_events import attach_sec_reviewed_catalyst_events, enrich_report_with_sec_reviewed_events


def _sec(**extra):
    row = {
        "source": "SEC EDGAR",
        "source_class": "PRIMARY_COMPANY",
        "mentioned_on": "2026-09-04",
        "story_id": "SEC:0001",
        "form": "8-K",
        "accession_number": "0001",
        "primary_document": "event.htm",
    }
    row.update(extra)
    return row


def test_generic_8k_never_creates_confirmed_event():
    row, warnings = attach_sec_reviewed_catalyst_events(_sec())
    assert warnings == []
    assert "reviewed_catalyst_events" not in row
    assert row["sec_catalyst_event_production"]["accepted_event_count"] == 0


def test_periodic_report_form_alone_never_creates_confirmed_event():
    row, warnings = attach_sec_reviewed_catalyst_events(_sec(form="10-Q"))
    assert warnings == []
    assert "reviewed_catalyst_events" not in row


def test_explicit_reviewed_favorable_company_specific_event_is_produced():
    row, warnings = attach_sec_reviewed_catalyst_events(_sec(sec_reviewed_events=[{
        "event_id": "SEC:0001:guidance",
        "family": "guidance_outlook",
        "status": "CONFIRMED",
        "event_date": "2026-09-04",
        "reason": "Reviewed filing metadata confirms favorable company guidance.",
        "favorable": True,
        "company_specific": True,
    }]))
    assert warnings == []
    event = row["reviewed_catalyst_events"][0]
    assert event["family"] == "guidance_outlook"
    assert event["provenance"]["accession_number"] == "0001"
    assert event["provenance"]["primary_document"] == "event.htm"


def test_unfavorable_or_developing_reviewed_event_does_not_cross_boundary():
    row, warnings = attach_sec_reviewed_catalyst_events(_sec(sec_reviewed_events=[{
        "event_id": "SEC:0001:developing",
        "family": "ma_strategic_activity",
        "status": "DEVELOPING",
        "event_date": "2026-09-04",
        "reason": "Transaction remains under review.",
        "favorable": True,
        "company_specific": True,
    }]))
    assert "reviewed_catalyst_events" not in row
    assert warnings == ["NONSCORING_SEC_REVIEWED_EVENT:0001:SEC:0001:developing"]


def test_unknown_family_fails_closed():
    row, warnings = attach_sec_reviewed_catalyst_events(_sec(sec_reviewed_events=[{
        "event_id": "SEC:0001:x",
        "family": "headline_hype",
        "status": "CONFIRMED",
        "event_date": "2026-09-04",
        "reason": "Not governed.",
        "favorable": True,
        "company_specific": True,
    }]))
    assert "reviewed_catalyst_events" not in row
    assert warnings


def test_produced_sec_event_is_accepted_by_existing_extractor():
    produced, warnings = attach_sec_reviewed_catalyst_events(_sec(sec_reviewed_events=[{
        "event_id": "SEC:0001:contract",
        "family": "contracts_customer_wins",
        "status": "CONFIRMED",
        "event_date": "2026-09-04",
        "reason": "Reviewed filing metadata confirms a favorable customer award.",
        "favorable": True,
        "company_specific": True,
    }]))
    assert warnings == []
    extracted, extraction_warnings = enrich_evidence_item(produced)
    assert extraction_warnings == []
    assert extracted["catalyst_events"][0]["event_id"] == "SEC:0001:contract"
    assert extracted["catalyst_events"][0]["provenance"]["accession_number"] == "0001"


def test_report_enrichment_does_not_change_nomination_eligibility():
    report = {"observations": [{"underlying_symbol": "NVDA", "nomination_eligible": False, "source_evidence": [_sec()]}], "warnings": []}
    enriched = enrich_report_with_sec_reviewed_events(report)
    assert enriched["observations"][0]["nomination_eligible"] is False
    assert enriched["sec_catalyst_event_policy"] == "EXPLICIT_REVIEWED_SEC_EVENT_METADATA_ONLY"
