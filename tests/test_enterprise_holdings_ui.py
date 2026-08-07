from src.dividend_bot.enterprise_holdings_ui import holdings_ui_css, render_holdings_panel


def _row():
    return {
        "strategy_id": "DIVIDEND-001",
        "portfolio_value": 468.16,
        "position_count": 3,
        "holdings": [
            {
                "symbol": "AVGW",
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


def test_holdings_renderer_uses_professional_table_and_summary_cards():
    page = render_holdings_panel(_row())

    assert "class='holdings-table'" in page
    assert "Portfolio Value" in page
    assert "$468.16" in page
    assert "Cash Reserve (SGOV)" in page
    assert "$329.78" in page
    assert "Invested" in page
    assert "AVGW" in page
    assert "AVGX" in page
    assert "SGOV" in page
    assert "OPEN" in page
    assert "PARKED" in page
    assert "% Portfolio" in page
    assert "✓ Verified" in page


def test_holdings_renderer_does_not_fabricate_missing_pnl():
    page = render_holdings_panel(_row())

    assert "Unrealized P&amp;L" not in page
    assert "Total Return" not in page
    assert "+2.00%" not in page


def test_holdings_renderer_escapes_strategy_owned_text():
    row = _row()
    row["holdings"][0]["pair"] = "<script>alert(1)</script>"
    row["holdings"][0]["source"] = "<b>unsafe</b>"

    page = render_holdings_panel(row)

    assert "<script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<b>unsafe</b>" not in page
    assert "&lt;b&gt;unsafe&lt;/b&gt;" in page


def test_holdings_renderer_has_clear_empty_state():
    page = render_holdings_panel(
        {"strategy_id": "DIVIDEND-001", "portfolio_value": 5000, "position_count": 0}
    )

    assert "0 positions" in page
    assert "No strategy-owned holdings detail is currently reported." in page


def test_holdings_css_contains_responsive_table_and_status_styles():
    css = holdings_ui_css()

    assert ".holdings-table-wrap" in css
    assert ".holdings-summary-grid" in css
    assert ".status-open" in css
    assert ".status-parked" in css
    assert "@media(max-width:520px)" in css
