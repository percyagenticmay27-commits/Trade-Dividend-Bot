from src.dividend_bot.enterprise_holdings_ui import holdings_ui_css, render_holdings_panel


def _row():
    return {
        "strategy_id": "DIVIDEND-001",
        "allocated_capital": 5000.0,
        "portfolio_value": 379.96,
        "position_count": 3,
        "holdings": [
            {"symbol": "AVGW", "name": "Avantis U.S. Large Cap Value ETF", "pair": "AVGW / AVGX", "sleeve": "A", "position_status": "OPEN", "shares": 0.8395752964, "price": 42.919998, "market_value": 36.03, "source": "paper_state.json"},
            {"symbol": "AVGX", "name": "Avantis International Value ETF", "pair": "AVGW / AVGX", "sleeve": "B", "position_status": "OPEN", "shares": 0.2526217178, "price": 56.02, "market_value": 14.15, "source": "paper_state.json"},
            {"symbol": "SGOV", "name": "iShares 0-3 Month Treasury Bond ETF", "pair": "CASH RESERVE", "sleeve": "RESERVE", "position_status": "PARKED", "shares": None, "price": None, "market_value": 329.78, "source": "paper_state.json"},
        ],
    }


def test_holdings_renderer_distinguishes_allocated_basis_from_current_market_value():
    page = render_holdings_panel(_row())
    assert "Allocated Capital" in page and "$5,000.00" in page
    assert "Current Portfolio Value" in page and "$379.96" in page
    assert "Invested Positions" in page and "$50.18" in page
    assert "Cash Reserve (SGOV)" in page and "$329.78" in page
    assert "Available / Undeployed Cash" in page
    assert "Not reported" in page
    assert "Market gain/loss is not inferred as undeployed cash" in page
    assert "-$4,620.04" in page


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
        "Cost Basis", "Avg Cost", "Unrealized P&amp;L", "Total Return", "Daily Change",
        "Yearly Distribution Yield", "Annual Income", "Next Ex-Date", "Audit", "Evidence",
    ):
        assert heading in page
    assert "Avantis U.S. Large Cap Value ETF" in page
    assert "OPEN" in page
    assert "PARKED" in page
    assert "No current income projection evidence is available." in page
    assert "Audit source" in page


def test_holdings_renderer_uses_professional_not_reported_badges():
    page = render_holdings_panel(_row())
    assert "class='not-reported'>Not reported</span>" in page
    assert "+2.00%" not in page
    assert "+$2.89" not in page


def test_holdings_renderer_displays_authoritative_optional_position_analytics():
    row = _row()
    row["holdings"][0].update({
        "cost_basis": 35.41, "average_cost": 42.18, "unrealized_pnl": 0.62,
        "total_return_percent": 2.10, "daily_change_percent": 0.45,
        "yearly_distribution_yield_percent": 63.08, "annual_income": 23.14,
        "next_ex_dividend_date": "2026-09-15",
        "trailing_12m_distribution_rate": 27.0712, "trailing_12m_payment_count": 52,
        "trailing_12m_window_start": "2025-08-07", "trailing_12m_window_end": "2026-08-07",
        "yearly_distribution_yield_price": 42.92,
        "yearly_distribution_yield_price_source": "HOLDING_CURRENT_PRICE",
        "yearly_distribution_yield_price_as_of": "2026-08-07",
        "yearly_distribution_yield_method": "TRAILING_365D_DISTRIBUTIONS_DIVIDED_BY_CURRENT_HOLDING_PRICE",
        "income_analytics_source": "market_data_snapshot.json",
    })
    page = render_holdings_panel(row)
    assert "$35.41" in page and "$42.18" in page and "$0.62" in page
    assert "2.10%" in page and "0.45%" in page and "63.08%" in page and "$23.14" in page
    assert "2026-09-15" in page
    assert "T12M distributions: $27.0712/share" in page
    assert "Payments: 52" in page
    assert "Yield price: $42.92" in page
    assert "Price source: Holding Current Price" in page
    assert "Price as-of: 2026-08-07" in page
    assert "Window: 2025-08-07 → 2026-08-07" in page
    assert "Trailing 365D Distributions Divided By Current Holding Price" in page
    assert "market_data_snapshot.json" in page
    assert "metric-positive" in page


def test_holdings_renderer_warns_when_reported_portfolio_value_does_not_match_visible_evidence():
    row = _row()
    row["portfolio_value"] = 468.16
    page = render_holdings_panel(row)
    assert "capital-reconciliation-warning" in page
    assert "does not match reported portfolio value" in page


