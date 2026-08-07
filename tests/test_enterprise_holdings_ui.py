from src.dividend_bot.enterprise_holdings_ui import holdings_ui_css, render_holdings_panel


def _row():
    return {
        "strategy_id": "DIVIDEND-001",
        "allocated_capital": 5000.0,
        "portfolio_value": 468.16,
        "position_count": 3,
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
                "symbol": "AVGX",
                "name": "Avantis International Value ETF",
                "pair": "AVGW / AVGX",
                "sleeve": "B",
                "position_status": "OPEN",
                "shares": 0.2526217178,
                "price": 56.02,
                "market_value": 14.15,
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
                "market_value": 329.78,
                "source": "paper_state.json",
            },
        ],
    }


def test_holdings_renderer_reconciles_allocated_deployed_and_undeployed_capital():
    page = render_holdings_panel(_row())

    assert "Allocated Capital" in page
    assert "$5,000.00" in page
    assert "Deployed Holdings" in page
    assert "$379.96" in page
    assert "Invested Positions" in page
    assert "$50.18" in page
    assert "Cash Reserve (SGOV)" in page
    assert "$329.78" in page
    assert "Available / Undeployed Cash" in page
    assert "$4,620.04" in page
    assert "Capital Reconciliation" in page
    assert "$379.96 deployed holdings + $4,620.04 undeployed cash = $5,000.00" in page


def test_holdings_renderer_uses_professional_extended_table():
    page = render_holdings_panel(_row())

    assert "class='holdings-table'" in page
    assert "Symbol" in page
    assert "Name" in page
    assert "Position Status" in page
    assert "Market Price" in page
    assert "Market Value" in page
    assert "% Allocation" in page
    assert "Cost Basis" in page
    assert "Avg Cost" in page
    assert "Unrealized P&amp;L" in page
    assert "Total Return" in page
    assert "Daily Change" in page
    assert "Yield" in page
    assert "Annual Income" in page
    assert "Next Ex-Date" in page
    assert "Avantis U.S. Large Cap Value ETF" in page
    assert "AVGW" in page
    assert "AVGX" in page
    assert "SGOV" in page
    assert "OPEN" in page
    assert "PARKED" in page
    assert "✓ Verified" in page


def test_holdings_renderer_does_not_fabricate_missing_analytics():
    page = render_holdings_panel(_row())

    assert "Unrealized P&amp;L" in page
    assert "Total Return" in page
    assert "Cost Basis" in page
    assert "Not reported" in page
    assert "+2.00%" not in page
    assert "+$2.89" not in page


def test_holdings_renderer_displays_authoritative_optional_position_analytics():
    row = _row()
    row["holdings"][0].update(
        {
            "cost_basis": 35.41,
            "average_cost": 42.18,
            "unrealized_pnl": 0.62,
            "total_return_percent": 2.10,
            "daily_change_percent": 0.45,
            "dividend_yield_percent": 4.25,
            "annual_income": 1.53,
            "next_ex_dividend_date": "2026-09-15",
        }
    )

    page = render_holdings_panel(row)

    assert "$35.41" in page
    assert "$42.18" in page
    assert "$0.62" in page
    assert "2.10%" in page
    assert "0.45%" in page
    assert "4.25%" in page
    assert "$1.53" in page
    assert "2026-09-15" in page


def test_holdings_renderer_warns_when_explicit_cash_does_not_reconcile():
    row = _row()
    row["available_cash"] = 100.0

    page = render_holdings_panel(row)

    assert "capital-reconciliation-warning" in page
    assert "does not match allocated capital" in page


def test_holdings_renderer_escapes_strategy_owned_text():
    row = _row()
    row["holdings"][0]["name"] = "<script>alert(1)</script>"
    row["holdings"][0]["source"] = "<b>unsafe</b>"

    page = render_holdings_panel(row)

    assert "<script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<b>unsafe</b>" not in page
    assert "&lt;b&gt;unsafe&lt;/b&gt;" in page


def test_holdings_renderer_has_clear_empty_state():
    page = render_holdings_panel(
        {"strategy_id": "DIVIDEND-001", "allocated_capital": 5000, "position_count": 0}
    )

    assert "0 positions" in page
    assert "Available / Undeployed Cash" in page
    assert "$5,000.00" in page
    assert "No strategy-owned holdings detail is currently reported." in page


def test_holdings_css_contains_responsive_table_and_reconciliation_styles():
    css = holdings_ui_css()

    assert ".holdings-table-wrap" in css
    assert ".holdings-summary-grid" in css
    assert ".capital-reconciliation" in css
    assert ".capital-reconciliation-warning" in css
    assert ".status-open" in css
    assert ".status-parked" in css
    assert "min-width:2050px" in css
    assert "@media(max-width:520px)" in css
