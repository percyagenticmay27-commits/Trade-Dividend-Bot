from enterprise_discovery_issuer_research import (
    attach_issuer_research_registry,
    build_issuer_research_registry,
    validate_issuer_profile,
)


def _profile():
    return {
        "symbol": "NVDA",
        "issuer_name": "NVIDIA Corporation",
        "tier": "TIER_1_PRIMARY_OFFICIAL",
        "status": "VERIFIED_ACTIVE",
        "verified_domains": ["investor.nvidia.com"],
        "research_pages": [{"role": "investor_relations", "url": "https://investor.nvidia.com/"}],
        "allowed_evidence_roles": ["earnings", "guidance"],
        "scoring_eligible": False,
    }


def test_verified_official_profile_is_accepted():
    valid, errors = validate_issuer_profile(_profile())
    assert valid is True
    assert errors == []


def test_unverified_domain_fails_closed():
    profile = _profile()
    profile["research_pages"] = [{"role": "news", "url": "https://example.com/nvda"}]
    valid, errors = validate_issuer_profile(profile)
    assert valid is False
    assert "UNVERIFIED_DOMAIN:example.com" in errors


def test_http_source_fails_closed():
    profile = _profile()
    profile["research_pages"] = [{"role": "news", "url": "http://investor.nvidia.com/news"}]
    valid, errors = validate_issuer_profile(profile)
    assert valid is False
    assert any(error.startswith("HTTPS_REQUIRED:") for error in errors)


def test_profile_cannot_be_scoring_eligible():
    profile = _profile()
    profile["scoring_eligible"] = True
    valid, errors = validate_issuer_profile(profile)
    assert valid is False
    assert "ISSUER_PROFILE_MUST_BE_NONSCORING" in errors


def test_registry_is_symbol_keyed_and_non_scoring():
    registry = build_issuer_research_registry([_profile()])
    assert registry["profile_count"] == 1
    assert registry["profiles"]["NVDA"]["issuer_name"] == "NVIDIA Corporation"
    assert registry["scoring_event_count"] == 0


def test_registry_attachment_does_not_change_observations():
    report = {"observations": [{"underlying_symbol": "NVDA", "nomination_eligible": False}]}
    registry = build_issuer_research_registry([_profile()])
    result = attach_issuer_research_registry(report, registry)
    assert result["observations"] == report["observations"]
    assert result["issuer_research_registry"]["scoring_event_count"] == 0
