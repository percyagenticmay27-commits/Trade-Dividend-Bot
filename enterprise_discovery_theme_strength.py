"""Authoritative shared Theme Strength evidence for Enterprise discovery candidates.

Theme Strength is broader than short-window mention momentum. This producer combines
current theme evidence breadth, source-class diversity, governed catalyst support,
market confirmation, and sector confirmation into one fail-closed 0-100 score. It
does not change Swing's existing Theme Momentum calculation.
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

CATALYST_FAMILIES = (
    "earnings_fundamental_growth",
    "analyst_institutional_revisions",
    "guidance_outlook",
    "product_innovation",
    "contracts_customer_wins",
    "capex_infrastructure_demand",
    "regulatory_government",
    "ma_strategic_activity",
    "sector_industry_tailwind",
    "corporate_capital_catalyst",
)

# Additional catalyst families are accepted only from explicit reviewed evidence.
# We do not infer them from titles or free text inside this scoring layer.
CATALYST_EVIDENCE_FLAGS = {
    "guidance_outlook": "guidance_outlook_related",
    "product_innovation": "product_innovation_related",
    "contracts_customer_wins": "contracts_customer_wins_related",
    "capex_infrastructure_demand": "capex_infrastructure_demand_related",
    "regulatory_government": "regulatory_government_related",
    "ma_strategic_activity": "ma_strategic_activity_related",
    "sector_industry_tailwind": "sector_industry_tailwind_related",
    "corporate_capital_catalyst": "corporate_capital_catalyst_related",
}

# Diminishing returns prevent many mediocre/repeated catalyst families from
# manufacturing a perfect score. Only distinct confirmed families consume slots.
CATALYST_SLOT_POINTS = (35.0, 25.0, 15.0, 10.0, 7.5, 5.0, 2.5)

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


def _confirmed_catalysts(
    evidence: list[Mapping[str, Any]],
    *,
    revenue_growth: float,
    eps_growth: float,
    analyst_upgrades: float,
    analyst_downgrades: float,
) -> tuple[dict[str, bool], dict[str, Any]]:
    source_earnings = any(bool(item.get("earnings_growth_related")) for item in evidence)
    source_analyst = any(bool(item.get("analyst_upgrade_related")) for item in evidence)
    fundamentals_earnings = revenue_growth > 0.0 and eps_growth > 0.0
    fundamentals_analyst = analyst_upgrades > analyst_downgrades

    catalysts = {
        "earnings_fundamental_growth": source_earnings or fundamentals_earnings,
        "analyst_institutional_revisions": source_analyst or fundamentals_analyst,
    }
    for family, flag in CATALYST_EVIDENCE_FLAGS.items():
        catalysts[family] = any(bool(item.get(flag)) for item in evidence)

    if set(catalysts) != set(CATALYST_FAMILIES):
        raise ValueError("catalyst taxonomy is incomplete")
    details = {
        "source_earnings_growth_catalyst": source_earnings,
        "source_analyst_upgrade_catalyst": source_analyst,
        "fundamentals_earnings_growth_catalyst": fundamentals_earnings,
        "fundamentals_analyst_upgrade_catalyst": fundamentals_analyst,
    }
    return catalysts, details


def _catalyst_score(catalysts: Mapping[str, bool]) -> float:
    count = sum(1 for family in CATALYST_FAMILIES if catalysts.get(family) is True)
    return _clamp(sum(CATALYST_SLOT_POINTS[:count]))


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

    if not themes or not evidence or market is None or not isinstance(financial_components, Mapping) or not isinstance(financial_evidence, Mapping):
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
    if any(value is None for value in (relative_strength, volume_ratio, sector_confirmation, revenue_growth, eps_growth, analyst_upgrades, analyst_downgrades)):
        return None

    breadth_score = _clamp(min(len(producers), 4) / 4.0 * 100.0)
    diversity_score = _clamp(min(len(source_classes), 3) / 3.0 * 100.0)
    catalysts, catalyst_details = _confirmed_catalysts(
        evidence,
        revenue_growth=revenue_growth,
        eps_growth=eps_growth,
        analyst_upgrades=analyst_upgrades,
        analyst_downgrades=analyst_downgrades,
    )
    catalyst_score = _catalyst_score(catalysts)
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

    confirmed = [family for family in CATALYST_FAMILIES if catalysts[family]]
    return {
        "score": score,
        "components": components,
        "evidence_timestamp": timestamp,
        "freshness_status": "CURRENT_CYCLE",
        "is_stale": False,
        "provenance": "AI_CIO_ENTERPRISE_DISCOVERY: reviewed source evidence + authoritative market evidence + Financial Health fundamentals/sector confirmation",
        "evidence": {
            "underlying_symbol": str(row.get("underlying_symbol") or "").strip().upper(),
            "themes": themes,
            "independent_producer_count": len(producers),
            "source_class_count": len(source_classes),
            "source_classes": sorted(source_classes),
            "catalyst_taxonomy_version": "1.0",
            "catalyst_family_count": len(CATALYST_FAMILIES),
            "confirmed_catalyst_count": len(confirmed),
            "confirmed_catalyst_families": confirmed,
            "catalysts": catalysts,
            "earnings_growth_catalyst": catalysts["earnings_fundamental_growth"],
            "analyst_upgrade_catalyst": catalysts["analyst_institutional_revisions"],
            **catalyst_details,
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
        "policy": "GOVERNED_CATALYST_TAXONOMY_FAIL_CLOSED",
    }


def attach_candidate_theme_strength(report: dict[str, Any], *, generated_at: str | datetime | None = None) -> dict[str, Any]:
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
    report["theme_strength_policy"] = "GOVERNED_CATALYST_TAXONOMY_FAIL_CLOSED"
    return report
