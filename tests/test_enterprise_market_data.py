from __future__ import annotations

import pytest

from enterprise_core.market_data import (
    EnterpriseMarketDataService,
    MarketBar,
    MarketDataProvider,
    MarketDataRequest,
    MarketDataResponse,
    ProviderEngine,
    ProviderStatus,
)
from enterprise_core.market_data.provider_engine import MarketDataUnavailableError


class StubProvider(MarketDataProvider):
    def __init__(
        self,
        name: str,
        priority: int,
        *,
        status: ProviderStatus = ProviderStatus.VERIFIED,
        bars: tuple[MarketBar, ...] = (),
        error: Exception | None = None,
    ) -> None:
        self.name = name
        self.priority = priority
        self._status = status
        self._bars = bars
        self._error = error
        self.calls = 0

    def health(self) -> ProviderStatus:
        return self._status

    def get_history(self, request: MarketDataRequest) -> MarketDataResponse:
        self.calls += 1
        if self._error:
            raise self._error
        return MarketDataResponse(
            request=request,
            bars=self._bars,
            provider=self.name,
            provider_status=self._status,
        )


def make_bar(provider: str = "yahoo") -> MarketBar:
    return MarketBar(
        symbol="SPY",
        timestamp="2026-07-28T00:00:00+00:00",
        open=630.0,
        high=635.0,
        low=628.0,
        close=634.0,
        volume=1000.0,
        provider=provider,
    )


def test_service_is_permanently_paper_only() -> None:
    assert EnterpriseMarketDataService.paper_trade_mode is True
    assert EnterpriseMarketDataService.live_trading_enabled is False
    assert EnterpriseMarketDataService.broker_execution_enabled is False


def test_provider_engine_uses_priority_order() -> None:
    yahoo = StubProvider("yahoo", 10, bars=(make_bar("yahoo"),))
    robinhood = StubProvider("robinhood_read_only", 20, bars=(make_bar("robinhood_read_only"),))
    service = EnterpriseMarketDataService(ProviderEngine([robinhood, yahoo]))

    response = service.get_history("spy")

    assert response.provider == "yahoo"
    assert yahoo.calls == 1
    assert robinhood.calls == 0
    assert service.provider_names() == ("yahoo", "robinhood_read_only")


def test_provider_engine_falls_back_after_failure() -> None:
    yahoo = StubProvider("yahoo", 10, error=RuntimeError("temporary failure"))
    robinhood = StubProvider(
        "robinhood_read_only",
        20,
        bars=(make_bar("robinhood_read_only"),),
    )
    service = EnterpriseMarketDataService(ProviderEngine([yahoo, robinhood]))

    response = service.get_history("SPY")

    assert response.provider == "robinhood_read_only"
    assert yahoo.calls == 1
    assert robinhood.calls == 1


def test_unavailable_provider_is_skipped() -> None:
    yahoo = StubProvider("yahoo", 10, status=ProviderStatus.UNAVAILABLE)
    cache = StubProvider("historical_cache", 30, bars=(make_bar("historical_cache"),))

    response = ProviderEngine([yahoo, cache]).get_history(MarketDataRequest("SPY"))

    assert response.provider == "historical_cache"
    assert yahoo.calls == 0


def test_empty_provider_response_triggers_fallback() -> None:
    yahoo = StubProvider("yahoo", 10)
    cache = StubProvider("historical_cache", 30, bars=(make_bar("historical_cache"),))

    response = ProviderEngine([yahoo, cache]).get_history(MarketDataRequest("SPY"))

    assert response.provider == "historical_cache"


def test_all_provider_failures_raise_clear_error() -> None:
    engine = ProviderEngine(
        [
            StubProvider("yahoo", 10, error=RuntimeError("failed")),
            StubProvider("robinhood_read_only", 20, status=ProviderStatus.UNAVAILABLE),
        ]
    )

    with pytest.raises(MarketDataUnavailableError, match="no provider could satisfy SPY"):
        engine.get_history(MarketDataRequest("SPY"))


def test_duplicate_provider_names_are_rejected() -> None:
    with pytest.raises(ValueError, match="provider names must be unique"):
        ProviderEngine([StubProvider("yahoo", 10), StubProvider("yahoo", 20)])


def test_market_bar_validation_rejects_invalid_ohlc() -> None:
    invalid = MarketBar(
        symbol="SPY",
        timestamp="2026-07-28T00:00:00+00:00",
        open=640.0,
        high=635.0,
        low=628.0,
        close=634.0,
        volume=1000.0,
        provider="test",
    )

    with pytest.raises(ValueError, match="open must be within"):
        invalid.validate()


def test_request_validation_rejects_blank_symbol() -> None:
    with pytest.raises(ValueError, match="symbol is required"):
        MarketDataRequest(" ").validate()
