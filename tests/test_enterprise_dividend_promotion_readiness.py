import json

from src.dividend_bot.enterprise_dividend_promotion_readiness import (
    build_dividend_promotion_readiness,
    enrich_dividend_watchlist_row,
)


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fixtures(tmp_path):
    _write(
        tmp_path / "results/enterprise_dividend_discovery_bucket.json",
        {
            "candidates": [
                {
                    "underlying_symbol": "NVDA",
                    "independent_source_count": 3,
                    "source_confluence": {
                        "independent_source_count": 3,
                        "source_class_count": 2,
                        "source_classes": ["CREATOR_INTELLIGENCE", "PRIMARY_COMPANY"],
                    },
                    "financial_health": {
                        "components": {
                            "analyst_revisions": 50.0,
                            "debt_health": 94.34,
                            "eps_growth": 100.0,
                            "gross_margin_trend": 49.37,
                            "operating_cash_flow": 100.0,
                            "revenue_growth": 100.0,
                            "sector_strength": 53.84,
                        },
                        "evidence_timestamp": "2026-09-04T16:35:35Z",
                        "provenance": "YAHOO_FINANCE",
                    },
                    "theme_strength": {
                        "score": 55.24,
                        "components": {
                            "catalyst_support": 50.0,
                            "evidence_breadth": 50.0,
                            "market_confirmation": 57.87,
                            "sector_confirmation": 53.84,
                            "source_class_diversity": 66.67,
                        },
                        "evidence_timestamp": "2026-09-04T17:37:51Z",
                        "provenance": "AI_CIO_ENTERPRISE_DISCOVERY",
                    },
                }
            ]
        },
    )
    _write(
        tmp_path / "results/enterprise_dividend_suitability.json",
        {
            "candidates": [
                {
                    "underlying_symbol": "NVDA",
                    "suitability_status": "EVIDENCE_REQUIRED",
                    "suitability_score": None,
                    "decision_reasons": ["No separately reviewed suitability evidence is available."],
                    "evidence_as_of": None,
                }
            ]
        },
    )
    _write(
        tmp_path / "results/enterprise_dividend_income_mapping.json",
        {
            "candidates": [
                {
                    "underlying_symbol": "NVDA",
                    "mapping_status": "RESEARCH_REQUIRED",
                }
            ]
        },
    )


def _nvda_watchlist_item():
    return {
        "symbol": "NVDA",
        "entry_confidence": 1.0,
        "entry_confidence_level": "HIGH",
        "entry_evidence_generated_at_utc": "2026-09-04T20:30:38Z",
        "entry_evidence_source": "entry_score_report.json",
        "entry_reasons": ["STRATEGY_ENTRY_TRIGGER_ACTIVE"],
        "entry_score": 100.0,
        "entry_status": "STRONG_ENTRY",
        "timing_context": "TREND_CONTINUATION",
        "valuation_score": 43.75,
    }


def test_nvda_authoritative_values_are_assembled_without_inventing_missing_gates(tmp_path):
    _fixtures(tmp_path)
    readiness = build_dividend_promotion_readiness(_nvda_watchlist_item(), tmp_path)

    assert readiness["financial_health"]["status"] == "PASS"
    assert readiness["financial_health"]["value"] == 78.22
    assert readiness["financial_health"]["threshold"] == 70.0
    assert readiness["financial_health"]["as_of"] == "2026-09-04T16:35:35Z"

    assert readiness["dividend_suitability"]["status"] == "PENDING"
    assert readiness["dividend_suitability"]["suitability_status"] == "EVIDENCE_REQUIRED"
    assert readiness["dividend_suitability"]["mapping_status"] == "RESEARCH_REQUIRED"
    assert "No separately reviewed suitability evidence" in readiness["dividend_suitability"]["reason"]

    assert readiness["valuation"]["status"] == "PENDING"
    assert readiness["valuation"]["value"] == 43.75

    assert readiness["opportunity_thesis"]["status"] == "PENDING"
    assert readiness["opportunity_thesis"]["value"] == 55.24

    assert readiness["entry"]["status"] == "PASS"
    assert readiness["entry"]["value"] == 100.0
    assert "Status: STRONG_ENTRY" in readiness["entry"]["reason"]
    assert "Confidence: HIGH" in readiness["entry"]["reason"]
    assert "Timing: TREND_CONTINUATION" in readiness["entry"]["reason"]
    assert readiness["entry"]["evidence_source"] == "entry_score_report.json"
    assert readiness["entry"]["as_of"] == "2026-09-04T20:30:38Z"

    assert readiness["dividend_safety"]["status"] == "PENDING"
    assert readiness["promotion_ready"] is False


def test_financial_health_fails_closed_when_incomplete(tmp_path):
    _write(
        tmp_path / "results/enterprise_dividend_discovery_bucket.json",
        {"candidates": [{"underlying_symbol": "NVDA", "financial_health": {"components": {"revenue_growth": 100}}}]},
    )
    readiness = build_dividend_promotion_readiness(_nvda_watchlist_item(), tmp_path)
    assert readiness["financial_health"]["status"] == "FAIL"
    assert readiness["financial_health"]["value"] == 100.0


def test_enrichment_preserves_original_watchlist_values(tmp_path):
    _fixtures(tmp_path)
    row = {
        "strategy_id": "DIVIDEND-001",
        "watchlist": [
            {
                **_nvda_watchlist_item(),
                "name": "NVIDIA Corporation",
                "rank": 1,
                "status": "READY",
                "market_data_stale": False,
            }
        ],
    }
    enriched = enrich_dividend_watchlist_row(row, tmp_path)

    original = row["watchlist"][0]
    result = enriched["watchlist"][0]
    for key in (
        "symbol",
        "name",
        "rank",
        "status",
        "entry_status",
        "entry_score",
        "entry_confidence",
        "entry_confidence_level",
        "timing_context",
        "valuation_score",
        "market_data_stale",
    ):
        assert result[key] == original[key]
    assert "promotion_readiness" not in original
    assert result["promotion_readiness"]["financial_health"]["value"] == 78.22


def test_no_external_files_means_pending_not_fabricated(tmp_path):
    readiness = build_dividend_promotion_readiness({"symbol": "XYZ"}, tmp_path)
    assert readiness["trusted_sources"]["status"] == "PENDING"
    assert readiness["financial_health"]["status"] == "PENDING"
    assert readiness["dividend_suitability"]["status"] == "PENDING"
    assert readiness["dividend_safety"]["status"] == "PENDING"
    assert readiness["valuation"]["status"] == "PENDING"
    assert readiness["opportunity_thesis"]["status"] == "PENDING"
    assert readiness["entry"]["status"] == "PENDING"
    assert readiness["promotion_ready"] is False
