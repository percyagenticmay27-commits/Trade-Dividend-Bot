import json

from enterprise_discovery_targeted_sec_enrichment import enrich_active_candidates_with_sec_submissions


def _report():
    return {
        "observations": [
            {"underlying_symbol": "NVDA", "nomination_eligible": False, "source_evidence": [{"story_id": "BROAD:1", "form": "8-K"}]},
            {"underlying_symbol": "OTHER", "nomination_eligible": False, "source_evidence": []},
        ],
        "warnings": [],
    }


def test_only_active_present_symbol_gets_targeted_submission_lookup_and_item_codes():
    directory = {"fields": ["cik", "name", "ticker", "exchange"], "data": [[1045810, "NVIDIA CORP", "NVDA", "Nasdaq"], [1, "OTHER", "OTHER", "NYSE"]]}
    submissions = {"filings": {"recent": {
        "form": ["8-K"],
        "filingDate": ["2026-09-03"],
        "accessionNumber": ["0001045810-26-000123"],
        "primaryDocument": ["nvda.htm"],
        "items": ["1.01,2.02,7.01"],
    }}}
    urls = []
    def get_bytes(url, _ua):
        urls.append(url)
        return json.dumps(directory if "company_tickers" in url else submissions).encode()
    result = enrich_active_candidates_with_sec_submissions(
        _report(), {"NVDA"}, as_of="2026-09-04T18:00:00Z",
        user_agent="AI-CIO operator@example.com", get_bytes=get_bytes, minimum_request_interval=0,
    )
    nvda = result["observations"][0]
    targeted = [item for item in nvda["source_evidence"] if item.get("targeted_sec_enrichment")]
    assert len(targeted) == 1
    assert targeted[0]["sec_item_codes"] == ["1.01", "2.02", "7.01"]
    assert targeted[0]["targeted_sec_enrichment"]["catalyst_inference_used"] is False
    assert "catalyst_events" not in targeted[0]
    assert "reviewed_catalyst_events" not in targeted[0]
    assert len(urls) == 2
    assert result["targeted_sec_enrichment"]["target_count"] == 1
    assert result["targeted_sec_enrichment"]["enriched_count"] == 1


def test_non_active_symbols_are_not_fetched_or_enriched():
    directory = {"fields": ["cik", "name", "ticker", "exchange"], "data": [[1045810, "NVIDIA CORP", "NVDA", "Nasdaq"], [1, "OTHER", "OTHER", "NYSE"]]}
    submissions = {"filings": {"recent": {"form": [], "filingDate": [], "accessionNumber": [], "primaryDocument": [], "items": []}}}
    urls = []
    def get_bytes(url, _ua):
        urls.append(url)
        return json.dumps(directory if "company_tickers" in url else submissions).encode()
    result = enrich_active_candidates_with_sec_submissions(
        _report(), {"NVDA"}, as_of="2026-09-04T18:00:00Z",
        user_agent="AI-CIO operator@example.com", get_bytes=get_bytes, minimum_request_interval=0,
    )
    assert all("CIK0000000001" not in url for url in urls)
    assert result["observations"][1]["source_evidence"] == []


def test_missing_cik_fails_closed_without_event_or_nomination_change():
    directory = {"fields": ["cik", "name", "ticker", "exchange"], "data": []}
    result = enrich_active_candidates_with_sec_submissions(
        _report(), {"NVDA"}, as_of="2026-09-04T18:00:00Z",
        user_agent="AI-CIO operator@example.com",
        get_bytes=lambda *_: json.dumps(directory).encode(), minimum_request_interval=0,
    )
    nvda = result["observations"][0]
    assert nvda["nomination_eligible"] is False
    assert len(nvda["source_evidence"]) == 1
    assert "TARGETED_SEC_ENRICHMENT_MISSING_CIK:NVDA" in result["warnings"]


def test_item_codes_never_create_catalyst_events_by_themselves():
    directory = {"fields": ["cik", "name", "ticker", "exchange"], "data": [[1045810, "NVIDIA CORP", "NVDA", "Nasdaq"]]}
    submissions = {"filings": {"recent": {
        "form": ["8-K"], "filingDate": ["2026-09-03"],
        "accessionNumber": ["a"], "primaryDocument": ["a.htm"], "items": ["2.02,8.01"],
    }}}
    result = enrich_active_candidates_with_sec_submissions(
        _report(), {"NVDA"}, as_of="2026-09-04T18:00:00Z",
        user_agent="AI-CIO operator@example.com",
        get_bytes=lambda url, _: json.dumps(directory if "company_tickers" in url else submissions).encode(),
        minimum_request_interval=0,
    )
    item = result["observations"][0]["source_evidence"][-1]
    assert item["sec_item_codes"] == ["2.02", "8.01"]
    assert item["sec_filing_metadata"]["catalyst_inference_used"] is False
    assert "catalyst_events" not in item
    assert "reviewed_catalyst_events" not in item
