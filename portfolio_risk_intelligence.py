"""Portfolio Risk Intelligence Engine for the Trade Dividend Bot AI CIO.

Evaluates portfolio-level structural, concentration, correlation, event, income,
leverage, reserve, decision, and opportunity-diversity risks. This module is
paper-only and reporting-only. It never places orders or communicates with a broker.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "portfolio_risk_intelligence"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_OUTPUT_FILES = {
    "json": "portfolio_risk_intelligence.json",
    "markdown": "portfolio_risk_intelligence.md",
    "html": "portfolio_risk_intelligence.html",
}

RISK_LABELS = (
    (80.0, "HIGH"),
    (60.0, "ELEVATED"),
    (40.0, "MODERATE"),
    (20.0, "LOW"),
    (0.0, "VERY_LOW"),
)

DETAILS = {
    "overall_portfolio_risk": {
        "label": "Overall Portfolio Risk",
        "definition": "A combined view of structural, concentration, event, leverage, income, reserve, decision, and opportunity-diversity risk.",
        "calculation": "Weighted average of the portfolio risk category scores.",
        "why_it_matters": "It summarizes whether several manageable risks are combining into a more serious portfolio-level condition.",
    },
    "underlying_exposure_risk": {
        "label": "Underlying Exposure Risk",
        "definition": "Measures hidden concentration in the same underlying company through multiple stocks, funds, or pairs.",
        "calculation": "Uses each allocation weight multiplied by its stated underlying-exposure fractions, then compares the largest total exposure with concentration thresholds.",
        "why_it_matters": "Different securities can still depend on the same company and may decline together.",
    },
    "sector_context_risk": {
        "label": "Sector Context Risk",
        "definition": "Shows how much portfolio capital is associated with each sector.",
        "calculation": "Adds allocation percentages by sector context and evaluates the largest concentration.",
        "why_it_matters": "It makes sector dependence visible without creating sector quotas or forcing diversification into weaker opportunities.",
    },
    "correlation_risk": {
        "label": "Correlation Risk",
        "definition": "Measures whether apparently different allocations are expected to move together.",
        "calculation": "Uses supplied pairwise correlation observations weighted by the smaller allocation weight in each pair.",
        "why_it_matters": "High correlation can reduce the practical benefit of owning multiple securities.",
    },
    "earnings_event_risk": {
        "label": "Earnings Event Risk",
        "definition": "Measures the portfolio capital exposed to near-term earnings events.",
        "calculation": "Adds allocation percentages linked to earnings events inside the configured review window, with greater weight for nearer events.",
        "why_it_matters": "Several earnings events close together can create concentrated gap and volatility risk.",
    },
    "income_concentration_risk": {
        "label": "Income Concentration Risk",
        "definition": "Measures dependence on a small number of allocations for portfolio income.",
        "calculation": "Compares the largest projected income contribution with total projected portfolio income.",
        "why_it_matters": "A portfolio can look diversified by value while most income still depends on one source.",
    },
    "leverage_risk": {
        "label": "Leverage Risk",
        "definition": "Measures direct and effective portfolio exposure created by leveraged allocations.",
        "calculation": "Combines leveraged allocation weight, stated leverage multipliers, and inverse exposure where supplied.",
        "why_it_matters": "Leverage can magnify both gains and losses and may increase path dependency and volatility drag.",
    },
    "sgov_reserve_risk": {
        "label": "SGOV Reserve Risk",
        "definition": "Evaluates whether protected or reserve capital is materially below or above the configured operating range.",
        "calculation": "Compares SGOV allocation with configurable minimum and maximum reserve percentages.",
        "why_it_matters": "Too little reserve may reduce flexibility; too much may create opportunity cost. Reserve levels are context, not forced targets.",
    },
    "decision_risk": {
        "label": "Decision Risk",
        "definition": "Measures whether recent AI CIO behavior appears stable, evidence-supported, and free from excessive reversals or overrides.",
        "calculation": "Combines Decision Stability, Evidence Confidence, replacement frequency, reversal frequency, and override frequency.",
        "why_it_matters": "A healthy portfolio process should not create avoidable churn or repeatedly reverse low-confidence decisions.",
    },
    "opportunity_diversity_risk": {
        "label": "Opportunity Diversity Risk",
        "definition": "Shows whether portfolio capital depends heavily on one opportunity style such as Growth, Income, Balanced, Defensive, or Opportunistic.",
        "calculation": "Adds allocation percentages by opportunity style and evaluates the largest share.",
        "why_it_matters": "This reveals style dependence without imposing arbitrary allocation quotas.",
    },
    "risk_momentum": {
        "label": "Risk Momentum",
        "definition": "Shows whether overall portfolio risk is improving, stable, or deteriorating.",
        "calculation": "Compares the current Overall Portfolio Risk score with recent prior scores.",
        "why_it_matters": "Direction can matter as much as the current level because a moderate but rapidly rising risk profile may deserve closer review.",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _clamp(value: Any) -> float:
    return round(max(0.0, min(100.0, _number(value))), 4)


def _risk_label(score: float) -> str:
    value = _clamp(score)
    for minimum, label in RISK_LABELS:
        if value >= minimum:
            return label
    return "VERY_LOW"


def _health_grade(score: float) -> str:
    risk = _clamp(score)
    if risk < 20:
        return "A"
    if risk < 40:
        return "B"
    if risk < 60:
        return "C"
    if risk < 80:
        return "D"
    return "F"


def _concentration_score(share: float, moderate: float = 35.0, high: float = 55.0) -> float:
    share = max(0.0, _number(share))
    if share <= 15.0:
        return _clamp(share)
    if share < moderate:
        return _clamp(15.0 + (share - 15.0) * 1.25)
    if share < high:
        return _clamp(40.0 + (share - moderate) * 2.0)
    return _clamp(80.0 + (share - high) * 1.0)


def _normalize_allocations(allocations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(allocations or []):
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("allocation_id") or item.get("name") or item.get("strategy") or f"ALLOCATION_{index + 1}").strip()
        weight = max(0.0, _number(item.get("allocation_percent", item.get("weight_percent", 0.0))))
        underlying = item.get("underlying_exposures") or {}
        if not isinstance(underlying, Mapping):
            underlying = {}
        normalized.append({
            "allocation_id": name.upper(),
            "allocation_percent": round(weight, 4),
            "sector_context": str(item.get("sector_context") or item.get("sector") or "UNKNOWN").upper(),
            "opportunity_style": str(item.get("opportunity_style") or item.get("style") or "UNKNOWN").upper(),
            "projected_income": max(0.0, _number(item.get("projected_income", item.get("annual_income", 0.0)))),
            "leverage_multiplier": max(0.0, _number(item.get("leverage_multiplier", 1.0), 1.0)),
            "inverse_exposure": bool(item.get("inverse_exposure", False)),
            "underlying_exposures": {str(k).upper(): max(0.0, _number(v)) for k, v in underlying.items()},
            "earnings_days": item.get("earnings_days"),
            "is_sgov": bool(item.get("is_sgov", False) or name.upper() == "SGOV"),
        })
    return normalized


def _underlying_risk(allocations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    exposures: dict[str, float] = defaultdict(float)
    for item in allocations:
        weight = _number(item.get("allocation_percent"))
        underlying = item.get("underlying_exposures") or {}
        if not underlying:
            exposures[item["allocation_id"]] += weight
            continue
        total_fraction = sum(max(0.0, _number(v)) for v in underlying.values())
        scale = 1.0 if total_fraction <= 1.0001 else 1.0 / total_fraction
        for symbol, fraction in underlying.items():
            exposures[str(symbol).upper()] += weight * max(0.0, _number(fraction)) * scale
    ordered = sorted(((k, round(v, 4)) for k, v in exposures.items()), key=lambda x: x[1], reverse=True)
    largest = ordered[0][1] if ordered else 0.0
    return {"score": _concentration_score(largest, 30.0, 45.0), "largest_exposure_percent": largest, "exposures": ordered}


def _group_risk(allocations: Sequence[Mapping[str, Any]], field: str) -> dict[str, Any]:
    groups: dict[str, float] = defaultdict(float)
    for item in allocations:
        groups[str(item.get(field) or "UNKNOWN").upper()] += _number(item.get("allocation_percent"))
    ordered = sorted(((k, round(v, 4)) for k, v in groups.items()), key=lambda x: x[1], reverse=True)
    largest = ordered[0][1] if ordered else 0.0
    return {"score": _concentration_score(largest, 45.0, 70.0), "largest_share_percent": largest, "distribution": ordered}


def _correlation_risk(allocations: Sequence[Mapping[str, Any]], correlations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    weights = {item["allocation_id"]: _number(item["allocation_percent"]) for item in allocations}
    weighted_sum = 0.0
    total_weight = 0.0
    observations: list[dict[str, Any]] = []
    for row in correlations or []:
        if not isinstance(row, Mapping):
            continue
        left = str(row.get("left") or row.get("allocation_a") or "").upper()
        right = str(row.get("right") or row.get("allocation_b") or "").upper()
        corr = max(-1.0, min(1.0, _number(row.get("correlation"))))
        if not left or not right or left not in weights or right not in weights:
            continue
        pair_weight = min(weights[left], weights[right])
        weighted_sum += max(0.0, corr) * pair_weight
        total_weight += pair_weight
        observations.append({"left": left, "right": right, "correlation": round(corr, 4)})
    average = weighted_sum / total_weight if total_weight else 0.0
    score = _clamp(max(0.0, (average - 0.35) / 0.65) * 100.0)
    return {"score": score, "weighted_average_correlation": round(average, 4), "observations": observations}


def _earnings_risk(allocations: Sequence[Mapping[str, Any]], window_days: int) -> dict[str, Any]:
    exposed = 0.0
    events: list[dict[str, Any]] = []
    for item in allocations:
        raw_days = item.get("earnings_days")
        if raw_days is None:
            continue
        days = int(_number(raw_days, 9999))
        if 0 <= days <= window_days:
            weight = _number(item.get("allocation_percent"))
            proximity = 1.0 - (days / max(window_days, 1)) * 0.5
            exposed += weight * proximity
            events.append({"allocation_id": item["allocation_id"], "days": days, "allocation_percent": weight})
    return {"score": _clamp(exposed * 2.0), "weighted_exposure_percent": round(exposed, 4), "events": sorted(events, key=lambda x: x["days"])}


def _income_risk(allocations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    incomes = [(item["allocation_id"], _number(item.get("projected_income"))) for item in allocations]
    total = sum(value for _, value in incomes)
    ordered = sorted(incomes, key=lambda x: x[1], reverse=True)
    largest_share = (ordered[0][1] / total * 100.0) if total > 0 and ordered else 0.0
    return {"score": _concentration_score(largest_share, 40.0, 60.0), "largest_income_share_percent": round(largest_share, 4), "income_sources": ordered}


def _leverage_risk(allocations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    leveraged_weight = 0.0
    effective_exposure = 0.0
    inverse_weight = 0.0
    details: list[dict[str, Any]] = []
    for item in allocations:
        weight = _number(item.get("allocation_percent"))
        multiplier = max(0.0, _number(item.get("leverage_multiplier"), 1.0))
        if multiplier > 1.0 or item.get("inverse_exposure"):
            leveraged_weight += weight
            effective_exposure += weight * multiplier
            if item.get("inverse_exposure"):
                inverse_weight += weight
            details.append({"allocation_id": item["allocation_id"], "allocation_percent": weight, "leverage_multiplier": multiplier, "inverse_exposure": bool(item.get("inverse_exposure"))})
    score = _clamp(leveraged_weight * 1.2 + max(0.0, effective_exposure - leveraged_weight) * 0.8 + inverse_weight * 0.5)
    return {"score": score, "leveraged_allocation_percent": round(leveraged_weight, 4), "effective_leveraged_exposure_percent": round(effective_exposure, 4), "inverse_allocation_percent": round(inverse_weight, 4), "allocations": details}


def _reserve_risk(allocations: Sequence[Mapping[str, Any]], minimum: float, maximum: float) -> dict[str, Any]:
    reserve = sum(_number(item.get("allocation_percent")) for item in allocations if item.get("is_sgov"))
    if reserve < minimum:
        score = _clamp((minimum - reserve) * 5.0)
        status = "BELOW_PREFERRED_RANGE"
    elif reserve > maximum:
        score = _clamp((reserve - maximum) * 3.0)
        status = "ABOVE_PREFERRED_RANGE"
    else:
        score = 0.0
        status = "WITHIN_PREFERRED_RANGE"
    return {"score": score, "sgov_allocation_percent": round(reserve, 4), "preferred_minimum_percent": minimum, "preferred_maximum_percent": maximum, "status": status}


def _decision_risk(metrics: Mapping[str, Any]) -> dict[str, Any]:
    stability = _clamp(metrics.get("average_decision_stability", 100.0))
    confidence = _clamp(metrics.get("average_evidence_confidence", 100.0))
    replacement_rate = max(0.0, _number(metrics.get("replacement_rate_percent", 0.0)))
    reversal_rate = max(0.0, _number(metrics.get("reversal_rate_percent", 0.0)))
    override_rate = max(0.0, _number(metrics.get("override_rate_percent", 0.0)))
    score = _clamp((100.0 - stability) * 0.35 + (100.0 - confidence) * 0.30 + replacement_rate * 0.15 + reversal_rate * 0.15 + override_rate * 0.05)
    return {"score": score, "average_decision_stability": stability, "average_evidence_confidence": confidence, "replacement_rate_percent": replacement_rate, "reversal_rate_percent": reversal_rate, "override_rate_percent": override_rate}


def _risk_momentum(current_score: float, history: Sequence[Any]) -> dict[str, Any]:
    values = [_clamp(item.get("overall_risk_score") if isinstance(item, Mapping) else item) for item in history or []]
    if not values:
        return {"direction": "STABLE", "change_points": 0.0, "history": []}
    baseline = sum(values[-3:]) / min(3, len(values))
    change = round(current_score - baseline, 4)
    if change >= 5.0:
        direction = "DETERIORATING"
    elif change <= -5.0:
        direction = "IMPROVING"
    else:
        direction = "STABLE"
    return {"direction": direction, "change_points": change, "history": values}


def build_portfolio_risk_intelligence(
    *,
    allocations: Sequence[Mapping[str, Any]],
    correlations: Optional[Sequence[Mapping[str, Any]]] = None,
    decision_metrics: Optional[Mapping[str, Any]] = None,
    prior_risk_history: Optional[Sequence[Any]] = None,
    earnings_window_days: int = 7,
    preferred_sgov_minimum_percent: float = 5.0,
    preferred_sgov_maximum_percent: float = 20.0,
) -> dict[str, Any]:
    """Build the paper-only Portfolio Risk Intelligence report."""
    if not isinstance(allocations, Sequence) or isinstance(allocations, (str, bytes)):
        raise ValueError("allocations must be a sequence")

    normalized = _normalize_allocations(allocations)
    warnings: list[str] = []
    if not normalized:
        warnings.append("No allocation records were supplied; risk scores default to zero.")

    underlying = _underlying_risk(normalized)
    sector = _group_risk(normalized, "sector_context")
    correlation = _correlation_risk(normalized, correlations or [])
    earnings = _earnings_risk(normalized, max(1, int(earnings_window_days)))
    income = _income_risk(normalized)
    leverage = _leverage_risk(normalized)
    reserve = _reserve_risk(normalized, max(0.0, _number(preferred_sgov_minimum_percent)), max(0.0, _number(preferred_sgov_maximum_percent)))
    decision = _decision_risk(decision_metrics or {})
    diversity = _group_risk(normalized, "opportunity_style")

    categories = {
        "underlying_exposure_risk": underlying,
        "sector_context_risk": sector,
        "correlation_risk": correlation,
        "earnings_event_risk": earnings,
        "income_concentration_risk": income,
        "leverage_risk": leverage,
        "sgov_reserve_risk": reserve,
        "decision_risk": decision,
        "opportunity_diversity_risk": diversity,
    }
    weights = {
        "underlying_exposure_risk": 0.18,
        "sector_context_risk": 0.08,
        "correlation_risk": 0.14,
        "earnings_event_risk": 0.12,
        "income_concentration_risk": 0.10,
        "leverage_risk": 0.14,
        "sgov_reserve_risk": 0.06,
        "decision_risk": 0.12,
        "opportunity_diversity_risk": 0.06,
    }
    overall = round(sum(_number(categories[name]["score"]) * weight for name, weight in weights.items()), 4)
    momentum = _risk_momentum(overall, prior_risk_history or [])

    highest = sorted(((name, _number(data["score"])) for name, data in categories.items()), key=lambda item: item[1], reverse=True)
    top_name, top_score = highest[0] if highest else ("none", 0.0)
    top_label = DETAILS.get(top_name, {}).get("label", top_name.replace("_", " ").title())

    commentary = (
        f"Overall portfolio risk is {_risk_label(overall).replace('_', ' ').title()} with a score of {overall:.2f} out of 100. "
        f"The largest current risk contribution is {top_label} at {top_score:.2f} out of 100. "
        "Sector exposure is treated as context only and does not create forced diversification or capital entitlements. "
        f"Risk Momentum is {momentum['direction'].replace('_', ' ').title()}."
    )

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
        "allocation_count": len(normalized),
        "total_allocation_percent": round(sum(_number(item["allocation_percent"]) for item in normalized), 4),
        "overall_portfolio_risk_score": overall,
        "overall_portfolio_risk_label": _risk_label(overall),
        "portfolio_health_grade": _health_grade(overall),
        "risk_momentum": momentum,
        "risk_categories": categories,
        "risk_category_weights": weights,
        "details": DETAILS,
        "ai_cio_commentary": commentary,
        "warnings": warnings,
        "errors": [],
    }


def format_portfolio_risk_markdown(report: Mapping[str, Any]) -> str:
    categories = report.get("risk_categories") or {}
    lines = [
        "# Portfolio Risk Intelligence",
        "",
        "## Executive Summary",
        "",
        f"- **Overall Portfolio Risk:** {str(report.get('overall_portfolio_risk_label', 'UNKNOWN')).replace('_', ' ').title()} ({_number(report.get('overall_portfolio_risk_score')):.2f} / 100)",
        f"- **Portfolio Health:** {report.get('portfolio_health_grade', 'Unknown')}",
        f"- **Risk Momentum:** {str((report.get('risk_momentum') or {}).get('direction', 'STABLE')).replace('_', ' ').title()}",
        "",
        "## Risk Categories",
        "",
        "| Risk Category | Score | Status | More... |",
        "|---|---:|---|---|",
    ]
    for key, data in categories.items():
        label = DETAILS.get(key, {}).get("label", key.replace("_", " ").title())
        score = _number(data.get("score"))
        lines.append(f"| {label} | {score:.2f} / 100 | {_risk_label(score).replace('_', ' ').title()} | [More...](#{key.replace('_', '-')}) |")

    lines.extend(["", "## AI CIO Commentary", "", str(report.get("ai_cio_commentary", "No commentary available.")), ""])

    for key, detail in DETAILS.items():
        lines.extend([
            f"## {detail['label']}",
            "",
            f"**What it means:** {detail['definition']}",
            "",
            f"**How it is calculated:** {detail['calculation']}",
            "",
            f"**Why it matters:** {detail['why_it_matters']}",
            "",
        ])

    lines.extend([
        "## Paper-Only Safety",
        "",
        "This report identifies and explains portfolio risk. It does not place orders, force sales, impose sector quotas, or communicate with a brokerage.",
        "",
    ])
    return "\n".join(lines)


def format_portfolio_risk_html(report: Mapping[str, Any]) -> str:
    import html

    markdown = format_portfolio_risk_markdown(report)
    escaped = html.escape(markdown)
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Portfolio Risk Intelligence</title>"
        "<style>body{font-family:Arial,sans-serif;max-width:1200px;margin:0 auto;padding:32px;background:#f5f7fb;color:#172033}"
        "pre{white-space:pre-wrap;background:white;padding:28px;border-radius:14px;box-shadow:0 4px 18px rgba(0,0,0,.08);line-height:1.5}</style>"
        "</head><body><pre>" + escaped + "</pre></body></html>"
    )


def write_portfolio_risk_intelligence(
    payload: Mapping[str, Any],
    root_path: str = ".",
    output_files: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    report = build_portfolio_risk_intelligence(**dict(payload))
    root = Path(root_path)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    (root / files["json"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_portfolio_risk_markdown(report), encoding="utf-8")
    (root / files["html"]).write_text(format_portfolio_risk_html(report), encoding="utf-8")
    return report


def build_and_write_portfolio_risk_intelligence(
    payload: Mapping[str, Any],
    root_path: str = ".",
    output_files: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    return write_portfolio_risk_intelligence(payload, root_path, output_files)


if __name__ == "__main__":
    sample = {
        "allocations": [
            {"allocation_id": "AMDW + PLTU", "allocation_percent": 30, "sector_context": "Technology", "opportunity_style": "Growth", "projected_income": 1200, "leverage_multiplier": 1.5, "underlying_exposures": {"AMD": 0.5, "PLTR": 0.5}, "earnings_days": 4},
            {"allocation_id": "QQQI + TQQQ", "allocation_percent": 25, "sector_context": "Technology", "opportunity_style": "Balanced", "projected_income": 1800, "leverage_multiplier": 2.0, "underlying_exposures": {"NVDA": 0.25, "MSFT": 0.20, "AAPL": 0.15, "OTHER": 0.40}},
            {"allocation_id": "SCHD", "allocation_percent": 20, "sector_context": "Multi-Sector", "opportunity_style": "Income", "projected_income": 950, "underlying_exposures": {"OTHER": 1.0}},
            {"allocation_id": "SGOV", "allocation_percent": 10, "sector_context": "Reserve", "opportunity_style": "Defensive", "projected_income": 210, "is_sgov": True},
        ],
        "correlations": [
            {"left": "AMDW + PLTU", "right": "QQQI + TQQQ", "correlation": 0.86},
            {"left": "AMDW + PLTU", "right": "SCHD", "correlation": 0.42},
        ],
        "decision_metrics": {
            "average_decision_stability": 84,
            "average_evidence_confidence": 93,
            "replacement_rate_percent": 8,
            "reversal_rate_percent": 2,
            "override_rate_percent": 1,
        },
        "prior_risk_history": [31.0, 33.0, 34.0],
    }
    result = write_portfolio_risk_intelligence(sample)
    print(f"Overall Portfolio Risk: {result['overall_portfolio_risk_score']:.2f} / 100")
