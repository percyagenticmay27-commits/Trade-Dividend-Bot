"""Provider abstraction for Enterprise Market Data."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import MarketDataRequest, MarketDataResponse, ProviderStatus


class MarketDataProvider(ABC):
    """Read-only market data provider contract.

    Providers retrieve and normalize data. They never place orders, manage
    accounts, move capital, or expose provider-specific objects to strategies.
    """

    name: str
    priority: int

    @abstractmethod
    def health(self) -> ProviderStatus:
        """Return the provider's current availability classification."""

    @abstractmethod
    def get_history(self, request: MarketDataRequest) -> MarketDataResponse:
        """Return normalized historical OHLCV data."""

    def supports(self, request: MarketDataRequest) -> bool:
        request.validate()
        return True
