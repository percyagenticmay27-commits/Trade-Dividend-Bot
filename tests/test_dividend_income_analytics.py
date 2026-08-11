from __future__ import annotations

from src.dividend_bot.dividend_income_analytics import (
    enrich_holdings_with_income_analytics,
    total_projected_annual_income,
)


def _holding(symbol: str = "AVGW", shares: float = 2.0) -> dict[str, object]:
    return {
        "symbol": symbol,
        "shares": shares,
        "market_value": 100.0,
        "position_status": "OPEN",
        "sleeve": "A",
    }


def test_populates_percent_yield_annual_income_and_ex_date_from_authoritative_record() -> None:
    rows = enrich_holdings_with_income_analytics(
        [_holding()],
        market_snapshot={
            "AVGW": {
                "security_name": "Avantis U.S. Large Cap Value ETF",
                "dividend_yield_percent": 2.5,
                "annual_dividend_rate": 1.25,
                "next_ex_dividend_date": "2026-09-15",
                "payment_frequency": "QUARTERLY",
            }
        },
    )

    row = rows[0]
    assert row["name"] == "Avantis U.S. Large Cap Value ETF"
    assert row["dividend_yield_percent"] == 2.5
    assert row["annual_income"] == 2.5
    assert row["next_ex_dividend_date"] == "2026-09-15"
    assert row["payment_frequency"] == "QUARTERLY"
    assert row["income_analytics_source"] == "market_data_snapshot.json"


def test_explicit_annual_income_is_preferred_over_rate_derivation() -> None:
    rows = enrich_holdings_with_income_analytics(
        [_holding(shares=10.0)],
        income_snapshot={
            "AVGW": {
                "annual_income": 17.25,
                "annual_dividend_rate": 99.0,
            }
        },
    )
    assert rows[0]["annual_income"] == 17.25
    assert rows[0]["income_analytics_source"] == "income_snapshot"


def test_does_not_guess_decimal_dividend_yield_semantics() -> None:
    rows = enrich_holdings_with_income_analytics(
        [_holding()],
        market_snapshot={"AVGW": {"dividendYield": 0.025}},
    )
    assert "dividend_yield_percent" not in rows[0]


def test_missing_income_evidence_remains_missing() -> None:
    rows = enrich_holdings_with_income_analytics([_holding()], market_snapshot={})
    row = rows[0]
    assert "dividend_yield_percent" not in row
    assert "annual_income" not in row
    assert "next_ex_dividend_date" not in row
    assert "income_analytics_source" not in row


def test_reserve_row_does_not_receive_dividend_position_metrics() -> None:
    reserve = {
        "symbol": "SGOV",
        "sleeve": "RESERVE",
        "position_status": "PARKED",
        "market_value": 300.0,
    }
    rows = enrich_holdings_with_income_analytics(
        [reserve],
        market_snapshot={
            "SGOV": {
                "dividend_yield_percent": 5.0,
                "annual_income": 15.0,
                "next_ex_dividend_date": "2026-09-01",
            }
        },
    )
    row = rows[0]
    assert "dividend_yield_percent" not in row
    assert "annual_income" not in row
    assert "next_ex_dividend_date" not in row


def test_total_projected_annual_income_sums_only_reported_values() -> None:
    assert total_projected_annual_income(
        [{"annual_income": 10.25}, {}, {"annual_income": 4.75}]
    ) == 15.0
    assert total_projected_annual_income([{}, {}]) is None


def test_estimates_next_ex_date_from_observed_weekly_cadence() -> None:
    rows = enrich_holdings_with_income_analytics(
        [_holding(symbol="AMDW", shares=4.0)],
        market_snapshot={
            "AMDW": {
                "history": {
                    "rows": [
                        {"date": "2026-08-10", "close": 50.0},
                        {"date": "2026-08-11", "close": 51.0},
                    ]
                },
                "dividends": {
                    "payments": [
                        {"date": "2026-07-27", "amount": 0.845},
                        {"date": "2026-08-03", "amount": 1.648},
                        {"date": "2026-08-10", "amount": 0.797},
                    ]
                },
            }
        },
    )

    row = rows[0]
    assert row["estimated_next_ex_dividend_date"] == "2026-08-17"
    assert row["next_ex_dividend_date_status"] == "ESTIMATED_FROM_OBSERVED_CADENCE"
    assert row["next_ex_dividend_date_method"] == "OBSERVED_MEDIAN_CADENCE_7_DAYS"
    assert row["payment_frequency"] == "QUARTERLY_OBSERVED"
