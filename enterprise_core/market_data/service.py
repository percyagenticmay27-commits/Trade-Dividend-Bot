"""Public Enterprise Market Data service."""

from __future__ import annotations

from .models import MarketDataRequest, MarketDataResponse
from .provider_engine import ProviderEngine


class EnterpriseMarketDataService:
    """Stable strategy-facing market data boundary."""

    paper_trade_mode = True
    live_trading_enabled = False
    broker_execution_enabled = False

    def __init__(self, provider_engine: ProviderEngine) -> None:
        self._provider_engine = provider_engine

    def get_history(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
    ) -> MarketDataResponse:
        request = MarketDataRequest(
            symbol=symbol.strip().upper(),
            interval=interval,
            start=start,
            end=end,
            limit=limit,
        )
        return self._provider_engine.get_history(request)

    def provider_names(self) -> tuple[str, ...]:
        """Operational visibility for Enterprise monitoring, not strategies."""
        return self._provider_engine.provider_names
