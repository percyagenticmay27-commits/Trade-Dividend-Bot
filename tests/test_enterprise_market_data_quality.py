from __future__ import annotations

from enterprise_core.market_data import (
    EnterpriseMarketDataService,
    MarketBar,
    MarketDataRequest,
    MarketDataResponse,
    ProviderEngine,
    ProviderStatus,
    assess_history_quality,
)
from enterprise_core.market_data.provider import MarketDataProvider


class StaticProvider(MarketDataProvider):
    name = "static"
    priority = 1

    def __init__(self, response):
        self.response = response

    def health(self):
        return self.response.provider_status

    def get_history(self, request):
        return MarketDataResponse(
            request=request,
            bars=self.response.bars,
            provider=self.name,
            provider_status=self.response.provider_status,
            warnings=self.response.warnings,
        )


def _response(status=ProviderStatus.VERIFIED, confidence=1.0, timestamps=None):
    request = MarketDataRequest("SPY")
    timestamps = timestamps or ["2026-01-02T00:00:00+00:00"]
    bars = tuple(
        MarketBar(
            symbol="SPY",
            timestamp=timestamp,
            open=100,
            high=105,
            low=99,
            close=104,
            volume=1000,
            provider="fixture",
            source_confidence=confidence,
        )
        for timestamp in timestamps
    )
    return MarketDataResponse(
        request=request,
        bars=bars,
        provider="fixture",
        provider_status=status,
    )


def test_verified_high_confidence_data_is_high_quality():
    quality = assess_history_quality(_response())
    assert quality.score == 100
    assert quality.classification == "HIGH"


def test_stale_data_is_penalized():
    quality = assess_history_quality(_response(ProviderStatus.STALE, confidence=0.75))
    assert quality.score < 65
    assert quality.classification in {"DEGRADED", "UNUSABLE"}


def test_duplicate_timestamps_are_detected():
    quality = assess_history_quality(
        _response(timestamps=[
            "2026-01-02T00:00:00+00:00",
            "2026-01-02T00:00:00+00:00",
        ])
    )
    assert quality.score == 80
    assert "Duplicate timestamps detected" in quality.warnings


def test_service_returns_response_and_quality():
    fixture = _response()
    service = EnterpriseMarketDataService(ProviderEngine([StaticProvider(fixture)]))

    response, quality = service.get_history_with_quality("spy")

    assert response.request.symbol == "SPY"
    assert quality.classification == "HIGH"
    assert service.paper_trade_mode is True
    assert service.live_trading_enabled is False
    assert service.broker_execution_enabled is False
