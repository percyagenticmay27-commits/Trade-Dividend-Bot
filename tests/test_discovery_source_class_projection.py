from copy import deepcopy

from src.dividend_bot.discovery_source_class_projection import (
    canonical_source_class,
    propagate_source_classes_to_swing_bucket,
)


def _bucket():
    return {
        "schema_version": "1.0",
        "strategy_id": "SWING-001",
        "candidates": [
            {
                "underlying_symbol": "AMAT",
                "discovery_status": "EMERGING",
                "discovery_leadership_score": 67.692308,
                "discovery_leadership_classification": "STRONG",
                "relative_leadership": {"leadership_persistence": 0.75},
                "evidence_sources": [
                    {"source": "24/7 Wall St.", "mentioned_on": "2026-08-20"},
                    {"source": "TIKR.com", "mentioned_on": "2026-08-20"},
                ],
            },
            {
                "underlying_symbol": "SJM",
                "discovery_status": "EMERGING",
                "discovery_leadership_score": 58.846154,
                "evidence_sources": [{"source": "AD HOC NEWS", "mentioned_on": "2026-08-20"}],
            },
            {
                "underlying_symbol": "ULTA",
                "discovery_status": "EMERGING",
                "discovery_leadership_score": 32.307692,
                "evidence_sources": [{"source": "Simply Wall Street", "mentioned_on": "2026-08-20"}],
            },
            {
                "underlying_symbol": "INTS",
                "discovery_status": "EMERGING",
                "discovery_leadership_score": 21.923077,
                "evidence_sources": [{"source": "GuruFocus", "mentioned_on": "2026-08-20"}],
            },
        ],
    }


def _report():
    def evidence(source, source_class="PROFESSIONAL_MEDIA"):
        return {
            "source": source,
            "source_class": source_class,
            "producer": source,
            "mentioned_on": "2026-08-20",
        }

    return {
        "candidates": [
            {"underlying_symbol": "AMAT", "source_evidence": [evidence("24/7 Wall St."), evidence("TIKR.com")]},
            {"underlying_symbol": "SJM", "source_evidence": [evidence("AD HOC NEWS")]},
            {"underlying_symbol": "ULTA", "source_evidence": [evidence("Simply Wall Street")]},
            {"underlying_symbol": "INTS", "source_evidence": [evidence("GuruFocus")]},
        ]
    }


def test_shared_vocabulary_and_legacy_authority_mapping():
    assert canonical_source_class({"source_class": "PROFESSIONAL_MEDIA"}) == "INSTITUTIONAL_NEWS"
    assert canonical_source_class({"source_class": "CREATOR_INTELLIGENCE"}) == "PROFESSIONAL_CREATOR"
    assert canonical_source_class({"source_class": "MARKET_ANALYTICS"}) == "MARKET_ANALYTICS"
    assert canonical_source_class({"source_class": "UNCLASSIFIED"}) is None


def test_regulatory_and_company_primary_legacy_provenance_are_resolved_inside_ai_cio():
    assert canonical_source_class({
        "source": "SEC EDGAR Daily Index",
        "producer": "U.S. Securities and Exchange Commission",
        "source_class": "PRIMARY_COMPANY",
    }) == "PRIMARY_REGULATORY"
    assert canonical_source_class({
        "source": "Company IR",
        "producer": "Example Corp",
        "source_class": "PRIMARY_COMPANY",
    }) == "COMPANY_PRIMARY"


def test_current_five_publishers_receive_authoritative_institutional_news_class():
    result = propagate_source_classes_to_swing_bucket(_bucket(), _report())
    assigned = {
        evidence["source"]: evidence["source_class"]
        for candidate in result["candidates"]
        for evidence in candidate["evidence_sources"]
    }
    assert assigned == {
        "24/7 Wall St.": "INSTITUTIONAL_NEWS",
        "TIKR.com": "INSTITUTIONAL_NEWS",
        "AD HOC NEWS": "INSTITUTIONAL_NEWS",
        "Simply Wall Street": "INSTITUTIONAL_NEWS",
        "GuruFocus": "INSTITUTIONAL_NEWS",
    }


def test_unclassified_evidence_remains_null_without_breaking_bucket():
    bucket = _bucket()
    bucket["candidates"][0]["evidence_sources"].append({
        "source": "Legacy Unknown",
        "mentioned_on": "2026-08-20",
    })
    report = _report()
    report["candidates"][0]["source_evidence"].append({
        "source": "Legacy Unknown",
        "source_class": "UNCLASSIFIED",
        "mentioned_on": "2026-08-20",
    })
    result = propagate_source_classes_to_swing_bucket(bucket, report)
    unknown = next(
        evidence
        for evidence in result["candidates"][0]["evidence_sources"]
        if evidence["source"] == "Legacy Unknown"
    )
    assert unknown["source_class"] is None
    assert result["schema_version"] == "1.0"
    assert result["strategy_id"] == "SWING-001"


def test_source_class_propagation_does_not_change_discovery_leadership_values():
    bucket = _bucket()
    before = deepcopy(bucket)
    result = propagate_source_classes_to_swing_bucket(bucket, _report())
    assert result["schema_version"] == "1.0"
    assert result["strategy_id"] == "SWING-001"
    for old, new in zip(before["candidates"], result["candidates"], strict=True):
        assert new.get("discovery_leadership_score") == old.get("discovery_leadership_score")
        assert new.get("discovery_leadership_classification") == old.get("discovery_leadership_classification")
        assert new.get("relative_leadership") == old.get("relative_leadership")
