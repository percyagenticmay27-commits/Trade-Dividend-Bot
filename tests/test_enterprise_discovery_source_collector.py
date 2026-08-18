import json

from enterprise_discovery_source_collector import collect_credential_free_observations


def test_sec_and_company_feed_create_provenanced_underlying_observation():
    sec = {"filings": {"recent": {"form": ["10-Q"], "filingDate": ["2026-08-15"], "accessionNumber": ["0001"], "primaryDocument": ["q2.htm"]}}}
    rss = b"<rss><channel><item><title>Company announces new platform</title><link>https://ir.example/news/1</link><pubDate>Sat, 15 Aug 2026 10:00:00 GMT</pubDate></item></channel></rss>"
    def get_bytes(url, user_agent):
        assert "operator@example.com" in user_agent
        return json.dumps(sec).encode() if "sec.gov" in url else rss
    result = collect_credential_free_observations([
        {"source_type": "SEC_SUBMISSIONS", "source_name": "SEC EDGAR", "underlying_symbol": "NVDA", "cik": "1045810"},
        {"source_type": "COMPANY_FEED", "source_name": "NVIDIA IR", "underlying_symbol": "NVDA", "url": "https://ir.example/feed.xml"},
    ], as_of="2026-08-17T01:00:00Z", user_agent="AI-CIO operator@example.com", get_bytes=get_bytes, minimum_request_interval=0)
    row = result["observations"][0]
    assert row["underlying_symbol"] == "NVDA"
    assert {item["source"] for item in row["source_evidence"]} == {"SEC EDGAR", "NVIDIA IR"}
    assert row["discovery_status"] == "NEW"


def test_market_snapshot_is_reused_without_inference():
    rss = b"<rss><channel><item><title>Update</title><link>https://ir.example/1</link><pubDate>2026-08-16</pubDate></item></channel></rss>"
    source = {"source_type": "RSS", "source_name": "Company IR", "underlying_symbol": "AMD", "url": "https://ir.example/feed.xml"}
    market = {"records": [{"symbol": "AMD", "price": 200.0, "volume": 12345, "is_stale": False}]}
    result = collect_credential_free_observations([source], as_of="2026-08-17T01:00:00Z", user_agent="AI-CIO operator@example.com", market_snapshot=market, get_bytes=lambda *_: rss, minimum_request_interval=0)
    assert result["observations"][0]["market_evidence"]["price"] == 200.0


def test_missing_or_malformed_sources_degrade_without_fabricating_candidates():
    sources = [{"source_type": "RSS", "source_name": "Broken Feed", "underlying_symbol": "AMD", "url": "http://insecure.example/feed"}]
    result = collect_credential_free_observations(sources, as_of="2026-08-17T01:00:00Z", user_agent="AI-CIO operator@example.com", get_bytes=lambda *_: b"")
    assert result["observations"] == []
    assert "HTTPS" in result["warnings"][0]


def test_no_user_agent_fails_closed():
    try:
        collect_credential_free_observations([], as_of="2026-08-17T01:00:00Z", user_agent="")
    except ValueError as exc:
        assert "User-Agent" in str(exc)
    else:
        raise AssertionError("missing user agent must fail closed")
