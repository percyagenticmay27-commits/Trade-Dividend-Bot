from datetime import date

from enterprise_discovery_sec_filing_metadata import (
    SEC_FILING_METADATA_POLICY,
    extract_recent_sec_filing_metadata,
)


def _payload():
    return {
        "filings": {
            "recent": {
                "form": ["8-K", "10-Q", "S-1", "4"],
                "filingDate": ["2026-09-04", "2026-09-03", "2026-08-01", "2026-09-04"],
                "accessionNumber": ["0001", "0002", "0003", "0004"],
                "primaryDocument": ["a.htm", "q.htm", "s1.htm", "form4.htm"],
                "items": ["1.01, 2.02; 7.01", "", None, ""],
            }
        }
    }


def test_preserves_structured_8k_item_codes_without_event_inference():
    rows = extract_recent_sec_filing_metadata(_payload(), cutoff=date(2026, 9, 1))
    row = rows[0]
    assert row["form"] == "8-K"
    assert row["sec_item_codes"] == ["1.01", "2.02", "7.01"]
    assert row["sec_filing_metadata"]["catalyst_inference_used"] is False
    assert row["sec_filing_metadata"]["policy"] == SEC_FILING_METADATA_POLICY
    assert "catalyst_events" not in row
    assert "catalyst_families" not in row


def test_periodic_report_metadata_is_preserved_but_not_scored():
    rows = extract_recent_sec_filing_metadata(_payload(), cutoff=date(2026, 9, 1))
    row = rows[1]
    assert row["form"] == "10-Q"
    assert row["accession_number"] == "0002"
    assert row["primary_document"] == "q.htm"
    assert row["sec_item_codes"] == []
    assert "reviewed_catalyst_events" not in row


def test_cutoff_and_form_allowlist_fail_closed():
    rows = extract_recent_sec_filing_metadata(_payload(), cutoff=date(2026, 9, 1))
    assert [row["form"] for row in rows] == ["8-K", "10-Q"]


def test_item_codes_are_deduplicated_in_provider_order():
    payload = {
        "filings": {"recent": {
            "form": ["8-K"],
            "filingDate": ["2026-09-04"],
            "accessionNumber": ["x"],
            "primaryDocument": ["x.htm"],
            "items": [["2.02", "1.01", "2.02", "7.01"]],
        }}
    }
    rows = extract_recent_sec_filing_metadata(payload, cutoff=date(2026, 9, 1))
    assert rows[0]["sec_item_codes"] == ["2.02", "1.01", "7.01"]


def test_malformed_recent_payload_returns_no_rows():
    assert extract_recent_sec_filing_metadata({"filings": {"recent": []}}, cutoff=date(2026, 9, 1)) == []
    assert extract_recent_sec_filing_metadata({}, cutoff=date(2026, 9, 1)) == []
