from src.dividend_bot.enterprise_holdings_ui import render_holdings_panel
from src.dividend_bot.enterprise_position_history_ui import render_position_history_panel


def test_holdings_ui_shows_current_entry_method_without_fabrication() -> None:
    page = render_holdings_panel({
        "strategy_id": "DIVIDEND-001",
        "allocated_capital": 100.0,
        "portfolio_value": 100.0,
        "position_count": 2,
        "holdings": [
            {
                "symbol": "AAA", "name": "Example", "sleeve": "A",
                "position_status": "OPEN", "shares": 10, "price": 10,
                "market_value": 100, "entry_method": "STRATEGY_A",
            },
            {
                "symbol": "SGOV", "sleeve": "RESERVE", "position_status": "PARKED",
                "market_value": 0,
            },
        ],
    })
    assert "Entry Method" in page
    assert "STRATEGY_A" in page
    assert "Entry Method is strategy-owned lifecycle evidence" in page
    # SGOV has no owner and must not inherit Strategy A.
    assert "Not reported" in page


def test_position_history_ui_shows_owner_controlled_exit_reason() -> None:
    page = render_position_history_panel({
        "performance_detail": {
            "position_lifecycle": [{
                "symbol": "AAA", "pair": "AAA / BBB", "sleeve": "A",
                "lifecycle_status": "PARKED_IN_SGOV",
                "first_purchase_date": "2026-08-01", "last_exit_date": "2026-08-05",
                "entry_value": 100, "last_exit_value": 95, "realized_gain_loss": -5,
                "entry_method": "STRATEGY_B", "exit_method": "STRATEGY_B",
                "last_exit_reason": "PRICE_BELOW_EMA20",
                "last_exit_action": "PAPER_SELL_TO_SGOV", "reentry_count": 0,
                "strategy_exit_evidence_source": "paper_state.json",
            }]
        }
    })
    assert "Entry Method" in page
    assert "Exit Method" in page
    assert "Why Sold" in page
    assert page.count("STRATEGY_B") >= 2
    assert "Price fell below its 20-day exponential moving average." in page
    assert "PRICE_BELOW_EMA20" not in page
    assert "paper_state.json" in page
