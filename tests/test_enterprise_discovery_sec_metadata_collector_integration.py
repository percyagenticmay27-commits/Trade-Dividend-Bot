import json

from enterprise_discovery_source_collector import collect_credential_free_observations


def _collect(sec_payload):
    return collect_credential_free_observations(
        [{
            "source_type": "SEC_SUBMISSIONS",
            "source_name": "SEC EDGAR",
            "underlying_symbol": "NVDA",
            "cik": "1045810",
        }],
        as_of="2026-09-04T18:00:00Z",
        user_agent="AI-CIO operator@example.com",
        get_bytes=lambda *_: json.dumps(sec_payload).encode(),
        minimum_request_interval=0,
    )


def test_sec_submissions_collector_preserves_item_codes_and_metadata_policy():
    payload = {"filings": {"recent": {
        "form": ["8-K"],
        "filingDate": ["2026-09-03"],
        "accessionNumber": ["0001045810-26-000123"],
        "primaryDocument": ["nvda-20260903.htm"],
        "items": ["1.01,2.02,7.01"],
    }}}
    result = _collect(payload)
    evidence = result["observations"][0]["source_evidence"][0]
    assert evidence["form"] == "8-K"
    assert evidence["filing_date"] == "2026-09-03"
    assert evidence["accession_number"] == "0001045810-26-000123"
    assert evidence["primary_document"] == "nvda-20260903.htm"
    assert evidence["sec_item_codes"] == ["1.01", "2.02", "7.01"]
    assert evidence["sec_filing_metadata"]["catalyst_inference_used"] is False
    assert evidence["earnings_growth_related"] is False
    assert "reviewed_catalyst_events" not in evidence
    assert "catalyst_events" not in evidence


def test_periodic_form_retains_existing_family_behavior_but_metadata_adds_no_event():
    payload = {"filings": {"recent": {
        "form": ["10-Q"],
        "filingDate": ["2026-09-03"],
        "accessionNumber": ["0002"],
        "primaryDocument": ["q3.htm"],
        "items": [""],
    }}}
    evidence = _collect(payload)["observations"][0]["source_evidence"][0]
    assert evidence["earnings_growth_related"] is True
    assert evidence["sec_item_codes"] == []
    assert evidence["sec_filing_metadata"]["item_codes_preserved"] is False
    assert evidence["sec_filing_metadata"]["catalyst_inference_used"] is False
    assert "reviewed_catalyst_events" not in evidence


def test_misaligned_items_array_fails_closed_to_empty_codes():
    payload = {"filings": {"recent": {
        "form": ["8-K", "8-K"],
        "filingDate": ["2026-09-03", "2026-09-02"],
        "accessionNumber": ["a", "b"],
        "primaryDocument": ["a.htm", "b.htm"],
        "items": ["1.01"],
    }}}
    evidence = _collect(payload)["observations"][0]["source_evidence"]
    by_accession = {item["accession_number"]: item for item in evidence}
    assert by_accession["a"]["sec_item_codes"] == ["1.01"]
    assert by_accession["b"]["sec_item_codes"] == []
    assert all("reviewed_catalyst_events" not in item for item in evidence)
