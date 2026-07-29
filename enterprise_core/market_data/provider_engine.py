"""Provider priority and fallback engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import MarketDataRequest, MarketDataResponse, ProviderStatus
from .provider import MarketDataProvider


class MarketDataUnavailableError(RuntimeError):
    """Raised when no registered provider can satisfy a request."""


@dataclass(frozen=True)
class ProviderAttempt:
    provider: str
    status: ProviderStatus
    error: str | None = None


class ProviderEngine:
    """Select providers by priority without exposing selection to strategies."""

    def __init__(self, providers: Iterable[MarketDataProvider]) -> None:
        ordered = sorted(providers, key=lambda provider: provider.priority)
        if not ordered:
            raise ValueError("at least one market data provider is required")
        names = [provider.name for provider in ordered]
        if len(names) != len(set(names)):
            raise ValueError("provider names must be unique")
        self._providers = tuple(ordered)

    @property
    def provider_names(self) -> tuple[str, ...]:
        return tuple(provider.name for provider in self._providers)

    def get_history(self, request: MarketDataRequest) -> MarketDataResponse:
        request.validate()
        attempts: list[ProviderAttempt] = []

        for provider in self._providers:
            status = provider.health()
            if status == ProviderStatus.UNAVAILABLE:
                attempts.append(ProviderAttempt(provider.name, status))
                continue
            try:
                if not provider.supports(request):
                    attempts.append(
                        ProviderAttempt(provider.name, ProviderStatus.PARTIAL, "unsupported request")
                    )
                    continue
                response = provider.get_history(request)
                response.validate()
                if not response.bars:
                    attempts.append(
                        ProviderAttempt(provider.name, ProviderStatus.PARTIAL, "empty response")
                    )
                    continue
                return response
            except Exception as exc:  # provider failures must permit fallback
                attempts.append(ProviderAttempt(provider.name, status, str(exc)))

        details = "; ".join(
            f"{attempt.provider}:{attempt.status.value}"
            + (f":{attempt.error}" if attempt.error else "")
            for attempt in attempts
        )
        raise MarketDataUnavailableError(
            f"no provider could satisfy {request.symbol} history request ({details})"
        )
