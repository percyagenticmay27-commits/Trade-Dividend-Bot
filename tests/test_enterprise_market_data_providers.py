from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from enterprise_core.market_data.models import MarketDataRequest, ProviderStatus
from enterprise_core.market_data.providers import (
    HistoricalCacheProvider,
    RobinhoodReadOnlyProvider,
    YahooFinanceProvider,
)


def _yahoo_payload():
    return {
        "chart": {
            "result": [
                {
                    "timestamp": [1767225600],
                    "indicators": {
                        "quote": [
                            {
                                "open": [100.0],
                                "high": [105.0],
                                "low": [99.0],
                                "close": [104.0],
                                "volume": [1000],
                            }
                        ],
                        "adjclose": [{"adjclose": [103.5]}],
                    },
                }
            ],
            "error": None,
        }
    }


def test_yahoo_normalizes_history_without_network():
    provider = YahooFinanceProvider(loader=lambda url, timeout: _yahoo_payload())
    response = provider.get_history(MarketDataRequest("spy", limit=1))

    assert response.provider == "yahoo_finance"
    assert response.provider_status is ProviderStatus.VERIFIED
    assert response.bars[0].symbol == "SPY"
    assert response.bars[0].close == 104.0
    assert response.bars[0].adjusted is True


def test_yahoo_failure_marks_provider_unavailable():
    def fail(url, timeout):
        raise OSError("offline")

    provider = YahooFinanceProvider(loader=fail)
    with pytest.raises(RuntimeError, match="Yahoo Finance history request failed"):
        provider.get_history(MarketDataRequest("SPY"))
    assert provider.health() is ProviderStatus.UNAVAILABLE


def test_robinhood_normalizes_mcp_style_rows():
    provider = RobinhoodReadOnlyProvider(
        history_reader=lambda request: [
            {
                "begins_at": "2026-01-02T00:00:00Z",
                "open_price": "50",
                "high_price": "52",
                "low_price": "49",
                "close_price": "51",
                "volume": "500",
            }
        ]
    )
    response = provider.get_history(MarketDataRequest("SCHD"))

    assert response.provider_status is ProviderStatus.VERIFIED
    assert response.bars[0].symbol == "SCHD"
    assert response.bars[0].provider == "robinhood_read_only"
    assert response.metadata["execution_enabled"] is False
    assert provider.paper_trade_mode is True
    assert provider.live_trading_enabled is False
    assert provider.broker_execution_enabled is False


def test_robinhood_has_no_execution_methods():
    forbidden = {"buy", "sell", "place_order", "cancel_order", "transfer"}
    assert forbidden.isdisjoint(set(dir(RobinhoodReadOnlyProvider)))


def test_cache_writes_and_reads_validated_response(tmp_path):
    yahoo = YahooFinanceProvider(loader=lambda url, timeout: _yahoo_payload())
    original = yahoo.get_history(MarketDataRequest("SPY"))
    cache = HistoricalCacheProvider(tmp_path)

    path = cache.write(original)
    response = cache.get_history(MarketDataRequest("SPY"))

    assert path.exists()
    assert response.provider == "historical_cache"
    assert response.provider_status is ProviderStatus.PARTIAL
    assert response.bars[0].provider == "historical_cache"
    assert response.bars[0].source_confidence <= 0.85


def test_cache_missing_file_returns_unavailable_response(tmp_path):
    response = HistoricalCacheProvider(tmp_path).get_history(MarketDataRequest("QQQ"))
    assert response.bars == ()
    assert response.provider_status is ProviderStatus.UNAVAILABLE


def test_cache_rejects_symbol_mismatch(tmp_path):
    path = tmp_path / "SPY_1d.json"
    path.write_text(
        json.dumps(
            {
                "bars": [
                    {
                        "symbol": "QQQ",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "open": 1,
                        "high": 2,
                        "low": 1,
                        "close": 2,
                        "volume": 10,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="symbol does not match"):
        HistoricalCacheProvider(tmp_path).get_history(MarketDataRequest("SPY"))


def test_cache_rejects_empty_write(tmp_path):
    provider = YahooFinanceProvider(loader=lambda url, timeout: {"chart": {"result": []}})
    empty = provider.get_history(MarketDataRequest("SPY"))
    with pytest.raises(ValueError, match="cannot cache an empty"):
        HistoricalCacheProvider(tmp_path).write(empty)
