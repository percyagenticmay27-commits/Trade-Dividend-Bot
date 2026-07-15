"""Institutional Context & Pattern Intelligence Engine v1.0.

Paper-only contextual analysis for security lifecycle, IPO stability, company
archetypes, historical twins, market-pattern similarity, and case-study lessons.
The engine provides context only and never promotes, ranks, allocates, or trades.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from html import escape
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

MODULE_NAME = "institutional_context_pattern_intelligence"
MODULE_VERSION = "1.0.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

LIFECYCLE_STAGES = {
    "IPO", "POST_LOCKUP", "EARLY_PUBLIC", "GROWTH_EXPANSION", "ESTABLISHED",
    "MATURE", "DECLINING", "TURNAROUND", "RECOVERY", "UNKNOWN",
}
ARCHETYPES = {
    "EMERGING_DISRUPTOR", "INFRASTRUCTURE_BUILDER", "COMPOUNDER",
    "DIVIDEND_COMPOUNDER", "CAPITAL_INTENSIVE_GROWTH", "HIGH_INNOVATION_HIGH_RISK",
    "DEFENSIVE_CASH_FLOW", "TURNAROUND", "CYCLICAL_LEADER", "PLATFORM_COMPANY",
    "UNKNOWN",
}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    if not math.isfinite(float(value)):
        return low
    return round(max(low, min(high, float(value))), 2)


@dataclass(frozen=True)
class IPOProfile:
    ipo_method: str = "UNKNOWN"
    ipo_date: str = ""
    lockup_expiration: str = ""
    months_public: float = 0.0
    insider_ownership_pct: float = 0.0
    institutional_ownership_pct: float = 0.0
    float_score: float = 50.0
    liquidity_score: float = 50.0
    volatility_score: float = 50.0
    earnings_reports_available: int = 0
    financial_history_score: float = 0.0


@dataclass(frozen=True)
class HistoricalCase:
    case_id: str
    name: str
    lifecycle_stage: str
    archetypes: tuple[str, ...] = ()
    features: Mapping[str, float] = field(default_factory=dict)
    observed_outcome: str = ""
    lessons: tuple[str, ...] = ()
    market_pattern: str = ""


@dataclass(frozen=True)
class MarketPattern:
    pattern_id: str
    name: str
    features: Mapping[str, float] = field(default_factory=dict)
    observed_outcomes: tuple[str, ...] = ()
    lessons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextRequest:
    symbol: str
    as_of_date: str
    lifecycle_stage: str = "UNKNOWN"
    archetype_candidates: tuple[str, ...] = ()
    current_features: Mapping[str, float] = field(default_factory=dict)
    ipo_profile: IPOProfile | None = None
    opportunity_quality_score: float = 0.0
    research_conviction_score: float = 0.0
    evidence_confidence: float = 0.0


def calculate_ipo_stability(profile: IPOProfile | None) -> dict[str, Any]:
    if profile is None:
        return {"applicable": False, "score": 100.0, "status": "NOT_APPLICABLE", "risk_flags": []}
    age = _clamp(profile.months_public / 18.0 * 100.0)
    lockup = 100.0
    flags: list[str] = []
    if profile.lockup_expiration:
        try:
            lockup_date = date.fromisoformat(profile.lockup_expiration)
            days = (lockup_date - date.today()).days
            if -30 <= days <= 60:
                lockup = 25.0
                flags.append("Lock-up expiration is near or recently completed.")
            elif days > 60:
                lockup = 55.0
                flags.append("Lock-up expiration remains ahead.")
        except ValueError:
            lockup = 40.0
            flags.append("Lock-up date is invalid or unverified.")
    earnings = _clamp(profile.earnings_reports_available / 4.0 * 100.0)
    ownership = _clamp((100.0 - min(100.0, profile.insider_ownership_pct)) * 0.45 + profile.institutional_ownership_pct * 0.55)
    volatility_stability = _clamp(100.0 - profile.volatility_score)
    score = _clamp(
        age * 0.20 + lockup * 0.20 + profile.financial_history_score * 0.15
        + earnings * 0.15 + ownership * 0.10 + profile.liquidity_score * 0.10
        + volatility_stability * 0.10
    )
    status = "STABLE" if score >= 75 else "DEVELOPING" if score >= 55 else "OBSERVATION_ONLY"
    if profile.months_public < 3:
        flags.append("Security is within the first three months of public trading.")
    if profile.earnings_reports_available < 2:
        flags.append("Limited public earnings history.")
    return {"applicable": True, "score": score, "status": status, "risk_flags": flags}


def _similarity(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    keys = sorted(set(left) & set(right))
    if not keys:
        return 0.0
    differences = [abs(_clamp(left[k]) - _clamp(right[k])) for k in keys]
    return _clamp(100.0 - sum(differences) / len(differences))


def find_historical_twins(request: ContextRequest, cases: Sequence[HistoricalCase], limit: int = 5) -> list[dict[str, Any]]:
    ranked = []
    for case in cases:
        score = _similarity(request.current_features, case.features)
        if request.lifecycle_stage == case.lifecycle_stage:
            score = _clamp(score + 5.0)
        overlap = set(request.archetype_candidates) & set(case.archetypes)
        if overlap:
            score = _clamp(score + min(8.0, 2.0 * len(overlap)))
        ranked.append({
            "case_id": case.case_id,
            "name": case.name,
            "similarity_score": score,
            "observed_outcome": case.observed_outcome,
            "lessons": list(case.lessons),
            "market_pattern": case.market_pattern,
        })
    return sorted(ranked, key=lambda item: (-item["similarity_score"], item["name"]))[: max(0, limit)]


def match_market_patterns(request: ContextRequest, patterns: Sequence[MarketPattern], limit: int = 5) -> list[dict[str, Any]]:
    matches = [
        {
            "pattern_id": pattern.pattern_id,
            "name": pattern.name,
            "pattern_match_score": _similarity(request.current_features, pattern.features),
            "observed_outcomes": list(pattern.observed_outcomes),
            "lessons": list(pattern.lessons),
        }
        for pattern in patterns
    ]
    return sorted(matches, key=lambda item: (-item["pattern_match_score"], item["name"]))[: max(0, limit)]


def build_context_report(
    request: ContextRequest,
    historical_cases: Sequence[HistoricalCase] = (),
    market_patterns: Sequence[MarketPattern] = (),
) -> dict[str, Any]:
    lifecycle = request.lifecycle_stage if request.lifecycle_stage in LIFECYCLE_STAGES else "UNKNOWN"
    archetypes = [a if a in ARCHETYPES else "UNKNOWN" for a in request.archetype_candidates] or ["UNKNOWN"]
    ipo = calculate_ipo_stability(request.ipo_profile)
    twins = find_historical_twins(request, historical_cases)
    patterns = match_market_patterns(request, market_patterns)
    twin_score = twins[0]["similarity_score"] if twins else 0.0
    pattern_score = patterns[0]["pattern_match_score"] if patterns else 0.0
    archetype_confidence = _clamp(45.0 + 10.0 * min(4, len([a for a in archetypes if a != "UNKNOWN"])))
    context_confidence = _clamp(
        request.evidence_confidence * 0.35
        + twin_score * 0.20
        + pattern_score * 0.20
        + archetype_confidence * 0.10
        + request.research_conviction_score * 0.10
        + (ipo["score"] if ipo["applicable"] else 75.0) * 0.05
    )
    warnings: list[str] = []
    if not historical_cases:
        warnings.append("No historical case library was supplied.")
    if not market_patterns:
        warnings.append("No market-pattern library was supplied.")
    if request.opportunity_quality_score <= 0:
        warnings.append("Opportunity Quality was not supplied; context cannot determine investability.")
    action = "CONTINUE_QUALIFICATION"
    if ipo["applicable"] and ipo["status"] == "OBSERVATION_ONLY":
        action = "CONTINUE_OBSERVATION"
    elif context_confidence < 45:
        action = "COLLECT_MORE_EVIDENCE"
    report = {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "paper_trade_mode": PAPER_TRADE_MODE,
        "live_trading_enabled": LIVE_TRADING_ENABLED,
        "broker_execution_enabled": BROKER_EXECUTION_ENABLED,
        "symbol": request.symbol.upper().strip(),
        "as_of_date": request.as_of_date,
        "lifecycle_stage": lifecycle,
        "archetypes": archetypes,
        "archetype_confidence": archetype_confidence,
        "ipo_intelligence": ipo,
        "historical_twins": twins,
        "market_pattern_matches": patterns,
        "context_confidence_score": context_confidence,
        "opportunity_quality_score_display_only": _clamp(request.opportunity_quality_score),
        "research_conviction_score_display_only": _clamp(request.research_conviction_score),
        "recommended_research_action": action,
        "allocation_authority": False,
        "ranking_authority": False,
        "watchlist_promotion_authority": False,
        "governance": {
            "historical_similarity_is_context_only": True,
            "company_age_neither_promotes_nor_rejects": True,
            "sector_or_archetype_creates_no_entitlement": True,
            "current_evidence_must_still_prove_opportunity": True,
            "prediction_language_prohibited": True,
        },
        "warnings": warnings,
    }
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Institutional Context & Pattern Intelligence",
        "",
        f"**Symbol:** {report['symbol']}",
        f"**Lifecycle Stage:** {report['lifecycle_stage']}",
        f"**Context Confidence:** {report['context_confidence_score']:.2f} / 100",
        f"**Research Action:** {report['recommended_research_action']}",
        "",
        "## IPO Intelligence",
        "",
        f"- Applicable: {report['ipo_intelligence']['applicable']}",
        f"- Stability Score: {report['ipo_intelligence']['score']:.2f}",
        f"- Status: {report['ipo_intelligence']['status']}",
        "",
        "## Historical Twins",
        "",
        "| Comparable Case | Similarity | Observed Outcome |",
        "|---|---:|---|",
    ]
    for item in report["historical_twins"]:
        lines.append(f"| {item['name']} | {item['similarity_score']:.2f} | {item['observed_outcome']} |")
    lines += ["", "## Market Pattern Matches", "", "| Pattern | Match |", "|---|---:|"]
    for item in report["market_pattern_matches"]:
        lines.append(f"| {item['name']} | {item['pattern_match_score']:.2f} |")
    lines += [
        "",
        "## Governance",
        "",
        "Historical similarity provides context only. It cannot promote a security, alter rankings, or allocate capital. Current fundamentals, financials, news, technicals, risk, Opportunity Quality, and Watchlist competition remain authoritative.",
    ]
    if report["warnings"]:
        lines += ["", "## Warnings", ""] + [f"- {warning}" for warning in report["warnings"]]
    return "\n".join(lines) + "\n"


def render_html(report: Mapping[str, Any]) -> str:
    markdown = render_markdown(report)
    return "<!doctype html><html><head><meta charset='utf-8'><title>Institutional Context & Pattern Intelligence</title></head><body><pre>" + escape(markdown) + "</pre></body></html>"


def write_reports(report: Mapping[str, Any], output_dir: str | Path = ".") -> dict[str, str]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": directory / "institutional_context_pattern_intelligence.json",
        "markdown": directory / "institutional_context_pattern_intelligence.md",
        "html": directory / "institutional_context_pattern_intelligence.html",
    }
    paths["json"].write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    paths["markdown"].write_text(render_markdown(report), encoding="utf-8")
    paths["html"].write_text(render_html(report), encoding="utf-8")
    return {key: str(value) for key, value in paths.items()}


def sample_report() -> dict[str, Any]:
    request = ContextRequest(
        symbol="QROB",
        as_of_date=date.today().isoformat(),
        lifecycle_stage="IPO",
        archetype_candidates=("EMERGING_DISRUPTOR", "CAPITAL_INTENSIVE_GROWTH"),
        current_features={"revenue_growth": 88, "profitability": 25, "volatility": 90, "institutional_interest": 61, "research_attention": 86},
        ipo_profile=IPOProfile(months_public=5, insider_ownership_pct=58, institutional_ownership_pct=22, liquidity_score=68, volatility_score=88, earnings_reports_available=1, financial_history_score=35),
        opportunity_quality_score=83,
        research_conviction_score=79,
        evidence_confidence=65,
    )
    cases = [HistoricalCase("CASE-OKLO", "Early Public Energy Innovator", "IPO", ("EMERGING_DISRUPTOR",), {"revenue_growth": 80, "profitability": 20, "volatility": 92, "institutional_interest": 55, "research_attention": 90}, "Elevated first-year volatility followed by evidence-dependent stabilization.", ("Observe lock-up and earnings progression.",), "Emerging Infrastructure Cycle")]
    patterns = [MarketPattern("PATTERN-AI-INFRA", "AI Infrastructure Expansion", {"revenue_growth": 85, "profitability": 45, "volatility": 70, "institutional_interest": 75, "research_attention": 90}, ("Strong winners and weak imitators separated by earnings execution.",), ("Current financial proof mattered more than theme popularity.",))]
    return build_context_report(request, cases, patterns)


if __name__ == "__main__":
    generated = sample_report()
    write_reports(generated)
    print("Generated institutional_context_pattern_intelligence.json/.md/.html")
