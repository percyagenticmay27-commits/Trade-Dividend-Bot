from src.dividend_bot.enterprise_watchlist_ui import render_watchlist_panel, watchlist_ui_css


def _row():
    return {
        "strategy_id": "DIVIDEND-001",
        "watchlist_count": 2,
        "watchlist": [
            {
                "symbol": "AAA",
                "name": "Alpha Income ETF",
                "rank": 1,
                "status": "WATCH",
                "opportunity_quality": 82.5,
                "conviction_score": 77,
                "momentum_score": 71,
                "daily_change_percent": 1.25,
                "market_data_stale": False,
                "currently_held": False,
                "sources": ["candidate_discovery.json"],
            },
            {
                "symbol": "BBB",
                "rank": 2,
                "status": "READY_FOR_SCORING",
                "market_data_stale": True,
                "currently_held": True,
                "sources": ["TEST"],
            },
        ],
    }


def test_watchlist_renderer_uses_professional_summary_and_table():
    page = render_watchlist_panel(_row())
    assert "2 candidates" in page
    assert "Total Watchlist" in page
    assert "Ready / Promoted" in page
    assert "Currently Held" in page
    assert "Stale Market Data" in page
    assert "Alpha Income ETF" in page
    assert "Opportunity" in page
    assert "Conviction" in page
    assert "Momentum" in page
    assert "Daily Change" in page
    assert "Market Data" in page


def test_watchlist_renderer_does_not_fabricate_missing_scores():
    page = render_watchlist_panel(_row())
    assert "watchlist-not-reported'>Not reported" in page
    assert "82.5" in page
    assert "77.0" in page
    assert "71.0" in page


def test_watchlist_renderer_preserves_market_freshness_and_status():
    page = render_watchlist_panel(_row())
    assert "WATCH" in page
    assert "READY_FOR_SCORING" in page
    assert "FRESH" in page
    assert "STALE" in page


def test_watchlist_renderer_has_explicit_zero_candidate_state():
    page = render_watchlist_panel({"strategy_id": "DIVIDEND-001", "watchlist_count": 0, "watchlist": []})
    assert "0 candidates" in page
    assert "No active strategy watchlist candidates." in page
    assert "explicitly marks them for watchlist monitoring" in page


def test_watchlist_renderer_escapes_strategy_owned_text():
    row = _row()
    row["watchlist"][0]["name"] = "<script>alert(1)</script>"
    row["watchlist"][0]["sources"] = ["<b>bad</b>"]
    page = render_watchlist_panel(row)
    assert "<script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<b>bad</b>" not in page


def test_watchlist_css_is_self_contained_and_responsive():
    css = watchlist_ui_css()
    assert css.lstrip().startswith("<style>")
    assert css.rstrip().endswith("</style>")
    assert ".watchlist-table" in css
    assert ".watchlist-summary-grid" in css
    assert ".watchlist-status-ready" in css
    assert "@media(max-width:520px)" in css
