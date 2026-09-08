"""Provider-aware market symbol normalization helpers."""
from __future__ import annotations

from dataclasses import dataclass


class UnsupportedProvider(ValueError):
    """Raised when no normalization rule exists for a provider."""


@dataclass(frozen=True)
class NormalizedSymbol:
    canonical: str
    provider: str
    provider_symbol: str


def normalize_symbol(symbol: str, provider: str) -> NormalizedSymbol:
    """Return the canonical symbol and provider-specific identifier.

    Version 1 rules intentionally remain conservative.  YFinance and
    Robinhood use the canonical uppercase symbol.  Stooq uses lowercase
    identifiers and appends ``.us`` for ordinary US-listed symbols unless
    a market suffix is already present.
    """
    canonical = symbol.strip().upper()
    if not canonical or not all(ch.isalnum() or ch in ".-^" for ch in canonical):
        raise ValueError("invalid symbol")

    normalized_provider = provider.strip().upper()
    if normalized_provider in {"YFINANCE", "ROBINHOOD_MCP", "LOCAL_CACHE"}:
        provider_symbol = canonical
    elif normalized_provider == "STOOQ":
        lowered = canonical.lower()
        if lowered.startswith("^"):
            provider_symbol = lowered
        elif "." in lowered:
            provider_symbol = lowered
        else:
            provider_symbol = f"{lowered}.us"
    else:
        raise UnsupportedProvider(f"unsupported provider: {provider}")

    return NormalizedSymbol(
        canonical=canonical,
        provider=normalized_provider,
        provider_symbol=provider_symbol,
    )
