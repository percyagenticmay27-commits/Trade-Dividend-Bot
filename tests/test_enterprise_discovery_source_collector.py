import json

from enterprise_discovery_source_collector import collect_broad_sec_filing_evidence, collect_credential_free_observations, collect_professional_feed_evidence, collect_youtube_evidence
from enterprise_weekly_market_discovery import build_swing_projection, build_weekly_discovery


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


def test_broad_sec_index_maps_cik_to_underlying_but_remains_evidence_only():
    tickers = {"fields": ["cik", "name", "ticker", "exchange"], "data": [[1045810, "NVIDIA CORP", "NVDA", "Nasdaq"]]}
    index = b"Description\n-----\n1045810|NVIDIA CORP|8-K|2026-08-14|edgar/data/1045810/filing.txt\n"
    def get_bytes(url, _user_agent):
        return json.dumps(tickers).encode() if "company_tickers" in url else index
    evidence, warnings = collect_broad_sec_filing_evidence(
        as_of="2026-08-17T01:00:00Z", user_agent="AI-CIO operator@example.com",
        get_bytes=get_bytes, index_dates=["2026-08-14"], minimum_request_interval=0,
    )
    assert warnings == []
    assert evidence[0]["underlying_symbol"] == "NVDA"
    source = {"source_type": "SEC_DAILY_INDEX", "source_name": "SEC Broad", "index_dates": ["2026-08-14"]}
    collected = collect_credential_free_observations([source], as_of="2026-08-17T01:00:00Z", user_agent="AI-CIO operator@example.com", get_bytes=get_bytes, minimum_request_interval=0)
    row = collected["observations"][0]
    assert row["nomination_eligible"] is False
    report = build_weekly_discovery(collected["observations"], generated_at="2026-08-17T01:00:00Z")
    assert build_swing_projection(report)["candidates"] == []


def test_exchange_directory_filters_otc_units_preferred_and_leveraged_products():
    tickers = {
        "fields": ["cik", "name", "ticker", "exchange"],
        "data": [
            [1, "OPERATING COMPANY", "GOOD", "NYSE"],
            [2, "FOREIGN OTC COMPANY", "BADAF", ""],
            [3, "SPAC UNIT", "SPACU", "Nasdaq"],
            [4, "ISSUER PREFERRED", "ISS-PF", "NYSE"],
            [5, "DAILY 3X BULL ETF", "BULL", "NYSE Arca"],
            [1, "OPERATING COMPANY CLASS B", "GOOD-B", "NYSE"],
        ],
    }
    index = (
        b"Description\n-----\n"
        b"1|OPERATING COMPANY|8-K|2026-08-14|edgar/data/1/a.txt\n"
        b"2|FOREIGN OTC COMPANY|8-K|2026-08-14|edgar/data/2/a.txt\n"
        b"3|SPAC UNIT|8-K|2026-08-14|edgar/data/3/a.txt\n"
        b"4|ISSUER PREFERRED|8-K|2026-08-14|edgar/data/4/a.txt\n"
        b"5|DAILY 3X BULL ETF|8-K|2026-08-14|edgar/data/5/a.txt\n"
    )
    evidence, warnings = collect_broad_sec_filing_evidence(
        as_of="2026-08-17T01:00:00Z", user_agent="AI-CIO operator@example.com",
        get_bytes=lambda url, _: json.dumps(tickers).encode() if "company_tickers" in url else index,
        index_dates=["2026-08-14"], minimum_request_interval=0,
    )
    assert warnings == []
    assert [row["underlying_symbol"] for row in evidence] == ["GOOD"]
    assert evidence[0]["exchange"] == "NYSE"


def test_reviewed_professional_feed_matches_only_known_explicit_underlyings():
    rss = b"""<rss><channel>
      <item><title>SMCI stock rises after earnings</title><link>https://media.example/smci</link><pubDate>Sun, 16 Aug 2026 10:00:00 GMT</pubDate></item>
      <item><title>UNKNOWN stock is discussed</title><link>https://media.example/unknown</link><pubDate>Sun, 16 Aug 2026 11:00:00 GMT</pubDate></item>
    </channel></rss>"""
    rows, warnings = collect_professional_feed_evidence(
        [{
            "source_type": "PROFESSIONAL_RSS",
            "source_name": "Reviewed Financial News",
            "producer": "Reviewed Financial News",
            "url": "https://media.example/rss",
            "authority": "PROFESSIONAL_MEDIA",
            "credibility_reviewed": True,
        }],
        as_of="2026-08-17T01:00:00Z",
        allowed_symbols=["SMCI"],
        user_agent="AI-CIO operator@example.com",
        get_bytes=lambda *_: rss,
    )
    assert warnings == []
    assert [row["underlying_symbol"] for row in rows] == ["SMCI"]
    assert rows[0]["evidence"]["source_class"] == "PROFESSIONAL_MEDIA"
    assert rows[0]["evidence"]["platform"] == "PROFESSIONAL_RSS"
    assert rows[0]["confirmation_eligible"] is True


