"""Tests for the Version 1.1 read-only market data layer."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from market_data_cache import MarketDataCache
from market_data_provider import MarketDataService, build_market_snapshot
from yahoo_finance_provider import MarketDataProviderError


class FakeProvider:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.quote_calls = 0
        self.history_calls = 0
        self.dividend_calls = 0

    def get_quote(self, symbol: str):
        self.quote_calls += 1
        if self.fail:
            raise MarketDataProviderError("provider unavailable")
        return {"provider": "FAKE", "symbol": symbol, "price": 123.45}

    def get_history(self, symbol: str, period: str = "1y", interval: str = "1d"):
        self.history_calls += 1
        if self.fail:
            raise MarketDataProviderError("provider unavailable")
        return {"provider": "FAKE", "symbol": symbol, "period": period, "interval": interval, "rows": []}

    def get_dividends(self, symbol: str, period: str = "5y"):
        self.dividend_calls += 1
        if self.fail:
            raise MarketDataProviderError("provider unavailable")
        return {"provider": "FAKE", "symbol": symbol, "period": period, "payments": []}


def test_cache_round_trip(tmp_path: Path):
    cache = MarketDataCache(str(tmp_path))
    cache.write("quote", "AAPL", {"symbol": "AAPL", "price": 100})
    assert cache.read("quote", "AAPL", max_age_seconds=60) == {"symbol": "AAPL", "price": 100}


def test_quote_uses_fresh_cache(tmp_path: Path):
    provider = FakeProvider()
    service = MarketDataService(root_path=str(tmp_path), provider=provider, min_request_interval_seconds=0)
    first = service.get_quote("aapl")
    second = service.get_quote("AAPL")
    assert first["data_source"] == "LIVE_PROVIDER"
    assert second["data_source"] == "CACHE_FRESH"
    assert provider.quote_calls == 1


def test_stale_cache_fallback_when_provider_fails(tmp_path: Path):
    good = MarketDataService(root_path=str(tmp_path), provider=FakeProvider(), min_request_interval_seconds=0)
    good.get_quote("MSFT")
    failing = MarketDataService(root_path=str(tmp_path), provider=FakeProvider(fail=True), quote_ttl_seconds=0, min_request_interval_seconds=0)
    result = failing.get_quote("MSFT", force_refresh=True)
    assert result["data_source"] == "CACHE_STALE_FALLBACK"
    assert result["is_stale"] is True
    assert "provider_warning" in result


def test_no_data_raises_when_provider_fails(tmp_path: Path):
    service = MarketDataService(root_path=str(tmp_path), provider=FakeProvider(fail=True), min_request_interval_seconds=0)
    with pytest.raises(MarketDataProviderError):
        service.get_quote("NVDA")


def test_history_and_dividend_cache_keys_are_distinct(tmp_path: Path):
    provider = FakeProvider()
    service = MarketDataService(root_path=str(tmp_path), provider=provider, min_request_interval_seconds=0)
    service.get_history("SPY", period="1y", interval="1d")
    service.get_history("SPY", period="5y", interval="1wk")
    service.get_dividends("SPY", period="5y")
    assert provider.history_calls == 2
    assert provider.dividend_calls == 1


def test_build_market_snapshot_preserves_paper_only_flags(tmp_path: Path):
    payload = build_market_snapshot(["AAPL", "MSFT"], root_path=str(tmp_path), provider=FakeProvider())
    assert payload["status"] == "COMPLETE"
    assert len(payload["quotes"]) == 2
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["read_only_market_data"] is True


def test_cache_file_is_json(tmp_path: Path):
    cache = MarketDataCache(str(tmp_path))
    path = cache.write("quote", "AMD", {"symbol": "AMD", "price": 150})
    decoded = json.loads(path.read_text(encoding="utf-8"))
    assert decoded["namespace"] == "quote"
    assert decoded["payload"]["symbol"] == "AMD"
