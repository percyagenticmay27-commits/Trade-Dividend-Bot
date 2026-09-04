from enterprise_discovery_official_macro_sources import collect_official_macro_evidence


def test_vetted_official_feed_is_collected_non_scoring():
    rss = b"<rss><channel><item><title>Official release</title><link>https://agency.gov/release/1</link><pubDate>Thu, 03 Sep 2026 12:00:00 GMT</pubDate></item></channel></rss>"
    result = collect_official_macro_evidence([
        {
            "source_name": "Official Agency",
            "tier": "TIER_1_PRIMARY_OFFICIAL",
            "source_class": "GOVERNMENT_PRIMARY",
            "roles": ["macro"],
            "url": "https://agency.gov/feed.xml",
        }
    ], as_of="2026-09-04T12:00:00Z", user_agent="AI-CIO operator@example.com", get_bytes=lambda *_: rss)
    assert result["evidence_count"] == 1
    row = result["evidence"][0]
    assert row["scoring_eligible"] is False
    assert row["symbol_linkage"] is None
    assert row["catalyst_inference_used"] is False
    assert result["scoring_event_count"] == 0


def test_untrusted_class_is_rejected():
    result = collect_official_macro_evidence([
        {
            "source_name": "Unknown Blog",
            "tier": "TIER_4_DISCOVERY_ONLY",
            "source_class": "BLOG",
            "url": "https://example.com/feed.xml",
        }
    ], as_of="2026-09-04T12:00:00Z", user_agent="AI-CIO operator@example.com", get_bytes=lambda *_: b"<rss/>")
    assert result["evidence"] == []
    assert "INVALID_TRUST_CLASS" in result["warnings"][0]


def test_http_source_is_rejected():
    result = collect_official_macro_evidence([
        {
            "source_name": "Official Agency",
            "tier": "TIER_1_PRIMARY_OFFICIAL",
            "source_class": "GOVERNMENT_PRIMARY",
            "url": "http://agency.gov/feed.xml",
        }
    ], as_of="2026-09-04T12:00:00Z", user_agent="AI-CIO operator@example.com", get_bytes=lambda *_: b"<rss/>")
    assert result["evidence"] == []
    assert "HTTPS_REQUIRED" in result["warnings"][0]


def test_old_items_are_filtered():
    rss = b"<rss><channel><item><title>Old release</title><pubDate>Mon, 10 Aug 2026 12:00:00 GMT</pubDate></item></channel></rss>"
    result = collect_official_macro_evidence([
        {
            "source_name": "Official Agency",
            "tier": "TIER_1_PRIMARY_OFFICIAL",
            "source_class": "GOVERNMENT_PRIMARY",
            "url": "https://agency.gov/feed.xml",
        }
    ], as_of="2026-09-04T12:00:00Z", user_agent="AI-CIO operator@example.com", get_bytes=lambda *_: rss)
    assert result["evidence_count"] == 0
