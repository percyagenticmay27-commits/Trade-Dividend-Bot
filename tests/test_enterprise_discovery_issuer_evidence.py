from enterprise_discovery_issuer_evidence import collect_issuer_primary_evidence, attach_issuer_primary_evidence


def _profile(symbol="NVDA"):
    return {
        "symbol": symbol,
        "issuer_name": "Example Issuer",
        "tier": "TIER_1_PRIMARY_OFFICIAL",
        "status": "VERIFIED_ACTIVE",
        "verified_domains": ["investor.example.com"],
        "research_pages": [{"role": "investor_relations", "url": "https://investor.example.com/"}],
        "scoring_eligible": False,
    }


def _get(url, user_agent):
    return b"<html><head><title>Official Investor Relations</title></head><body>facts</body></html>"


def test_collects_only_active_symbol_as_non_scoring_primary_evidence():
    result = collect_issuer_primary_evidence(
        [_profile("NVDA"), _profile("NFLX")],
        active_symbols={"NVDA"},
        as_of="2026-09-04T20:00:00Z",
        user_agent="AI-CIO test@example.com",
        get_bytes=_get,
    )
    assert result["evidence_count"] == 1
    row = result["evidence"][0]
    assert row["underlying_symbol"] == "NVDA"
    assert row["source_class"] == "PRIMARY_COMPANY"
    assert row["symbol_linkage"] == "VERIFIED_PROFILE"
    assert row["review_required"] is True
    assert row["scoring_eligible"] is False
    assert row["catalyst_inference_used"] is False
    assert row["catalyst_events"] == []
    assert result["scoring_event_count"] == 0


def test_unverified_page_domain_is_rejected():
    profile = _profile()
    profile["research_pages"] = [{"role": "news", "url": "https://evil.example/news"}]
    result = collect_issuer_primary_evidence(
        [profile], active_symbols={"NVDA"}, as_of="2026-09-04T20:00:00Z",
        user_agent="AI-CIO test@example.com", get_bytes=_get,
    )
    assert result["evidence"] == []
    assert any("UNVERIFIED_URL" in warning for warning in result["warnings"])


def test_scoring_profile_is_rejected():
    profile = _profile()
    profile["scoring_eligible"] = True
    result = collect_issuer_primary_evidence(
        [profile], active_symbols={"NVDA"}, as_of="2026-09-04T20:00:00Z",
        user_agent="AI-CIO test@example.com", get_bytes=_get,
    )
    assert result["evidence_count"] == 0
    assert any("SCORING_PROFILE_FORBIDDEN" in warning for warning in result["warnings"])


def test_fetch_failure_fails_closed_without_evidence():
    def failing_get(url, user_agent):
        raise OSError("offline")
    result = collect_issuer_primary_evidence(
        [_profile()], active_symbols={"NVDA"}, as_of="2026-09-04T20:00:00Z",
        user_agent="AI-CIO test@example.com", get_bytes=failing_get,
    )
    assert result["evidence_count"] == 0
    assert result["scoring_event_count"] == 0
    assert any(warning.startswith("ISSUER_PAGE_FAILED:NVDA") for warning in result["warnings"])


def test_attachment_does_not_change_symbol_observations():
    report = {"observations": [{"underlying_symbol": "NVDA", "nomination_eligible": False}]}
    issuer = collect_issuer_primary_evidence(
        [_profile()], active_symbols={"NVDA"}, as_of="2026-09-04T20:00:00Z",
        user_agent="AI-CIO test@example.com", get_bytes=_get,
    )
    result = attach_issuer_primary_evidence(report, issuer)
    assert result["observations"] == report["observations"]
    assert result["issuer_primary_evidence"]["scoring_event_count"] == 0
