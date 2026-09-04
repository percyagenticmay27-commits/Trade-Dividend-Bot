from enterprise_discovery_theme_strength import (
    THEME_STRENGTH_COMPONENTS,
    attach_candidate_theme_strength,
    build_theme_strength_block,
)
from enterprise_weekly_market_discovery import build_swing_projection, build_weekly_discovery
from scripts.collect_enterprise_discovery_sources import _hydrate_retained_theme_context


def _row(**overrides):
    payload = {
        "underlying_symbol": "NVDA",
        "discovery_status": "RISING",
        "themes": ["Semiconductors"],
        "source_evidence": [
            {
                "source": "Reuters",
                "producer": "Reuters",
                "source_class": "PROFESSIONAL_MEDIA",
                "mentioned_on": "2026-09-04",
                "story_id": "nvda-1",
                "earnings_growth_related": True,
                "analyst_upgrade_related": False,
            },
            {
                "source": "SEC EDGAR",
                "producer": "U.S. Securities and Exchange Commission",
                "source_class": "PRIMARY_COMPANY",
                "mentioned_on": "2026-09-03",
                "story_id": "nvda-2",
                "earnings_growth_related": False,
                "analyst_upgrade_related": False,
            },
            {
                "source": "Research Desk",
                "producer": "Research Desk",
                "source_class": "INSTITUTIONAL_RESEARCH",
                "mentioned_on": "2026-09-02",
                "story_id": "nvda-3",
                "earnings_growth_related": False,
                "analyst_upgrade_related": True,
            },
        ],
        "market_evidence": {
            "status": "AVAILABLE",
            "relative_strength_vs_benchmark_percent": 2.0,
            "volume_expansion_ratio": 1.2,
            "latest_session": "2026-09-04",
            "benchmark_symbol": "SPY",
            "is_stale": False,
        },
        "financial_health": {
            "components": {"sector_strength": 70.0},
            "evidence_timestamp": "2026-09-04T16:35:35Z",
        },
    }
    payload.update(overrides)
    return payload


def test_complete_theme_strength_block_has_all_components_and_provenance():
    block = build_theme_strength_block(_row(), generated_at="2026-09-04T16:40:00Z")
    assert block is not None
    assert set(block["components"]) == set(THEME_STRENGTH_COMPONENTS)
    assert all(0.0 <= value <= 100.0 for value in block["components"].values())
    assert 0.0 <= block["score"] <= 100.0
    assert block["evidence_timestamp"] == "2026-09-04T16:40:00Z"
    assert "AI_CIO_ENTERPRISE_DISCOVERY" in block["provenance"]


def test_theme_strength_fails_closed_when_market_evidence_is_partial():
    row = _row()
    row["market_evidence"]["status"] = "PARTIAL"
    assert build_theme_strength_block(row, generated_at="2026-09-04T16:40:00Z") is None


def test_theme_strength_fails_closed_without_sector_confirmation():
    row = _row()
    row["financial_health"]["components"].pop("sector_strength")
    assert build_theme_strength_block(row, generated_at="2026-09-04T16:40:00Z") is None


def test_attach_adds_block_without_changing_nomination_state():
    row = _row(nomination_eligible=False)
    report = {"observations": [row], "warnings": []}
    result = attach_candidate_theme_strength(report, generated_at="2026-09-04T16:40:00Z")
    assert result["observations"][0]["nomination_eligible"] is False
    assert "theme_strength" in result["observations"][0]
    assert result["theme_strength_policy"] == "ALL_COMPONENTS_REQUIRED_FAIL_CLOSED"


def test_retained_active_theme_is_reused_when_current_research_row_omits_theme():
    report = {
        "observations": [
            {
                "underlying_symbol": "NVDA",
                "nomination_eligible": False,
                "themes": [],
            }
        ]
    }
    active = {
        "NVDA": {
            "underlying_symbol": "NVDA",
            "nomination_eligible": True,
            "themes": ["Semiconductors"],
        }
    }
    result = _hydrate_retained_theme_context(report, active)
    assert result["observations"][0]["themes"] == ["Semiconductors"]
    assert result["observations"][0]["nomination_eligible"] is False


def test_weekly_and_swing_projection_preserve_theme_strength():
    row = _row()
    row["theme_strength"] = build_theme_strength_block(row, generated_at="2026-09-04T16:40:00Z")
    report = build_weekly_discovery([row], generated_at="2026-09-04T16:45:00Z")
    swing = build_swing_projection(report)
    assert swing["candidates"][0]["theme_strength"] == row["theme_strength"]
