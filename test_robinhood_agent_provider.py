"""Tests for the read-only Robinhood Agent market-data fallback."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from market_data_provider import MarketDataService
from robinhood_agent_provider import (
    HISTORICAL_OPERATION,
    RobinhoodAgentProvider,
)
from yahoo_finance_provider import MarketDataProviderError


NOW = datetime(2026, 7, 29, 17, 0, tzinfo=timezone.utc)


def _response(symbol: str = "SPY"):
    return {
        "data": {
            "results": [
                {
                    "symbol": symbol,
                    "interval": "day",
                    "bounds": "regular",
                    "bars": [
                        {
                            "begins_at": "2026-07-27T00:00:00Z",
                            "open_price": "100.00",
                            "high_price": "104.00",
                            "low_price": "99.00",
                            "close_price": "103.00",
                            "volume": 1000,
                            "session": "reg",
                            "interpolated": False,
                        },
                        {
                            "begins_at": "2026-07-28T00:00:00Z",
                            "open_price": "103.00",
                            "high_price": "106.00",
                            "low_price": "102.00",
                            "close_price": "105.00",
                            "volume": 1200,
                            "session": "reg",
                            "interpolated": False,
                        },
                        {
                            "begins_at": "2026-07-29T00:00:00Z",
                            "open_price": "105.00",
                            "high_price": "107.00",
                            "low_price": "104.00",
                            "close_price": "106.00",
                            "volume": 900,
                            "session": "reg",
                            "interpolated": False,
                        },
                    ],
                }
            ],
            "not_found": [],
        }
    }


class FailingYahoo:
    def get_quote(self, symbol: str):
        raise MarketDataProviderError("Yahoo unavailable")

    def get_history(self, symbol: str, period: str = "1y", interval: str = "1d"):
        raise MarketDataProviderError("Yahoo unavailable")

    def get_dividends(self, symbol: str, period: str = "5y"):
        raise MarketDataProviderError("Yahoo unavailable")


class SuccessfulYahoo:
    def get_quote(self, symbol: str):
        return {"provider": "YAHOO_FINANCE", "symbol": symbol, "price": 101.0}

    def get_history(self, symbol: str, period: str = "1y", interval: str = "1d"):
        return {"provider": "YAHOO_FINANCE", "symbol": symbol, "rows": []}

    def get_dividends(self, symbol: str, period: str = "5y"):
        return {"provider": "YAHOO_FINANCE", "symbol": symbol, "payments": []}


def test_provider_invokes_verified_operation_and_normalizes_rows():
    calls = []

    def invoke(operation, payload):
        calls.append((operation, payload))
        return _response()

    provider = RobinhoodAgentProvider(invoker=invoke, now_factory=lambda: NOW)
    result = provider.get_history("spy")

    assert calls[0][0] == HISTORICAL_OPERATION
    assert calls[0][1]["symbols"] == ["SPY"]
    assert calls[0][1]["interval"] == "day"
    assert calls[0][1]["bounds"] == "regular"
    assert calls[0][1]["adjustment_type"] == "split"
    assert len(result["rows"]) == 2
    assert result["rows"][-1]["date"] == "2026-07-28"
    assert result["rows"][-1]["adj_close"] == result["rows"][-1]["close"]
    assert result["adjusted_close_source"] == "UNAVAILABLE_USE_CLOSE"
    assert result["corporate_action_adjusted"] is False


def test_interpolated_bars_are_ignored():
    payload = _response()
    payload["data"]["results"][0]["bars"][0]["interpolated"] = True
    provider = RobinhoodAgentProvider(invoker=lambda *_: payload, now_factory=lambda: NOW)
    result = provider.get_history("SPY")
    assert len(result["rows"]) == 1


def test_not_found_symbol_raises():
    provider = RobinhoodAgentProvider(
        invoker=lambda *_: {"data": {"results": [], "not_found": ["BEX"]}},
        now_factory=lambda: NOW,
    )
    with pytest.raises(MarketDataProviderError, match="symbol not found"):
        provider.get_history("BEX")


def test_yahoo_success_does_not_call_robinhood(tmp_path: Path):
    calls = []
    fallback = RobinhoodAgentProvider(
        invoker=lambda *args: calls.append(args) or _response(),
        now_factory=lambda: NOW,
    )
    service = MarketDataService(
        root_path=str(tmp_path),
        provider=SuccessfulYahoo(),
        fallback_provider=fallback,
        min_request_interval_seconds=0,
    )
    result = service.get_history("SPY", force_refresh=True)
    assert result["data_source"] == "LIVE_PROVIDER_PRIMARY"
    assert calls == []


def test_yahoo_failure_uses_robinhood_history(tmp_path: Path):
    fallback = RobinhoodAgentProvider(invoker=lambda *_: _response(), now_factory=lambda: NOW)
    service = MarketDataService(
        root_path=str(tmp_path),
        provider=FailingYahoo(),
        fallback_provider=fallback,
        min_request_interval_seconds=0,
    )
    result = service.get_history("SPY", force_refresh=True)
    assert result["data_source"] == "LIVE_PROVIDER_FALLBACK"
    assert result["provider"] == "ROBINHOOD_AGENT_READ_ONLY"
    assert [row["status"] for row in result["provider_attempts"]] == ["FAILED", "SUCCESS"]


def test_dividends_do_not_use_robinhood_ohlcv_fallback(tmp_path: Path):
    calls = []
    fallback = RobinhoodAgentProvider(
        invoker=lambda *args: calls.append(args) or _response(),
        now_factory=lambda: NOW,
    )
    service = MarketDataService(
        root_path=str(tmp_path),
        provider=FailingYahoo(),
        fallback_provider=fallback,
        min_request_interval_seconds=0,
    )
    with pytest.raises(MarketDataProviderError):
        service.get_dividends("SPY", force_refresh=True)
    assert calls == []


def test_provider_exposes_no_order_or_transfer_methods():
    provider = RobinhoodAgentProvider(invoker=lambda *_: _response(), now_factory=lambda: NOW)
    forbidden = {
        "place_order",
        "submit_order",
        "cancel_order",
        "move_money",
        "transfer_funds",
        "manage_position",
    }
    assert not any(hasattr(provider, name) for name in forbidden)
