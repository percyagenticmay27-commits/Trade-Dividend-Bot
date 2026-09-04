from pathlib import Path

from enterprise_discovery_source_trust import evaluate_source_candidate, load_source_trust_profile


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "configs" / "enterprise_discovery_source_trust_profile.json"


def test_profile_is_fail_closed_and_never_auto_activates():
    profile = load_source_trust_profile(PROFILE)
    assert profile["continuous_source_discovery"] is True
    assert profile["auto_activate_new_sources"] is False
    assert profile["admission_requirements"]["new_sources_require_review_before_activation"] is True


def test_valid_official_source_is_review_required_not_auto_active():
    profile = load_source_trust_profile(PROFILE)
    decision = evaluate_source_candidate({
        "name": "Example Government Agency",
        "publisher": "Example Government Agency",
        "tier": "TIER_1_PRIMARY_OFFICIAL",
        "url": "https://agency.gov/feed.xml",
        "provenance": "official agency RSS",
        "source_class": "PRIMARY_GOVERNMENT",
        "published_timestamp_supported": True,
    }, profile)
    assert decision["status"] == "REVIEW_REQUIRED"
    assert decision["eligible_for_activation_review"] is True
    assert decision["auto_activate"] is False


def test_insecure_or_anonymous_source_is_rejected():
    profile = load_source_trust_profile(PROFILE)
    decision = evaluate_source_candidate({
        "name": "Rumor Feed",
        "tier": "TIER_4_DISCOVERY_ONLY",
        "url": "http://example.invalid/feed",
        "provenance": "unknown",
        "source_class": "SOCIAL",
        "published_timestamp_supported": True,
        "anonymous_social": True,
    }, profile)
    assert decision["status"] == "REJECTED"
    assert "HTTPS_REQUIRED" in decision["reasons"]
    assert "ANONYMOUS_SOCIAL_REJECTED" in decision["reasons"]


def test_repost_only_aggregator_is_rejected():
    profile = load_source_trust_profile(PROFILE)
    decision = evaluate_source_candidate({
        "name": "Aggregator",
        "publisher": "Aggregator",
        "tier": "TIER_2_PROFESSIONAL_NEWS",
        "url": "https://aggregator.example/feed",
        "provenance": "reposted headlines",
        "source_class": "PROFESSIONAL_MEDIA",
        "published_timestamp_supported": True,
        "repost_only": True,
    }, profile)
    assert decision["status"] == "REJECTED"
    assert "REPOST_ONLY_REJECTED" in decision["reasons"]


def test_profile_contains_vetted_official_expansion_queue():
    profile = load_source_trust_profile(PROFILE)
    names = {row["name"] for row in profile["trusted_expansion_queue"]}
    assert "Federal Reserve Board" in names
    assert "U.S. Bureau of Labor Statistics" in names
    assert "U.S. Energy Information Administration" in names
    assert "Federal Trade Commission" in names
    assert "U.S. Department of Justice Antitrust Division" in names
