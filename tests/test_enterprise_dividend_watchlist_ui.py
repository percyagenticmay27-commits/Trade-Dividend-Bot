from src.dividend_bot.enterprise_dividend_watchlist_ui import render_dividend_watchlist_panel
from src.dividend_bot.enterprise_portal_strategy_ui_v2 import render_strategy_workspace


def _dividend_row():
    return {
        "strategy_id": "DIVIDEND-001",
        "display_name": "Dividend Income Strategy",
        "watchlist_count": 1,
        "watchlist": [
            {
                "symbol": "DG",
                "name": "Dollar General",
                "watchlist_rank": 1,
                "status": "WATCHLIST",
                "entry_status": "WATCH",
                "entry_score": 54,
                "entry_confidence": 63.5,
                "entry_confidence_level": "MEDIUM",
                "timing_context": "WAIT_FOR_PULLBACK",
                "requirements_for_buy": ["PRICE_CONFIRMATION"],
                "market_data_stale": False,
                "currently_held": False,
                "evidence_source": "results/dividend_entry_score.json",
                "entry_evidence_generated_at_utc": "2026-09-04T12:00:00Z",
                "trusted_sources": {"status": "PASS", "value": 6, "threshold": 5},
                "financial_health": {"status": "PASS", "value": 76.2, "threshold": 70},
                "opportunity_thesis": {"status": "PASS"},
                "promotion_readiness": {
                    "entry": {"status": "FAIL", "value": 54, "threshold": 70},
                    "promotion_ready": False,
                    "blocking_reasons": ["ENTRY_READINESS"],
                },
            }
        ],
    }


def test_dividend_watchlist_preserves_original_columns_and_values():
    output = render_dividend_watchlist_panel(_dividend_row())

    for heading in (
        "Rank",
        "Candidate",
        "Entry Status",
        "Entry Score",
        "Confidence",
        "Timing",
        "Why It Has Not Progressed",
        "What Happens Next",
        "Market Data",
        "Held",
        "Evidence As-Of",
    ):
        assert f">{heading}<" in output

    assert "DG" in output
    assert "Dollar General" in output
    assert ">WATCH<" in output
    assert ">54.0<" in output
    assert "63.5 (Medium)" in output
    assert "Wait For Pullback" in output
    assert "Waiting for Price confirmation." in output
    assert "Re-evaluate after the listed requirements are satisfied." in output
    assert ">FRESH<" in output
    assert ">NO<" in output
    assert "results/dividend_entry_score.json" in output
    assert "2026-09-04T12:00:00Z" in output


def test_dividend_watchlist_collapsible_record_matches_swing_promotion_spec():
    output = render_dividend_watchlist_panel(_dividend_row())

    assert "dividend-watch-detail-toggle" in output
    assert "dividend-watch-detail-1" in output
    assert "colspan='11'" in output
    assert "Promotion Readiness — DG" in output
    assert "Four-gate Promotion Readiness" in output

    assert "watchlist-promotion-panel dividend-promotion-spec" in output
    assert "watchlist-promotion-panel-heading" in output
    assert "watchlist-promotion-section-title" in output
    assert "watchlist-promotion-gates-wrap" in output
    assert "watchlist-promotion-gates" in output
    assert output.count("watchlist-promotion-gate-card") == 4
    assert "watchlist-promotion-gate-header" in output
    assert "watchlist-promotion-gate-content" in output
    assert "watchlist-promotion-blockers" in output

    assert "Trusted Sources / Evidence" in output
    assert "Financial Health" in output
    assert "Theme / Opportunity Evidence" in output
    assert "Entry Readiness" in output
    assert "Dividend / Income Suitability" not in output
    assert "Dividend Safety / Sustainability" not in output
    assert "Valuation / Price Suitability" not in output
    assert "ENTRY_READINESS" in output

    assert "<th>Promotion</th>" not in output
    assert "<th>Status</th>" not in output


def test_missing_dividend_gate_evidence_is_pending_not_pass():
    row = _dividend_row()
    row["watchlist"][0].pop("opportunity_thesis")
    output = render_dividend_watchlist_panel(row)

    theme_start = output.index("Theme / Opportunity Evidence")
    theme_slice = output[theme_start:theme_start + 500]
    assert "PENDING" in theme_slice
    assert "Authoritative gate evidence is unavailable" in theme_slice


def test_dividend_workspace_keeps_original_watchlist_and_adds_collapsible_detail():
    row = _dividend_row()
    row.update({
        "strategy_type": "DIVIDEND",
        "lifecycle_status": "PRODUCTION",
        "runtime_status": "ONLINE",
        "health_status": "HEALTHY",
        "readiness": "READY",
        "allocated_capital": 5000,
        "portfolio_value": 5000,
        "capability_count": 1,
        "capabilities": ["watchlist"],
        "published_artifact_count": 0,
        "published_artifacts": [],
        "evidence_status": "AVAILABLE",
    })
    output = render_strategy_workspace({"strategy_kpis": [row]}, audience="executive")

    assert "Strategy-owned candidates being monitored before promotion or allocation." in output
    assert "Total Watchlist" in output
    assert "Ready / Promoted" in output
    assert "Currently Held" in output
    assert "Stale Market Data" in output
    assert "Why It Has Not Progressed" in output
    assert "What Happens Next" in output
    assert "Promotion Readiness — DG" in output
    assert "Four-gate Promotion Readiness" in output
    assert "without changing the original Watchlist columns or published values" in output
