from src.dividend_bot.dividend_income_analytics import (
    ANNUAL_INCOME_METHOD,
    YEARLY_DISTRIBUTION_YIELD_METHOD,
    enrich_holdings_with_income_analytics,
)


def test_trailing_payment_history_drives_yield_and_income_without_ambiguous_provider_yield():
    holdings = [{"symbol": "TEST", "shares": 2.0, "price": 50.0, "position_status": "OPEN"}]
    market = {
        "records": [
            {
                "symbol": "TEST",
                "price": 50.0,
                "dividend_yield_percent": 9999.0,
                "history": {
                    "rows": [
                        {"date": "2026-08-07T00:00:00+00:00", "close": 50.0},
                    ]
                },
                "dividends": {
                    "payments": [
                        {"date": "2026-05-01T00:00:00+00:00", "amount": 0.50},
                        {"date": "2026-02-01T00:00:00+00:00", "amount": 0.50},
                        {"date": "2025-11-01T00:00:00+00:00", "amount": 0.50},
                        {"date": "2025-08-15T00:00:00+00:00", "amount": 0.50},
                        {"date": "2025-07-01T00:00:00+00:00", "amount": 20.00},
                    ]
                },
            }
        ]
    }

    row = enrich_holdings_with_income_analytics(holdings, market_snapshot=market)[0]

    assert row["trailing_12m_distribution_rate"] == 2.0
    assert row["trailing_12m_payment_count"] == 4
    assert row["trailing_12m_window_start"] == "2025-08-07"
    assert row["trailing_12m_window_end"] == "2026-08-07"
    assert row["trailing_12m_first_payment_date"] == "2025-08-15"
    assert row["trailing_12m_last_payment_date"] == "2026-05-01"
    assert row["dividend_yield_percent"] == 4.0
    assert row["yearly_distribution_yield_percent"] == 4.0
    assert row["yearly_distribution_yield_price"] == 50.0
    assert row["yearly_distribution_yield_method"] == YEARLY_DISTRIBUTION_YIELD_METHOD
    assert row["annual_income"] == 4.0
    assert row["annual_income_share_count"] == 2.0
    assert row["annual_income_method"] == ANNUAL_INCOME_METHOD
    assert row["payment_frequency"] == "QUARTERLY_OBSERVED"
    assert row["dividend_yield_source"] == "TRAILING_12M_PAYMENT_HISTORY"


def test_nested_quote_supplies_security_name_and_explicit_ex_date():
    holdings = [{"symbol": "TEST", "shares": 1.0, "price": 25.0, "position_status": "OPEN"}]
    market = {
        "records": [
            {
                "symbol": "TEST",
                "price": 25.0,
                "quote": {
                    "short_name": "Test Income ETF",
                    "next_ex_dividend_date": "2026-08-15",
                },
                "history": {"rows": [{"date": "2026-08-07T00:00:00+00:00", "close": 25.0}]},
                "dividends": {"payments": []},
            }
        ]
    }

    row = enrich_holdings_with_income_analytics(holdings, market_snapshot=market)[0]

    assert row["name"] == "Test Income ETF"
    assert row["next_ex_dividend_date"] == "2026-08-15"
