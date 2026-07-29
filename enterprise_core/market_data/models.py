"""Canonical Enterprise Market Data contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence


class ProviderStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class MarketDataRequest:
    symbol: str
    interval: str = "1d"
    start: str | None = None
    end: str | None = None
    limit: int | None = None

    def validate(self) -> None:
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol is required")
        if not self.interval or not self.interval.strip():
            raise ValueError("interval is required")
        if self.limit is not None and self.limit <= 0:
            raise ValueError("limit must be greater than zero")


@dataclass(frozen=True)
class MarketBar:
    symbol: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    provider: str
    adjusted: bool = False
    session: str = "regular"
    source_confidence: float = 1.0

    def validate(self) -> None:
        if not self.symbol:
            raise ValueError("bar symbol is required")
        if not self.timestamp:
            raise ValueError("bar timestamp is required")
        if self.high < self.low:
            raise ValueError("bar high cannot be less than low")
        if not self.low <= self.open <= self.high:
            raise ValueError("bar open must be within low/high")
        if not self.low <= self.close <= self.high:
            raise ValueError("bar close must be within low/high")
        if self.volume < 0:
            raise ValueError("bar volume cannot be negative")
        if not 0.0 <= self.source_confidence <= 1.0:
            raise ValueError("source_confidence must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketDataResponse:
    request: MarketDataRequest
    bars: Sequence[MarketBar]
    provider: str
    provider_status: ProviderStatus
    warnings: Sequence[str] = field(default_factory=tuple)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        self.request.validate()
        if not self.provider:
            raise ValueError("provider is required")
        for bar in self.bars:
            bar.validate()
            if bar.symbol.upper() != self.request.symbol.upper():
                raise ValueError("bar symbol does not match request symbol")

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": asdict(self.request),
            "bars": [bar.to_dict() for bar in self.bars],
            "provider": self.provider,
            "provider_status": self.provider_status.value,
            "warnings": list(self.warnings),
            "generated_at": self.generated_at,
            "metadata": dict(self.metadata),
        }
