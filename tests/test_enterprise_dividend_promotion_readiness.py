import json
from datetime import datetime, timezone

from src.dividend_bot.enterprise_dividend_promotion_readiness import (
    build_dividend_promotion_readiness,
    enrich_dividend_watchlist_row,
)

NOW = datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)


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
                    "source_evidence": [
                        {"producer": "Issuer", "mentioned_on": "2026-09-04"},
                        {"producer": "SEC", "mentioned_on": "2026-09-04"},
                        {"producer": "Research", "mentioned_on": "2026-09-04"},
                    ],
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
                        "score": 52.99,
                        "components": {
                            "catalyst_support": 35.0,
                            "evidence_breadth": 50.0,
                            "market_confirmation": 57.87,
                            "sector_confirmation": 53.84,
                            "source_class_diversity": 66.67,
                        },
                        "evidence_timestamp": "2026-09-04T18:06:09Z",
                        "provenance": "AI_CIO_ENTERPRISE_DISCOVERY",
                    },
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


def test_only_four_watchlist_promotion_gates_are_assembled(tmp_path):
    _fixtures(tmp_path)
    readiness = build_dividend_promotion_readiness(_nvda_watchlist_item(), tmp_path, now=NOW)

    assert readiness["policy"] == "DIVIDEND_PRETRADE_FOUR_REFRESHABLE_GATES_FAIL_CLOSED"
    assert readiness["financial_health"]["status"] == "PASS"
    assert readiness["financial_health"]["value"] == 78.22
    assert readiness["financial_health"]["freshness_status"] == "FRESH"
    assert readiness["opportunity_thesis"]["value"] == 52.99
    assert readiness["entry"]["status"] == "PASS"
    assert readiness["entry"]["value"] == 100.0
    assert readiness["entry"]["freshness_status"] == "FRESH"

    # Income qualification belongs to the Dividend Gateway, not Watchlist readiness.
    assert "dividend_suitability" not in readiness
    assert "dividend_safety" not in readiness
    assert "valuation" not in readiness


def test_stale_previous_pass_is_not_reused(tmp_path):
    _fixtures(tmp_path)
    stale_now = datetime(2026, 9, 20, 0, 0, tzinfo=timezone.utc)
    readiness = build_dividend_promotion_readiness(_nvda_watchlist_item(), tmp_path, now=stale_now)

    assert readiness["financial_health"]["status"] == "PENDING"
    assert readiness["financial_health"]["freshness_status"] == "STALE_OR_UNAVAILABLE"
    assert "stale" in readiness["financial_health"]["reason"].lower()
    assert readiness["entry"]["status"] == "PENDING"
    assert readiness["entry"]["freshness_status"] == "STALE_OR_UNAVAILABLE"
    assert readiness["promotion_ready"] is False


def test_missing_timestamp_fails_closed_even_with_good_values(tmp_path):
    _write(
        tmp_path / "results/enterprise_dividend_discovery_bucket.json",
        {
            "candidates": [{
                "underlying_symbol": "NVDA",
                "financial_health": {"components": {
                    "revenue_growth": 100,
                    "eps_growth": 100,
                    "operating_cash_flow": 100,
                    "gross_margin_trend": 100,
                    "debt_health": 100,
                    "analyst_revisions": 100,
                    "sector_strength": 100,
                }},
            }]
        },
    )
    readiness = build_dividend_promotion_readiness(_nvda_watchlist_item(), tmp_path, now=NOW)
    assert readiness["financial_health"]["value"] == 100.0
    assert readiness["financial_health"]["status"] == "PENDING"
    assert "timestamp" in readiness["financial_health"]["reason"].lower()


def test_enrichment_preserves_original_watchlist_values(tmp_path):
    _fixtures(tmp_path)
    row = {"strategy_id": "DIVIDEND-001", "watchlist": [{**_nvda_watchlist_item(), "name": "NVIDIA Corporation", "rank": 1}]}
    enriched = enrich_dividend_watchlist_row(row, tmp_path, now=NOW)
    assert enriched["watchlist"][0]["symbol"] == "NVDA"
    assert enriched["watchlist"][0]["valuation_score"] == 43.75
    assert "promotion_readiness" not in row["watchlist"][0]
    assert enriched["watchlist"][0]["promotion_readiness"]["financial_health"]["value"] == 78.22


def test_no_external_files_means_all_four_pending(tmp_path):
    readiness = build_dividend_promotion_readiness({"symbol": "XYZ"}, tmp_path, now=NOW)
    assert readiness["trusted_sources"]["status"] == "PENDING"
    assert readiness["financial_health"]["status"] == "PENDING"
    assert readiness["opportunity_thesis"]["status"] == "PENDING"
    assert readiness["entry"]["status"] == "PENDING"
    assert readiness["promotion_ready"] is False
