from datetime import date

import pytest

from scripts.review_professional_discovery_feeds import review_feed


RSS = b"""<rss><channel>
<item><title>SMCI stock gains after earnings</title><link>https://media.example/smci</link><pubDate>Sun, 16 Aug 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_professional_feed_review_validates_without_approving_or_configuring():
    result = review_feed(
        "Official Financial News",
        "https://media.example/rss",
        user_agent="AI-CIO operator@example.com",
        get_bytes=lambda *_: RSS,
        today=date(2026, 8, 17),
    )
    assert result["review_status"] == "VALID_WITH_RECENT_ENTRIES"
    assert result["xml_feed_valid"] is True
    assert result["entry_count"] == 1
    assert result["recent_entry_count"] == 1
    assert result["automatically_approved"] is False
    assert result["production_configuration_modified"] is False


def test_professional_feed_review_requires_https_and_operator_identity():
    with pytest.raises(ValueError, match="HTTPS"):
        review_feed(
            "Feed",
            "http://media.example/rss",
            user_agent="AI-CIO operator@example.com",
            get_bytes=lambda *_: RSS,
        )
    with pytest.raises(ValueError, match="USER_AGENT"):
        review_feed(
            "Feed",
            "https://media.example/rss",
            user_agent="",
            get_bytes=lambda *_: RSS,
        )

def test_professional_feed_timeout_becomes_structured_failed_review():
    def timeout(*_):
        raise TimeoutError("read operation timed out")
    result = review_feed(
        "Slow Feed",
        "https://media.example/rss",
        user_agent="AI-CIO operator@example.com",
        get_bytes=timeout,
    )
    assert result["review_status"] == "REQUEST_FAILED"
    assert result["xml_feed_valid"] is False
    assert "TimeoutError" in result["review_error"]
    assert result["automatically_approved"] is False


def test_professional_feed_invalid_xml_becomes_structured_failed_review():
    result = review_feed(
        "HTML Endpoint",
        "https://media.example/rss",
        user_agent="AI-CIO operator@example.com",
        get_bytes=lambda *_: b"<html><broken>",
    )
    assert result["review_status"] == "INVALID_XML"
    assert result["xml_feed_valid"] is False
    assert "ParseError" in result["review_error"]
    assert result["production_configuration_modified"] is False

