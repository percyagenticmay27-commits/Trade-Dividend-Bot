from src.dividend_bot.enterprise_portal_strategy_ui import (
    render_strategy_workspace,
    strategy_ui_css,
)


def _report() -> dict:
    return {
        "strategy_kpis": [
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Income Strategy",
                "allocated_capital": 5000.0,
                "portfolio_value": 468.16,
                "position_count": 2,
                "watchlist_count": 0,
                "opportunity_quality": 60.44,
                "win_rate_percent": 0.0,
                "health_status": "HEALTHY",
                "evidence_status": "AVAILABLE",
                "capability_count": 7,
                "published_artifact_count": 4,
                "holdings": [
                    {
                        "symbol": "AVGW",
                        "name": "Avantis U.S. Large Cap Value ETF",
                        "pair": "AVGW / AVGX",
                        "sleeve": "A",
                        "position_status": "OPEN",
                        "shares": 0.8395752964,
                        "price": 42.919998,
                        "market_value": 36.03,
                        "source": "paper_state.json",
                    },
                    {
                        "symbol": "SGOV",
                        "name": "iShares 0-3 Month Treasury Bond ETF",
                        "pair": "CASH RESERVE",
                        "sleeve": "RESERVE",
                        "position_status": "PARKED",
                        "shares": None,
                        "price": None,
                        "market_value": 432.13,
                        "source": "paper_state.json",
                    },
                ],
            }
        ]
    }


def test_workspace_uses_professional_holdings_renderer() -> None:
    output = render_strategy_workspace(_report(), audience="executive")

    assert "class='holdings-pro'" in output
    assert "class='holdings-table'" in output
    assert "Allocated Capital" in output
    assert "Available / Undeployed Cash" in output
    assert "Capital Reconciliation" in output
    assert "Position Status" in output
    assert "Cost Basis" in output
    assert "Unrealized P&amp;L" in output
    assert "Total Return" in output
    assert "Cash Reserve (SGOV)" in output
    assert "✓ Verified" in output
    assert "AVGW: Pair:" not in output


def test_workspace_keeps_missing_position_analytics_unreported() -> None:
    output = render_strategy_workspace(_report(), audience="executive")

    assert "Unrealized P&amp;L" in output
    assert "Total Return" in output
    assert "Not reported" in output
    assert "+2.00%" not in output


def test_strategy_css_includes_professional_holdings_styles() -> None:
    css = strategy_ui_css()

    assert ".holdings-summary-grid" in css
    assert ".holdings-table-wrap" in css
    assert ".capital-reconciliation" in css
    assert ".holding-status.status-open" in css
    assert "@media(max-width:850px)" in css