def test_professional_feed_retries_one_transient_timeout(monkeypatch):
    rss = b"<rss><channel><item><title>SMCI stock update</title><link>https://media.example/smci</link><pubDate>Sun, 16 Aug 2026 10:00:00 GMT</pubDate></item></channel></rss>"
    calls = []
    def transient(*_):
        calls.append(1)
        if len(calls) == 1:
            raise TimeoutError("temporary CDN stall")
        return rss
    monkeypatch.setattr("enterprise_discovery_source_collector.time.sleep", lambda *_: None)
    rows, warnings = collect_professional_feed_evidence(
        [{
            "source_type": "PROFESSIONAL_RSS",
            "source_name": "Reviewed Financial News",
            "url": "https://media.example/rss",
            "authority": "PROFESSIONAL_MEDIA",
            "credibility_reviewed": True,
        }],
        as_of="2026-08-17T01:00:00Z",
        allowed_symbols=["SMCI"],
        user_agent="AI-CIO operator@example.com",
        get_bytes=transient,
    )
    assert len(calls) == 2
    assert warnings == []
    assert rows[0]["underlying_symbol"] == "SMCI"


def test_unreviewed_professional_feed_fails_closed():
    rows, warnings = collect_professional_feed_evidence(
        [{
            "source_type": "PROFESSIONAL_RSS",
            "source_name": "Unreviewed Feed",
            "url": "https://media.example/rss",
            "authority": "PROFESSIONAL_MEDIA",
            "credibility_reviewed": False,
        }],
        as_of="2026-08-17T01:00:00Z",
        allowed_symbols=["SMCI"],
        user_agent="AI-CIO operator@example.com",
        get_bytes=lambda *_: b"<rss/>",
    )
    assert rows == []
    assert "not credibility-reviewed" in warnings[0]


def test_reviewed_professional_feed_can_confirm_existing_sec_lead():
    tickers = {"fields": ["cik", "name", "ticker", "exchange"], "data": [[1375365, "SUPER MICRO COMPUTER", "SMCI", "Nasdaq"]]}
    index = b"Description\n-----\n1375365|SUPER MICRO COMPUTER|8-K|2026-08-14|edgar/data/1375365/a.txt\n"
    rss = b"<rss><channel><item><title>SMCI stock gains after earnings</title><link>https://media.example/smci</link><pubDate>Sun, 16 Aug 2026 10:00:00 GMT</pubDate></item></channel></rss>"
    def get_bytes(url, _user_agent):
        if "company_tickers" in url:
            return json.dumps(tickers).encode()
        if "media.example" in url:
            return rss
        return index
    result = collect_credential_free_observations([
        {"source_type": "SEC_DAILY_INDEX", "source_name": "SEC Broad", "index_dates": ["2026-08-14"]},
        {
            "source_type": "PROFESSIONAL_RSS",
            "source_name": "Reviewed Financial News",
            "producer": "Reviewed Financial News",
            "url": "https://media.example/rss",
            "authority": "PROFESSIONAL_MEDIA",
            "credibility_reviewed": True,
        },
    ], as_of="2026-08-17T01:00:00Z", user_agent="AI-CIO operator@example.com", get_bytes=get_bytes, minimum_request_interval=0)
    row = result["observations"][0]
    assert row["underlying_symbol"] == "SMCI"
    assert row["nomination_eligible"] is True
    assert {item["source_class"] for item in row["source_evidence"]} == {"PRIMARY_COMPANY", "PROFESSIONAL_MEDIA"}


