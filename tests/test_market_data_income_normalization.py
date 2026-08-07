from __future__ import annotations

from market_data_integration_engine import refresh_market_data_snapshot


class FakeService:
    def __init__(self, quote):
        self.quote = dict(quote)

    def get_quote(self, symbol, force_refresh=False):
        payload = dict(self.quote)
        payload.setdefault("symbol", symbol)
        payload.setdefault("provider", "YAHOO_FINANCE")
        payload.setdefault("data_source", "LIVE_PROVIDER")
        payload.setdefault("is_stale", False)
        return payload

    def get_history(self, symbol, period="1y", interval="1d", force_refresh=False):
        return {
            "symbol": symbol,
            "rows": [{"date": "2026-08-07", "close": 50.0}],
            "data_source": "LIVE_PROVIDER",
            "is_stale": False,
        }

    def get_dividends(self, symbol, period="5y", force_refresh=False):
        return {
            "symbol": symbol,
            "payments": [],
            "data_source": "LIVE_PROVIDER",
            "is_stale": False,
        }


def test_market_snapshot_exposes_explicit_income_semantics():
    report = refresh_market_data_snapshot(
        ["TEST"],
        FakeService({
            "price": 50.0,
            "short_name": "Test Income ETF",
            "dividend_yield": 0.0625,
            "dividend_rate": 3.125,
            "ex_dividend_date": "2026-08-15",
        }),
    )

    assert report["status"] == "COMPLETE"
    row = report["records"][0]
    assert row["name"] == "Test Income ETF"
    assert row["dividend_yield_percent"] == 6.25
    assert row["annual_dividend_rate"] == 3.125
    assert row["next_ex_dividend_date"] == "2026-08-15"
    assert row["income_normalization_source"] == "YAHOO_FINANCE"


def test_market_snapshot_does_not_fabricate_missing_income_metrics():
    report = refresh_market_data_snapshot(
        ["TEST"],
        FakeService({"price": 50.0}),
    )

    row = report["records"][0]
    assert "name" not in row
    assert "dividend_yield_percent" not in row
    assert "annual_dividend_rate" not in row
    assert "next_ex_dividend_date" not in row
    assert "income_normalization_source" not in row


def test_zero_yield_is_preserved_when_provider_explicitly_reports_zero():
    report = refresh_market_data_snapshot(
        ["TEST"],
        FakeService({"price": 50.0, "dividend_yield": 0.0}),
    )

    row = report["records"][0]
    assert row["dividend_yield_percent"] == 0.0
