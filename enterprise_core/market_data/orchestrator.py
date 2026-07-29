"""Market-data orchestration with validated cache persistence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import MarketDataResponse, ProviderStatus
from .providers.historical_cache import HistoricalCacheProvider
from .quality import assess_market_data_quality
from .service import EnterpriseMarketDataService


@dataclass(frozen=True)
class OrchestrationResult:
    response: MarketDataResponse
    quality_score: float
    quality_level: str
    cache_path: str | None
    warnings: tuple[str, ...]


class MarketDataOrchestrator:
    """Coordinates retrieval, quality assessment, and safe cache writes."""

    paper_trade_mode = True
    live_trading_enabled = False
    broker_execution_enabled = False

    def __init__(
        self,
        service: EnterpriseMarketDataService,
        cache_provider: HistoricalCacheProvider | None = None,
        *,
        minimum_cache_quality: float = 70.0,
    ) -> None:
        if not 0.0 <= minimum_cache_quality <= 100.0:
            raise ValueError("minimum_cache_quality must be between 0 and 100")
        self._service = service
        self._cache_provider = cache_provider
        self._minimum_cache_quality = minimum_cache_quality

    def get_history(self, symbol: str, **kwargs: object) -> OrchestrationResult:
        response = self._service.get_history(symbol, **kwargs)
        assessment = assess_market_data_quality(response)
        cache_path: Path | None = None
        warnings = list(response.warnings)

        should_cache = (
            self._cache_provider is not None
            and response.provider != self._cache_provider.name
            and response.provider_status in (ProviderStatus.VERIFIED, ProviderStatus.PARTIAL)
            and assessment.score >= self._minimum_cache_quality
            and bool(response.bars)
        )
        if should_cache:
            try:
                cache_path = self._cache_provider.write(response)
            except (OSError, ValueError) as exc:
                warnings.append(f"cache write failed: {exc}")

        return OrchestrationResult(
            response=response,
            quality_score=assessment.score,
            quality_level=assessment.level.value,
            cache_path=str(cache_path) if cache_path is not None else None,
            warnings=tuple(warnings),
        )