def test_youtube_search_is_bounded_and_only_matches_known_underlyings():
    payload = {"items": [
        {"id": {"videoId": "v1"}, "snippet": {"publishedAt": "2026-08-16T12:00:00Z", "channelId": "channel-1", "channelTitle": "Reviewed Analyst", "title": "$NVDA earnings and NVDX trading", "description": "NVDA demand review"}},
        {"id": {"videoId": "v2"}, "snippet": {"publishedAt": "2026-08-16T13:00:00Z", "channelId": "wrong-channel", "channelTitle": "Imposter", "title": "AMD", "description": ""}},
    ]}
    requested = []
    rows, warnings = collect_youtube_evidence(
        [{"source_type": "YOUTUBE_SEARCH", "source_name": "Reviewed Analyst", "channel_id": "channel-1", "query": "weekly stocks", "max_results": 50, "authority": "REVIEWED_CREATOR", "credibility_reviewed": True}],
        as_of="2026-08-17T01:00:00Z", api_key="secret-key", allowed_symbols=["NVDA", "AMD"],
        user_agent="AI-CIO operator@example.com", get_bytes=lambda url, _: requested.append(url) or json.dumps(payload).encode(),
    )
    assert warnings == []
    assert [row["underlying_symbol"] for row in rows] == ["NVDA"]
    assert rows[0]["confirmation_eligible"] is True
    assert "maxResults=25" in requested[0]


def test_short_ticker_requires_cashtag_in_youtube_prose():
    from enterprise_discovery_source_collector import _youtube_symbols
    assert _youtube_symbols("This could be important", ["BE"]) == []
    assert _youtube_symbols("Why $BE moved this week", ["BE"]) == ["BE"]


def test_common_words_and_generic_descriptions_are_not_ticker_mentions():
    from enterprise_discovery_source_collector import _youtube_symbols
    text = "These companies HELP you build wealth. This portfolio is MINE. MFG data follows."
    assert _youtube_symbols(text, ["HELP", "MINE", "MFG"]) == []
    assert _youtube_symbols("Super Micro Computer (SMCI) Stock Roller-Coaster", ["SMCI"]) == ["SMCI"]


def test_missing_youtube_key_degrades_without_fabricating_evidence():
    rows, warnings = collect_youtube_evidence(
        [{"source_type": "YOUTUBE_SEARCH", "query": "stocks"}],
        as_of="2026-08-17T01:00:00Z", api_key="", allowed_symbols=["NVDA"],
        user_agent="AI-CIO operator@example.com",
    )
    assert rows == []
    assert "unavailable" in warnings[0]


def test_reviewed_youtube_can_confirm_sec_lead_but_unreviewed_source_cannot():
    tickers = {"fields": ["cik", "name", "ticker", "exchange"], "data": [[1045810, "NVIDIA CORP", "NVDA", "Nasdaq"]]}
    index = b"Description\n-----\n1045810|NVIDIA CORP|8-K|2026-08-14|edgar/data/1045810/a.txt\n"
    youtube = {"items": [{"id": {"videoId": "v1"}, "snippet": {"publishedAt": "2026-08-16T12:00:00Z", "channelId": "channel-1", "channelTitle": "Reviewed Analyst", "title": "NVDA stock weekly review", "description": ""}}]}
    def get_bytes(url, _user_agent):
        if "company_tickers" in url:
            return json.dumps(tickers).encode()
        if "youtube" in url:
            return json.dumps(youtube).encode()
        return index
    sources = [
        {"source_type": "SEC_DAILY_INDEX", "source_name": "SEC Broad", "index_dates": ["2026-08-14"]},
        {"source_type": "YOUTUBE_SEARCH", "source_name": "Reviewed Analyst", "channel_id": "channel-1", "authority": "REVIEWED_CREATOR", "credibility_reviewed": True},
    ]
    result = collect_credential_free_observations(
        sources, as_of="2026-08-17T01:00:00Z", user_agent="AI-CIO operator@example.com",
        youtube_api_key="secret-key", get_bytes=get_bytes, minimum_request_interval=0,
    )
    assert result["observations"][0]["nomination_eligible"] is True
    assert {item["source_class"] for item in result["observations"][0]["source_evidence"]} == {"PRIMARY_COMPANY", "CREATOR_INTELLIGENCE"}

    sources[1]["credibility_reviewed"] = False
    unreviewed = collect_credential_free_observations(
        sources, as_of="2026-08-17T01:00:00Z", user_agent="AI-CIO operator@example.com",
        youtube_api_key="secret-key", get_bytes=get_bytes, minimum_request_interval=0,
    )
    assert unreviewed["observations"][0]["nomination_eligible"] is False