def test_explicit_undeployed_cash_is_added_to_current_value_without_being_inferred():
    row = _row()
    row["available_cash"] = 100.0
    row["portfolio_value"] = 479.96
    page = render_holdings_panel(row)
    assert "Available / Undeployed Cash" in page
    assert "$100.00" in page
    assert "Current Portfolio Value" in page
    assert "$479.96" in page


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
    page = render_holdings_panel({"strategy_id": "DIVIDEND-001", "allocated_capital": 5000, "position_count": 0})
    assert "0 positions" in page
    assert "Available / Undeployed Cash" in page
    assert "Not reported" in page
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


def test_holdings_renderer_explains_legacy_hold_and_exit_consensus() -> None:
    row = _row()
    row["holdings"][0].update({
        "strategy_owner": "LEGACY_UNASSIGNED",
        "entry_method": "LEGACY_UNASSIGNED",
        "exit_state": "WARNING_BUFFERED",
        "exit_warning_active": True,
        "exit_buffered": True,
        "exit_warning_reasons": ["PRICE_BELOW_EMA20"],
        "sell_trigger": False,
        "sell_reasons": [],
        "exit_evidence_source": "entry_score_report.json",
        "exit_evidence_generated_at_utc": "2026-08-11T12:00:00Z",
    })
    page = render_holdings_panel(row)
    assert "Position Management" in page
    assert "HOLD — CONSENSUS PENDING" in page
    assert "requires both Strategy A and Strategy B to confirm an exit" in page
    assert "Price below ema20" in page
    assert "2026-08-11T12:00:00Z" in page


def test_holdings_renderer_marks_confirmed_owner_exit_as_actionable() -> None:
    row = _row()
    row["holdings"][0].update({
        "strategy_owner": "STRATEGY_B",
        "exit_state": "SELL_CONFIRMED",
        "sell_trigger": True,
        "sell_reasons": ["PRICE_BELOW_EMA20"],
    })
    page = render_holdings_panel(row)
    assert "SELL CONFIRMED" in page
    assert "The owning strategy confirmed its exit conditions" in page
    assert "management-sell" in page


def test_holdings_income_explains_estimated_ex_date_and_evidence_source() -> None:
    row = _row()
    row["holdings"][0].update({
        "yearly_distribution_yield_percent": 55.81,
        "annual_income": 217.62,
        "estimated_next_ex_dividend_date": "2026-08-17",
        "income_analytics_source": "market_data_snapshot.json",
    })
    page = render_holdings_panel(row)
    assert "2026-08-17" in page
    assert "Estimated" in page
    assert "Observed distribution history and current holding price support this projection." in page
    assert "Audit source" in page
    assert "market_data_snapshot.json" in page

def test_swing_holdings_render_explicit_reconciliation_without_false_warning():
    page = render_holdings_panel({
        "strategy_id": "SWING-001",
        "allocated_capital": 4500.0,
        "portfolio_value": 4525.52,
        "cash_balance": 2700.0,
        "invested_capital": 1800.0,
        "positions_market_value": 1825.52,
        "position_count": 2,
        "unrealized_pnl": 25.52,
        "holdings": [
            {
                "symbol": "SOXL",
                "shares": 8.04145854,
                "entry_price": 139.899993896484,
                "current_price": 143.264297485352,
                "market_value": 1152.05,
                "unrealized_pnl": 27.05,
                "unrealized_pnl_percent": 2.404444,
                "active_strategy": "Strategy A",
            },
            {
                "symbol": "TQQQ",
                "shares": 9.021652,
                "entry_price": 74.819999694824,
                "current_price": 74.650001525879,
                "market_value": 673.47,
                "unrealized_pnl": -1.53,
                "unrealized_pnl_percent": -0.226667,
                "active_strategy": "Strategy A",
            },
        ],
    })

    assert "2 positions" in page
    assert "SOXL" in page and "TQQQ" in page
    assert "Invested Capital" in page and "$1,800.00" in page
    assert "Positions Market Value" in page and "$1,825.52" in page
    assert "Cash Reserve" in page and "$2,700.00" in page
    assert "Current Portfolio Value" in page and "$4,525.52" in page
    assert "Unrealized P&amp;L" in page and "+$25.52" in page
    assert "$143.26" in page and "$74.65" in page
    assert "$139.90" in page and "$74.82" in page
    assert "Strategy A" in page
    assert "does not match reported portfolio value" not in page
    assert "capital-reconciliation-ok" in page

