from src.dividend_bot.enterprise_portal_strategy_ui import render_strategy_workspace, strategy_ui_css


def _report():
    return {
        "strategy_kpis": [
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Income Strategy",
                "allocated_capital": 5000.0,
                "health_status": "HEALTHY",
                "evidence_status": "AVAILABLE",
                "watchlist_count": 1,
                "watchlist": [
                    {
                        "symbol": "TEST",
                        "status": "WATCH",
                        "market_data_stale": False,
                        "currently_held": False,
                        "sources": ["candidate_discovery.json"],
                    }
                ],
            }
        ]
    }


def test_workspace_uses_professional_watchlist_renderer():
    output = render_strategy_workspace(_report(), audience="investor")
    assert "watchlist-pro" in output
    assert "watchlist-table" in output
    assert "1 candidates" in output
    assert "candidate_discovery.json" in output


def test_workspace_zero_watchlist_is_valid_empty_state():
    report = _report()
    report["strategy_kpis"][0]["watchlist_count"] = 0
    report["strategy_kpis"][0]["watchlist"] = []
    output = render_strategy_workspace(report, audience="executive")
    assert "No active strategy watchlist candidates." in output
    assert "0 candidates" in output


def test_strategy_css_includes_watchlist_styles():
    css = strategy_ui_css()
    assert ".watchlist-table" in css
    assert ".watchlist-summary-grid" in css
