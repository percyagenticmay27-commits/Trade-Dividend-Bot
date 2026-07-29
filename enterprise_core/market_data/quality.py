"""Deterministic quality assessment for normalized market-data responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import MarketDataResponse, ProviderStatus


@dataclass(frozen=True)
class MarketDataQuality:
    score: int
    classification: str
    warnings: tuple[str, ...]

    def validate(self) -> None:
        if not 0 <= self.score <= 100:
            raise ValueError("quality score must be between 0 and 100")
        if self.classification not in {"HIGH", "ACCEPTABLE", "DEGRADED", "UNUSABLE"}:
            raise ValueError("invalid quality classification")


def assess_history_quality(response: MarketDataResponse) -> MarketDataQuality:
    response.validate()
    warnings = list(response.warnings)
    if not response.bars:
        return MarketDataQuality(0, "UNUSABLE", tuple(warnings + ["No market bars available"]))

    score = 100
    if response.provider_status is ProviderStatus.PARTIAL:
        score -= 15
    elif response.provider_status is ProviderStatus.STALE:
        score -= 35
    elif response.provider_status is ProviderStatus.UNAVAILABLE:
        score = 0

    timestamps = [bar.timestamp for bar in response.bars]
    if timestamps != sorted(timestamps):
        score -= 15
        warnings.append("Bars are not sorted chronologically")
    if len(timestamps) != len(set(timestamps)):
        score -= 20
        warnings.append("Duplicate timestamps detected")

    confidences = [bar.source_confidence for bar in response.bars]
    average_confidence = sum(confidences) / len(confidences)
    score -= round((1.0 - average_confidence) * 30)

    try:
        for timestamp in timestamps:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        score -= 20
        warnings.append("One or more timestamps are not ISO-8601 compatible")

    score = max(0, min(100, score))
    if score >= 85:
        classification = "HIGH"
    elif score >= 65:
        classification = "ACCEPTABLE"
    elif score >= 40:
        classification = "DEGRADED"
    else:
        classification = "UNUSABLE"

    quality = MarketDataQuality(score, classification, tuple(warnings))
    quality.validate()
    return quality
