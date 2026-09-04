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
                "watchlist_rank": 1,
                "status": "WATCHLIST",
                "trusted_sources": {"status": "PASS", "value": 6, "threshold": 5},
                "financial_health": {"status": "PASS", "value": 76.2, "threshold": 70},
                "dividend_suitability": {"status": "PASS", "reason": "Income mandate satisfied"},
                "dividend_safety": {"status": "PASS", "reason": "Payout evidence accepted"},
                "valuation": {"status": "PENDING", "reason": "Await current valuation evidence"},
                "opportunity_thesis": {"status": "PASS"},
                "promotion_readiness": {
                    "entry": {"status": "FAIL", "value": 54, "threshold": 70},
                    "promotion_ready": False,
                    "blocking_reasons": ["ENTRY_READINESS"],
                },
            }
        ],
    }


def test_dividend_watchlist_renders_collapsible_symbol_record():
    output = render_dividend_watchlist_panel(_dividend_row())

    assert "Dividend Watchlist" in output
    assert ">DG<" in output
    assert "dividend-watch-toggle" in output
    assert "dividend-watch-detail-1" in output
    assert "Dividend Promotion Readiness — DG" in output
    assert "Trusted Sources / Evidence" in output
    assert "Financial Health" in output
    assert "Dividend / Income Suitability" in output
    assert "Dividend Safety / Sustainability" in output
    assert "Valuation / Price Suitability" in output
    assert "Theme / Opportunity Evidence" in output
    assert "Entry Readiness" in output
    assert "ENTRY_READINESS" in output


def test_missing_dividend_gate_evidence_is_pending_not_pass():
    row = _dividend_row()
    row["watchlist"][0].pop("valuation")
    output = render_dividend_watchlist_panel(row)

    valuation_start = output.index("Valuation / Price Suitability")
    valuation_slice = output[valuation_start:valuation_start + 500]
    assert "PENDING" in valuation_slice
    assert "Authoritative evidence has not been published" in valuation_slice


def test_dividend_workspace_replaces_base_watchlist_with_collapsible_panel():
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

    assert "Dividend Promotion Readiness — DG" in output
    assert "Each symbol expands to the Dividend Bot's pre-trade qualification record." in output
    assert "post-entry Win Rate / return / drawdown gates" in output
