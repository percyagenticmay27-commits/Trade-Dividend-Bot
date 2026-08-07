from src.dividend_bot.dividend_position_analytics import (
    enrich_holdings_with_position_analytics,
    total_unrealized_pnl,
)


def test_reconstructs_open_cost_basis_after_sell_and_reentry() -> None:
    rows = [
        {"Action": "PAPER_BUY_OPEN", "Ticker": "AVGW", "Shares": "2", "Price": "10", "Paper_Value": "20"},
        {"Action": "PAPER_SELL_TO_SGOV", "Ticker": "AVGW", "Shares": "2", "Price": "8", "Paper_Value": "16"},
        {"Action": "PAPER_BUY_FROM_SGOV", "Ticker": "AVGW", "Shares": "1", "Price": "12", "Paper_Value": "12"},
    ]
    holdings = [{"symbol": "AVGW", "shares": 1, "market_value": 15, "position_status": "OPEN"}]

    enriched = enrich_holdings_with_position_analytics(holdings, rows)

    assert enriched[0]["cost_basis"] == 12.0
    assert enriched[0]["average_cost"] == 12.0
    assert enriched[0]["unrealized_pnl"] == 3.0
    assert enriched[0]["total_return_percent"] == 25.0


def test_multiple_buys_use_weighted_average_cost() -> None:
    rows = [
        {"Action": "PAPER_BUY_OPEN", "Ticker": "AVGX", "Shares": "1", "Price": "10", "Paper_Value": "10"},
        {"Action": "PAPER_BUY_FROM_SGOV", "Ticker": "AVGX", "Shares": "1", "Price": "14", "Paper_Value": "14"},
    ]
    holdings = [{"symbol": "AVGX", "shares": 2, "market_value": 30, "position_status": "OPEN"}]

    enriched = enrich_holdings_with_position_analytics(holdings, rows)

    assert enriched[0]["cost_basis"] == 24.0
    assert enriched[0]["average_cost"] == 12.0
    assert enriched[0]["unrealized_pnl"] == 6.0
    assert enriched[0]["total_return_percent"] == 25.0


def test_market_snapshot_adds_name_and_daily_change_without_fabrication() -> None:
    holdings = [{"symbol": "NVDW", "shares": 1, "market_value": 42, "position_status": "OPEN"}]
    market = {
        "symbols": [
            {
                "symbol": "NVDW",
                "longName": "GraniteShares 2x Long NVDA Daily ETF",
                "price": 42,
                "previous_close": 40,
            }
        ]
    }

    enriched = enrich_holdings_with_position_analytics(holdings, [], market)

    assert enriched[0]["name"] == "GraniteShares 2x Long NVDA Daily ETF"
    assert enriched[0]["daily_change_percent"] == 5.0
    assert "cost_basis" not in enriched[0]
    assert "unrealized_pnl" not in enriched[0]


def test_reserve_row_does_not_fabricate_position_analytics() -> None:
    rows = [{"Action": "PAPER_BUY_OPEN", "Ticker": "SGOV", "Shares": "3", "Price": "100", "Paper_Value": "300"}]
    holdings = [{"symbol": "SGOV", "sleeve": "RESERVE", "market_value": 300, "position_status": "PARKED"}]

    enriched = enrich_holdings_with_position_analytics(holdings, rows)

    assert "cost_basis" not in enriched[0]
    assert "average_cost" not in enriched[0]
    assert "unrealized_pnl" not in enriched[0]


def test_total_unrealized_pnl_uses_only_reported_values() -> None:
    holdings = [
        {"symbol": "A", "unrealized_pnl": 2.25},
        {"symbol": "B"},
        {"symbol": "C", "unrealized_pnl": -1.0},
    ]

    assert total_unrealized_pnl(holdings) == 1.25
    assert total_unrealized_pnl([{"symbol": "B"}]) is None
