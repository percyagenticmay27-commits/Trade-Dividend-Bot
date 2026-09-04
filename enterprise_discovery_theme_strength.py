"""Authoritative shared Theme Strength evidence for Enterprise discovery candidates.

Theme Strength is broader than short-window mention momentum. This producer combines
current theme evidence breadth, source-class diversity, explicit catalysts, market
confirmation, and sector confirmation into one fail-closed 0-100 score. It does not
change Swing's existing Theme Momentum calculation; it produces upstream evidence
that can be validated independently by downstream consumers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping

THEME_STRENGTH_COMPONENTS = (
    "evidence_breadth",
    "source_class_diversity",
    "catalyst_support",
    "market_confirmation",
    "sector_confirmation",
)

WEIGHTS = {
    "evidence_breadth": 0.25,
    "source_class_diversity": 0.15,
    "catalyst_support": 0.15,
    "market_confirmation": 0.25,
    "sector_confirmation": 0.20,
}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def _linear(value: float, low: float, high: float) -> float:
    if high == low:
        raise ValueError("high and low must differ")
    return _clamp((value - low) * 100.0 / (high - low))


def _normalized_evidence(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    items = row.get("source_evidence") or row.get("evidence_sources") or []
    return [item for item in items if isinstance(item, Mapping)] if isinstance(items, list) else []


def build_theme_strength_block(
    row: Mapping[str, Any],
    *,
    generated_at: str | datetime | None = None,
) -> dict[str, Any] | None:
    """Return complete Theme Strength evidence, otherwise None without placeholders."""
    themes = sorted({str(value).strip() for value in row.get("themes", []) if str(value).strip()})
    evidence = _normalized_evidence(row)
    market = row.get("market_evidence") if isinstance(row.get("market_evidence"), Mapping) else None
    financial = row.get("financial_health") if isinstance(row.get("financial_health"), Mapping) else None
    financial_components = financial.get("components") if isinstance(financial, Mapping) else None
    financial_evidence = financial.get("evidence") if isinstance(financial, Mapping) else None

    if (
        not themes
        or not evidence
        or market is None
        or not isinstance(financial_components, Mapping)
        or not isinstance(financial_evidence, Mapping)
    ):
        return None
    if str(market.get("status") or "").upper() != "AVAILABLE" or market.get("is_stale"):
        return None

    producers = {
        str(item.get("producer") or item.get("source") or "").strip().lower()
        for item in evidence
        if str(item.get("producer") or item.get("source") or "").strip()
    }
    source_classes = {
        str(item.get("source_class") or "").strip().upper()
        for item in evidence
        if str(item.get("source_class") or "").strip()
    }
    if not producers or not source_classes:
        return None

    relative_strength = _number(market.get("relative_strength_vs_benchmark_percent"))
    volume_ratio = _number(market.get("volume_expansion_ratio"))
    sector_confirmation = _number(financial_components.get("sector_strength"))
    revenue_growth = _number(financial_evidence.get("revenue_growth"))
    eps_growth = _number(financial_evidence.get("eps_growth"))
    analyst_upgrades = _number(financial_evidence.get("analyst_upgrades_90d"))
    analyst_downgrades = _number(financial_evidence.get("analyst_downgrades_90d"))
    if (
        relative_strength is None
        or volume_ratio is None
        or sector_confirmation is None
        or revenue_growth is None
        or eps_growth is None
        or analyst_upgrades is None
        or analyst_downgrades is None
    ):
        return None

    breadth_score = _clamp(min(len(producers), 4) / 4.0 * 100.0)
    diversity_score = _clamp(min(len(source_classes), 3) / 3.0 * 100.0)

    # Catalyst support is confirmation, not headline classification. Reviewed source
    # evidence may explicitly identify a catalyst, while the authoritative Financial
    # Health block independently confirms whether earnings are actually growing and
    # whether analyst revisions are net-positive. This prevents a generic "earnings"
    # title from receiving catalyst credit without fundamental support.
    source_earnings_catalyst = any(bool(item.get("earnings_growth_related")) for item in evidence)
    source_analyst_catalyst = any(bool(item.get("analyst_upgrade_related")) for item in evidence)
    fundamentals_earnings_catalyst = revenue_growth > 0.0 and eps_growth > 0.0
    fundamentals_analyst_catalyst = analyst_upgrades > analyst_downgrades
    earnings_catalyst = source_earnings_catalyst or fundamentals_earnings_catalyst
    analyst_catalyst = source_analyst_catalyst or fundamentals_analyst_catalyst
    catalyst_score = float(50 * int(earnings_catalyst) + 50 * int(analyst_catalyst))

    relative_score = _linear(relative_strength, -5.0, 5.0)
    volume_score = _linear(volume_ratio, 0.5, 1.5)
    market_score = round((relative_score + volume_score) / 2.0, 2)

    components = {
        "evidence_breadth": breadth_score,
        "source_class_diversity": diversity_score,
        "catalyst_support": catalyst_score,
        "market_confirmation": market_score,
        "sector_confirmation": _clamp(sector_confirmation),
    }
    if set(components) != set(THEME_STRENGTH_COMPONENTS):
        return None

    score = round(sum(components[name] * WEIGHTS[name] for name in THEME_STRENGTH_COMPONENTS), 2)
    stamp = generated_at or datetime.now(timezone.utc)
    if isinstance(stamp, datetime):
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        timestamp = stamp.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    else:
        timestamp = str(stamp).strip()
    if not timestamp:
        return None

    return {
        "score": score,
        "components": components,
        "evidence_timestamp": timestamp,
        "provenance": "AI_CIO_ENTERPRISE_DISCOVERY: reviewed source evidence + authoritative market evidence + Financial Health fundamentals/sector confirmation",
        "evidence": {
            "underlying_symbol": str(row.get("underlying_symbol") or "").strip().upper(),
            "themes": themes,
            "independent_producer_count": len(producers),
            "source_class_count": len(source_classes),
            "source_classes": sorted(source_classes),
            "earnings_growth_catalyst": earnings_catalyst,
            "analyst_upgrade_catalyst": analyst_catalyst,
            "source_earnings_growth_catalyst": source_earnings_catalyst,
            "source_analyst_upgrade_catalyst": source_analyst_catalyst,
            "fundamentals_earnings_growth_catalyst": fundamentals_earnings_catalyst,
            "fundamentals_analyst_upgrade_catalyst": fundamentals_analyst_catalyst,
            "revenue_growth": revenue_growth,
            "eps_growth": eps_growth,
            "analyst_upgrades_90d": analyst_upgrades,
            "analyst_downgrades_90d": analyst_downgrades,
            "relative_strength_vs_benchmark_percent": relative_strength,
            "volume_expansion_ratio": volume_ratio,
            "sector_strength_component": sector_confirmation,
            "market_latest_session": market.get("latest_session"),
            "market_benchmark_symbol": market.get("benchmark_symbol"),
            "financial_health_evidence_timestamp": financial.get("evidence_timestamp"),
        },
        "policy": "ALL_COMPONENTS_REQUIRED_FAIL_CLOSED",
    }


def attach_candidate_theme_strength(
    report: dict[str, Any],
    *,
    generated_at: str | datetime | None = None,
) -> dict[str, Any]:
    """Attach complete Theme Strength blocks wherever authoritative evidence exists."""
    for row in report.get("observations", []):
        if not isinstance(row, dict):
            continue
        row.pop("theme_strength", None)
        block = build_theme_strength_block(row, generated_at=generated_at)
        if block is not None:
            row["theme_strength"] = block
        elif row.get("themes"):
            row.setdefault("evidence_warnings", []).append(
                f"Theme Strength evidence incomplete or stale for {str(row.get('underlying_symbol') or '').strip().upper()}; block omitted."
            )
    report["theme_strength_policy"] = "ALL_COMPONENTS_REQUIRED_FAIL_CLOSED"
    return report
