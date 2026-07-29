"""Validated JSON historical-cache provider."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models import MarketBar, MarketDataRequest, MarketDataResponse, ProviderStatus
from ..provider import MarketDataProvider


class HistoricalCacheProvider(MarketDataProvider):
    name = "historical_cache"
    priority = 30

    def __init__(self, cache_directory: str | Path, max_age_seconds: int | None = None):
        self.cache_directory = Path(cache_directory)
        self.max_age_seconds = max_age_seconds
        if max_age_seconds is not None and max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be greater than zero")
        self._last_status = ProviderStatus.PARTIAL

    def health(self) -> ProviderStatus:
        return self._last_status if self.cache_directory.exists() else ProviderStatus.UNAVAILABLE

    def get_history(self, request: MarketDataRequest) -> MarketDataResponse:
        request.validate()
        path = self._path_for(request)
        if not path.exists():
            self._last_status = ProviderStatus.UNAVAILABLE
            return MarketDataResponse(
                request=request,
                bars=(),
                provider=self.name,
                provider_status=ProviderStatus.UNAVAILABLE,
                warnings=(f"Historical cache file not found: {path.name}",),
                metadata={"cache_path": str(path)},
            )

        payload = json.loads(path.read_text(encoding="utf-8"))
        bars = self._parse_bars(payload, request)
        stale = self._is_stale(path)
        status = ProviderStatus.STALE if stale else ProviderStatus.PARTIAL
        self._last_status = status
        warnings = ("Historical cache is stale",) if stale else ("Serving validated cache fallback",)
        return MarketDataResponse(
            request=request,
            bars=tuple(bars),
            provider=self.name,
            provider_status=status,
            warnings=warnings,
            metadata={
                "cache_path": str(path),
                "cached_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
            },
        )

    def write(self, response: MarketDataResponse) -> Path:
        response.validate()
        if not response.bars:
            raise ValueError("cannot cache an empty market data response")
        self.cache_directory.mkdir(parents=True, exist_ok=True)
        path = self._path_for(response.request)
        payload = response.to_dict()
        payload["cached_from_provider"] = response.provider
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def _path_for(self, request: MarketDataRequest) -> Path:
        safe_symbol = "".join(char for char in request.symbol.upper() if char.isalnum() or char in ("-", "."))
        safe_interval = "".join(char for char in request.interval if char.isalnum())
        return self.cache_directory / f"{safe_symbol}_{safe_interval}.json"

    def _is_stale(self, path: Path) -> bool:
        if self.max_age_seconds is None:
            return False
        age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
        return age > self.max_age_seconds

    @classmethod
    def _parse_bars(cls, payload: dict[str, Any], request: MarketDataRequest) -> list[MarketBar]:
        raw_bars = payload.get("bars")
        if not isinstance(raw_bars, list):
            raise ValueError("cache payload must contain a bars list")
        bars: list[MarketBar] = []
        for row in raw_bars:
            if not isinstance(row, dict):
                raise ValueError("cache bar must be an object")
            bar = MarketBar(
                symbol=str(row.get("symbol") or request.symbol).upper(),
                timestamp=str(row["timestamp"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0.0)),
                provider=cls.name,
                adjusted=bool(row.get("adjusted", False)),
                session=str(row.get("session") or "regular"),
                source_confidence=min(float(row.get("source_confidence", 0.75)), 0.85),
            )
            bar.validate()
            if bar.symbol != request.symbol.upper():
                raise ValueError("cached bar symbol does not match request")
            bars.append(bar)
        bars.sort(key=lambda bar: bar.timestamp)
        if request.limit is not None:
            bars = bars[-request.limit :]
        return bars
