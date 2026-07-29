"""Configuration-driven construction for Enterprise Market Data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .orchestrator import MarketDataOrchestrator
from .provider import MarketDataProvider
from .provider_engine import ProviderEngine
from .providers.historical_cache import HistoricalCacheProvider
from .providers.robinhood_read_only import RobinhoodReadOnlyProvider
from .providers.yahoo_finance import YahooFinanceProvider
from .service import EnterpriseMarketDataService


@dataclass(frozen=True)
class MarketDataConfiguration:
    enable_yahoo: bool = True
    enable_robinhood_read_only: bool = False
    enable_historical_cache: bool = True
    cache_directory: str = "results/enterprise_market_data_cache"
    cache_max_age_seconds: int | None = 86_400
    minimum_cache_quality: float = 70.0

    def validate(self) -> None:
        if not any(
            (
                self.enable_yahoo,
                self.enable_robinhood_read_only,
                self.enable_historical_cache,
            )
        ):
            raise ValueError("at least one market data provider must be enabled")
        if self.enable_historical_cache and not self.cache_directory.strip():
            raise ValueError("cache_directory is required when cache is enabled")
        if self.cache_max_age_seconds is not None and self.cache_max_age_seconds <= 0:
            raise ValueError("cache_max_age_seconds must be greater than zero")
        if not 0.0 <= self.minimum_cache_quality <= 100.0:
            raise ValueError("minimum_cache_quality must be between 0 and 100")

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "MarketDataConfiguration":
        allowed = {field_name for field_name in cls.__dataclass_fields__}
        unknown = sorted(set(values) - allowed)
        if unknown:
            raise ValueError(f"unknown market data configuration keys: {', '.join(unknown)}")
        config = cls(**values)
        config.validate()
        return config


@dataclass(frozen=True)
class MarketDataRuntime:
    providers: tuple[MarketDataProvider, ...]
    cache_provider: HistoricalCacheProvider | None
    service: EnterpriseMarketDataService
    orchestrator: MarketDataOrchestrator


def build_market_data_runtime(
    configuration: MarketDataConfiguration,
    *,
    robinhood_history_reader: Callable[..., Sequence[Mapping[str, object]]] | None = None,
) -> MarketDataRuntime:
    configuration.validate()
    providers: list[MarketDataProvider] = []
    cache_provider: HistoricalCacheProvider | None = None

    if configuration.enable_yahoo:
        providers.append(YahooFinanceProvider())

    if configuration.enable_robinhood_read_only:
        if robinhood_history_reader is None:
            raise ValueError(
                "robinhood_history_reader is required when Robinhood read-only is enabled"
            )
        providers.append(RobinhoodReadOnlyProvider(robinhood_history_reader))

    if configuration.enable_historical_cache:
        cache_provider = HistoricalCacheProvider(
            Path(configuration.cache_directory),
            max_age_seconds=configuration.cache_max_age_seconds,
        )
        providers.append(cache_provider)

    engine = ProviderEngine(providers)
    service = EnterpriseMarketDataService(engine)
    orchestrator = MarketDataOrchestrator(
        service,
        cache_provider,
        minimum_cache_quality=configuration.minimum_cache_quality,
    )
    return MarketDataRuntime(tuple(providers), cache_provider, service, orchestrator)
