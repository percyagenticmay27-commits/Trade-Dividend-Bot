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


def test_holdings_renderer_groups_overview_analytics_and_income():
    page = render_holdings_panel(_row())
    assert "Holdings Overview" in page
    assert "Position Analytics" in page
    assert ">Income<" in page
    assert "holdings-overview-table" in page
    assert "holdings-analytics-table" in page
    assert "holdings-income-table" in page


def test_holdings_overview_displays_dual_weights():
    page = render_holdings_panel(_row())
    assert "% Strategy Allocation" in page
    assert "% Deployed Portfolio" in page
    assert "0.72%" in page
    assert "9.48%" in page


def test_holdings_renderer_uses_professional_position_columns():
    page = render_holdings_panel(_row())
    for heading in (
        "Symbol", "Name", "Status", "Shares", "Market Price", "Market Value",
        "Cost Basis", "Avg Cost", "Unrealized P&amp;L", "Total Return",
        "Daily Change", "Yearly Distribution Yield", "Annual Income", "Next Ex-Date", "Audit", "Evidence",
    ):
        assert heading in page
    assert "Avantis U.S. Large Cap Value ETF" in page
    assert "OPEN" in page
    assert "PARKED" in page
    assert "✓ Verified" in page


def test_holdings_renderer_uses_professional_not_reported_badges():
    page = render_holdings_panel(_row())
    assert "class='not-reported'>Not reported</span>" in page
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
            "yearly_distribution_yield_percent": 63.08,
            "annual_income": 23.14,
            "next_ex_dividend_date": "2026-09-15",
            "trailing_12m_distribution_rate": 27.0712,
            "trailing_12m_payment_count": 52,
            "trailing_12m_window_start": "2025-08-07",
            "trailing_12m_window_end": "2026-08-07",
            "yearly_distribution_yield_price": 42.92,
            "yearly_distribution_yield_method": "TRAILING_365D_DISTRIBUTIONS_DIVIDED_BY_CURRENT_PRICE",
            "income_analytics_source": "market_data_snapshot.json",
        }
    )
    page = render_holdings_panel(row)
    assert "$35.41" in page
    assert "$42.18" in page
    assert "$0.62" in page
    assert "2.10%" in page
    assert "0.45%" in page
    assert "63.08%" in page
    assert "$23.14" in page
    assert "2026-09-15" in page
    assert "T12M distributions: $27.0712/share" in page
    assert "Payments: 52" in page
    assert "Yield price: $42.92" in page
    assert "Window: 2025-08-07 → 2026-08-07" in page
    assert "Trailing 365D Distributions Divided By Current Price" in page
    assert "market_data_snapshot.json" in page
    assert "metric-positive" in page


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


def test_holdings_css_is_self_contained_and_responsive():
    css = holdings_ui_css()
    assert css.lstrip().startswith("<style>")
    assert css.rstrip().endswith("</style>")
    assert ".holdings-overview-table" in css
    assert ".holdings-analytics-table" in css
    assert ".holdings-income-table" in css
    assert ".yield-audit" in css
    assert ".not-reported" in css
    assert ".metric-positive" in css
    assert ".metric-negative" in css
    assert ".capital-reconciliation" in css
    assert "@media(max-width:520px)" in css
