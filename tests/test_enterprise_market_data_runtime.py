from __future__ import annotations

from pathlib import Path

import pytest

from enterprise_core.market_data.diagnostics import build_market_data_diagnostics
from enterprise_core.market_data.dividend_bot_adapter import DividendBotMarketDataAdapter
from enterprise_core.market_data.factory import (
    MarketDataConfiguration,
    build_market_data_runtime,
)
from enterprise_core.market_data.models import (
    MarketBar,
    MarketDataRequest,
    MarketDataResponse,
    ProviderStatus,
)
from enterprise_core.market_data.orchestrator import MarketDataOrchestrator
from enterprise_core.market_data.provider import MarketDataProvider
from enterprise_core.market_data.provider_engine import ProviderEngine
from enterprise_core.market_data.providers.historical_cache import HistoricalCacheProvider
from enterprise_core.market_data.service import EnterpriseMarketDataService


class StaticProvider(MarketDataProvider):
    name = "static"
    priority = 1

    def health(self) -> ProviderStatus:
        return ProviderStatus.VERIFIED

    def get_history(self, request: MarketDataRequest) -> MarketDataResponse:
        return MarketDataResponse(
            request=request,
            bars=(
                MarketBar(
                    symbol=request.symbol,
                    timestamp="2026-07-29T00:00:00+00:00",
                    open=100.0,
                    high=105.0,
                    low=99.0,
                    close=104.0,
                    volume=1000.0,
                    provider=self.name,
                ),
            ),
            provider=self.name,
            provider_status=ProviderStatus.VERIFIED,
        )


class BrokenHealthProvider(StaticProvider):
    name = "broken"
    priority = 2

    def health(self) -> ProviderStatus:
        raise RuntimeError("health unavailable")


def test_orchestrator_writes_high_quality_response_to_cache(tmp_path: Path) -> None:
    service = EnterpriseMarketDataService(ProviderEngine([StaticProvider()]))
    cache = HistoricalCacheProvider(tmp_path)
    result = MarketDataOrchestrator(service, cache).get_history("AAPL")

    assert result.quality_score >= 70
    assert result.quality_level in {"HIGH", "ACCEPTABLE"}
    assert result.cache_path is not None
    assert Path(result.cache_path).exists()


def test_orchestrator_does_not_rewrite_cache_response(tmp_path: Path) -> None:
    cache = HistoricalCacheProvider(tmp_path)
    source_service = EnterpriseMarketDataService(ProviderEngine([StaticProvider()]))
    MarketDataOrchestrator(source_service, cache).get_history("AAPL")
    original_mtime = (tmp_path / "AAPL_1d.json").stat().st_mtime_ns

    cache_service = EnterpriseMarketDataService(ProviderEngine([cache]))
    result = MarketDataOrchestrator(cache_service, cache).get_history("AAPL")

    assert result.response.provider == "historical_cache"
    assert result.cache_path is None
    assert (tmp_path / "AAPL_1d.json").stat().st_mtime_ns == original_mtime


def test_diagnostics_reports_partial_provider_availability() -> None:
    diagnostics = build_market_data_diagnostics([StaticProvider(), BrokenHealthProvider()])

    assert diagnostics.overall_status == "WARNING"
    assert diagnostics.providers[0].available is True
    assert diagnostics.providers[1].available is False
    assert diagnostics.providers[1].error == "health unavailable"
    assert diagnostics.paper_trade_mode is True
    assert diagnostics.live_trading_enabled is False
    assert diagnostics.broker_execution_enabled is False


def test_configuration_rejects_unknown_keys() -> None:
    with pytest.raises(ValueError, match="unknown market data configuration keys"):
        MarketDataConfiguration.from_mapping({"not_valid": True})


def test_factory_requires_robinhood_reader_when_enabled(tmp_path: Path) -> None:
    config = MarketDataConfiguration(
        enable_yahoo=False,
        enable_robinhood_read_only=True,
        enable_historical_cache=True,
        cache_directory=str(tmp_path),
    )
    with pytest.raises(ValueError, match="robinhood_history_reader"):
        build_market_data_runtime(config)


def test_factory_builds_cache_only_runtime(tmp_path: Path) -> None:
    config = MarketDataConfiguration(
        enable_yahoo=False,
        enable_robinhood_read_only=False,
        enable_historical_cache=True,
        cache_directory=str(tmp_path),
    )
    runtime = build_market_data_runtime(config)

    assert runtime.service.provider_names() == ("historical_cache",)
    assert runtime.cache_provider is not None
    assert runtime.orchestrator.paper_trade_mode is True


def test_dividend_bot_adapter_returns_legacy_friendly_values(tmp_path: Path) -> None:
    service = EnterpriseMarketDataService(ProviderEngine([StaticProvider()]))
    adapter = DividendBotMarketDataAdapter(MarketDataOrchestrator(service))

    rows = adapter.get_price_history("aapl")

    assert rows == [
        {
            "symbol": "AAPL",
            "timestamp": "2026-07-29T00:00:00+00:00",
            "open": 100.0,
            "high": 105.0,
            "low": 99.0,
            "close": 104.0,
            "volume": 1000.0,
        }
    ]
    assert adapter.get_latest_price("AAPL") == 104.0
    assert adapter.get_close_series("AAPL") == [104.0]
    assert adapter.paper_trade_mode is True
    assert adapter.live_trading_enabled is False
    assert adapter.broker_execution_enabled is False
