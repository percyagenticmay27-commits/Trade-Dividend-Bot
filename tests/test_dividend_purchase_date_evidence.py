from src.dividend_bot.dividend_position_analytics import enrich_holdings_with_position_analytics
from src.dividend_bot.enterprise_holdings_purchase_date_ui import render_holdings_panel
from src.dividend_bot.enterprise_income_ui import render_income_panel


def test_current_position_purchase_date_comes_from_first_open_buy() -> None:
    rows = [
        {"Date": "2026-07-01", "Action": "PAPER_BUY_OPEN", "Ticker": "AVGW", "Shares": "1", "Price": "40", "Paper_Value": "40"},
        {"Date": "2026-07-05", "Action": "PAPER_BUY_FROM_SGOV", "Ticker": "AVGW", "Shares": "1", "Price": "42", "Paper_Value": "42"},
    ]
    holdings = [{"symbol": "AVGW", "shares": 2, "market_value": 90, "position_status": "OPEN"}]

    item = enrich_holdings_with_position_analytics(holdings, rows)[0]

    assert item["purchase_date"] == "2026-07-01"
    assert item["purchase_date_source"] == "paper_trade_log.csv"
    assert item["purchase_date_method"] == "CURRENT_OPEN_POSITION_FIRST_BUY"


def test_purchase_date_resets_after_full_exit_and_reentry() -> None:
    rows = [
        {"Date": "2026-06-01", "Action": "PAPER_BUY_OPEN", "Ticker": "AVGW", "Shares": "2", "Price": "40", "Paper_Value": "80"},
        {"Date": "2026-06-20", "Action": "PAPER_SELL_TO_SGOV", "Ticker": "AVGW", "Shares": "2", "Price": "45", "Paper_Value": "90"},
        {"Date": "2026-08-02", "Action": "PAPER_BUY_FROM_SGOV", "Ticker": "AVGW", "Shares": "1", "Price": "44", "Paper_Value": "44"},
    ]
    holdings = [{"symbol": "AVGW", "shares": 1, "market_value": 46, "position_status": "OPEN"}]

    item = enrich_holdings_with_position_analytics(holdings, rows)[0]

    assert item["purchase_date"] == "2026-08-02"


def test_missing_purchase_date_is_not_fabricated() -> None:
    rows = [
        {"Action": "PAPER_BUY_OPEN", "Ticker": "AVGX", "Shares": "1", "Price": "50", "Paper_Value": "50"},
    ]
    holdings = [{"symbol": "AVGX", "shares": 1, "market_value": 55, "position_status": "OPEN"}]

    item = enrich_holdings_with_position_analytics(holdings, rows)[0]

    assert "purchase_date" not in item


def test_reserve_does_not_fabricate_purchase_date() -> None:
    rows = [
        {"Date": "2026-07-01", "Action": "PAPER_BUY_OPEN", "Ticker": "SGOV", "Shares": "3", "Price": "100", "Paper_Value": "300"},
    ]
    holdings = [{"symbol": "SGOV", "sleeve": "RESERVE", "market_value": 300, "position_status": "PARKED"}]

    item = enrich_holdings_with_position_analytics(holdings, rows)[0]

    assert "purchase_date" not in item


def test_holdings_and_income_display_current_position_purchase_date() -> None:
    holding = {
        "symbol": "AVGW",
        "name": "Roundhill AVGO WeeklyPay ETF",
        "sleeve": "A",
        "position_status": "OPEN",
        "shares": 1,
        "price": 43,
        "market_value": 43,
        "purchase_date": "2026-07-01",
        "cost_basis": 40,
        "average_cost": 40,
        "unrealized_pnl": 3,
        "total_return_percent": 7.5,
        "daily_change_percent": 1.0,
        "yearly_distribution_yield_percent": 63.0,
        "annual_income": 27.09,
        "payment_frequency": "WEEKLY_OBSERVED",
        "income_analytics_source": "market_data_snapshot.json",
    }
    row = {
        "allocated_capital": 5000,
        "position_count": 1,
        "holdings": [holding],
        "income": 0,
        "projected_annual_income": 27.09,
        "income_events": [],
    }

    holdings_html = render_holdings_panel(row)
    income_html = render_income_panel(row)

    assert "Purchase Date" in holdings_html
    assert "2026-07-01" in holdings_html
    assert "Purchase Date" in income_html
    assert "2026-07-01" in income_html
