"""Operational diagnostics for Enterprise Market Data providers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable

from .models import ProviderStatus
from .provider import MarketDataProvider


@dataclass(frozen=True)
class ProviderDiagnostic:
    name: str
    priority: int
    status: ProviderStatus
    available: bool
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass(frozen=True)
class MarketDataDiagnostics:
    generated_at: str
    overall_status: str
    providers: tuple[ProviderDiagnostic, ...]
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "overall_status": self.overall_status,
            "providers": [provider.to_dict() for provider in self.providers],
            "paper_trade_mode": self.paper_trade_mode,
            "live_trading_enabled": self.live_trading_enabled,
            "broker_execution_enabled": self.broker_execution_enabled,
        }


def build_market_data_diagnostics(
    providers: Iterable[MarketDataProvider],
) -> MarketDataDiagnostics:
    diagnostics: list[ProviderDiagnostic] = []
    for provider in sorted(providers, key=lambda item: item.priority):
        try:
            status = provider.health()
            diagnostics.append(
                ProviderDiagnostic(
                    name=provider.name,
                    priority=provider.priority,
                    status=status,
                    available=status != ProviderStatus.UNAVAILABLE,
                )
            )
        except Exception as exc:
            diagnostics.append(
                ProviderDiagnostic(
                    name=provider.name,
                    priority=provider.priority,
                    status=ProviderStatus.UNAVAILABLE,
                    available=False,
                    error=str(exc),
                )
            )

    available_count = sum(item.available for item in diagnostics)
    if not diagnostics or available_count == 0:
        overall = "ERROR"
    elif available_count < len(diagnostics):
        overall = "WARNING"
    else:
        overall = "OK"

    return MarketDataDiagnostics(
        generated_at=datetime.now(timezone.utc).isoformat(),
        overall_status=overall,
        providers=tuple(diagnostics),
    )
