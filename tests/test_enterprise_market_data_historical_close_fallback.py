from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from refresh_enterprise_market_data import refresh_strategy_market_data
from src.dividend_bot.enterprise_market_data_provider import MarketDataUnavailable

NOW = datetime(2026, 8, 4, 17, 0, tzinfo=timezone.utc)


class Provider:
    def __init__(self, results_dir: Path, *, history_available: bool = True) -> None:
        self.results_dir = results_dir
        self.attempts = []
        self.history_available = history_available

    def get_quote(self, symbol: str):
        raise MarketDataUnavailable("all live quote providers unavailable")

    def get_history(self, symbol: str, period: str, interval: str):
        if not self.history_available:
            raise MarketDataUnavailable("all history providers unavailable")
        return {
            "symbol": symbol,
            "period": period,
            "interval": interval,
            "provider": "YFINANCE",
            "generated_at": NOW.isoformat(),
            "latest_bar_date": "2026-08-04",
            "stale": False,
            "corporate_action_adjusted": True,
            "split_history": [],
            "dividend_history": [],
            "cache_used": False,
            "warnings": [],
            "bars": [
                {
                    "date": "2026-08-04",
                    "open": 138.0,
                    "high": 141.0,
                    "low": 137.0,
                    "close": 140.0,
                    "adjusted_close": 140.25,
                    "volume": 123456,
                }
            ],
        }


def test_fresh_history_close_prevents_required_symbol_block(tmp_path: Path) -> None:
    provider = Provider(tmp_path / "results")
    result = refresh_strategy_market_data(provider, "SWING-001", ["SOXL"], [])

    assert result["status"] == "WARNING"
    assert result["errors"] == []
    record = result["records"][0]
    assert record["status"] == "WARNING"
    assert record["quote"]["price"] == 140.25
    assert record["quote"]["source_type"] == "HISTORICAL_CLOSE_FALLBACK"
    assert record["quote"]["valuation_fallback"] is True
    assert record["quote"]["stale"] is False
    assert record["history"]["latest_bar_date"] == "2026-08-04"


def test_fallback_uses_close_when_adjusted_close_missing(tmp_path: Path) -> None:
    provider = Provider(tmp_path / "results")
    original = provider.get_history

    def get_history(symbol: str, period: str, interval: str):
        payload = original(symbol, period, interval)
        payload["bars"][-1]["adjusted_close"] = None
        return payload

    provider.get_history = get_history  # type: ignore[method-assign]
    result = refresh_strategy_market_data(provider, "SWING-001", ["TQQQ"], [])

    assert result["records"][0]["quote"]["price"] == 140.0


def test_missing_quote_and_history_still_blocks_required_strategy(tmp_path: Path) -> None:
    provider = Provider(tmp_path / "results", history_available=False)
    result = refresh_strategy_market_data(provider, "SWING-001", ["SOXL"], [])

    assert result["status"] == "BLOCKED"
    assert result["records"][0]["quote"] is None
    assert result["records"][0]["history"] is None
    assert result["errors"]


def test_contract_publishes_historical_close_fallback_policy(tmp_path: Path) -> None:
    import json

    provider = Provider(tmp_path / "results")
    refresh_strategy_market_data(provider, "SWING-001", ["SOXL"], [])
    contract = json.loads(
        (tmp_path / "results" / "enterprise_market_data_contract.json").read_text()
    )

    assert contract["valuation_fallback"]["enabled"] is True
    assert contract["valuation_fallback"]["source_type"] == "HISTORICAL_CLOSE_FALLBACK"
    assert contract["valuation_fallback"]["blocks_when_history_missing"] is True
