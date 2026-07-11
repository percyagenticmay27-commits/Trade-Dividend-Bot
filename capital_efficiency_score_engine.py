"""Unified Capital Efficiency Score Engine for Trade-Dividend-Bot Version 2.

Scores single instruments, pairs, and multi-asset strategies under the permanent
MAXIMUM_TOTAL_WEALTH objective. The engine is deterministic, paper-only, and
contains no brokerage or order-routing behavior.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

MODULE_NAME = "capital_efficiency_score_engine"
MODULE_VERSION = "2.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True
DEFAULT_OPTIMIZATION_PROFILE = "MAXIMUM_TOTAL_WEALTH"

DEFAULT_OUTPUT_FILES = {
    "json": "capital_efficiency_scores.json",
    "markdown": "capital_efficiency_scores.md",
}

SUPPORTED_CANDIDATE_TYPES = {
    "SINGLE_INSTRUMENT",
    "PAIR",
    "PORTFOLIO_STRATEGY",
    "DEFENSIVE_ALLOCATION",
}

DEFAULT_WEIGHTS = {
    "expected_capital_appreciation": 0.30,
    "expected_income": 0.20,
    "reinvestment_potential": 0.08,
    "momentum_trend_quality": 0.10,
    "fundamental_or_fund_quality": 0.08,
    "sector_leadership": 0.07,
    "market_regime_support": 0.05,
    "distribution_sustainability": 0.05,
    "evidence_confidence": 0.07,
}

DEFAULT_PENALTY_WEIGHTS = {
    "volatility_risk": 0.08,
    "drawdown_risk": 0.10,
    "downside_risk": 0.07,
    "concentration_risk": 0.06,
    "correlation_risk": 0.04,
    "turnover_tax_friction": 0.05,
    "missing_evidence": 0.08,
}

CONCENTRATED_TYPES = {"SINGLE_INSTRUMENT", "PAIR"}
CONCENTRATED_CONFIRMATION_MINIMUM = 65.0
MINIMUM_REPLACEMENT_IMPROVEMENT = 5.0

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "reporting_only is enforced as True",
    "all outputs are paper recommendations",
    "read-only market evidence may be consumed",
]


@dataclass(frozen=True)
class CapitalEfficiencyCandidateResult:
    candidate_id: str
    candidate_type: str
    symbols: list[str]
    capital_efficiency_score: float
    gross_total_wealth_score: float
    total_penalty: float
    growth_contribution: float
    income_contribution: float
    quality_contribution: float
    regime_contribution: float
    confidence_contribution: float
    penalty_breakdown: dict[str, float]
    component_scores: dict[str, float]
    evidence_confidence: float
    missing_evidence_count: int
    concentrated_confirmation_passed: bool
    qualifying: bool
    rank: int
    recommendation: str
    reasons: list[str]
    risk_flags: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class CapitalEfficiencyScoreReport:
    module_name: str
    module_version: str
    schema_version: str
    generated_by: str
    generated_at_utc: str
    paper_trade_mode: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    reporting_only: bool
    optimization_profile: str
    candidate_count: int
    qualifying_candidate_count: int
    top_candidate_id: Optional[str]
    minimum_replacement_improvement: float
    results: list[dict[str, Any]]
    warnings: list[str]
    errors: list[str]
    safety_guarantees: list[str]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_score(value: Any) -> float:
    return round(max(0.0, min(100.0, _number(value))), 4)


def _normalize_symbols(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in values:
        if isinstance(item, str) and item.strip():
            symbol = item.strip().upper()
            if symbol not in result:
                result.append(symbol)
    return result


def _validate_weights(weights: Mapping[str, float], label: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for key, value in weights.items():
        numeric = _number(value, -1.0)
        if numeric < 0.0:
            raise ValueError(f"{label} weights must be non-negative")
        result[str(key)] = numeric
    return result


def _weighted_sum(scores: Mapping[str, float], weights: Mapping[str, float]) -> float:
    return sum(_clamp_score(scores.get(name, 0.0)) * weight for name, weight in weights.items())


def _candidate_id(candidate: Mapping[str, Any], symbols: list[str], index: int) -> str:
    raw = candidate.get("candidate_id") or candidate.get("strategy_id") or candidate.get("name")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if symbols:
        return "+".join(symbols)
    return f"CANDIDATE_{index + 1}"


def _component_scores(candidate: Mapping[str, Any]) -> dict[str, float]:
    aliases = {
        "expected_capital_appreciation": ("expected_capital_appreciation", "growth_score", "capital_appreciation_score"),
        "expected_income": ("expected_income", "income_score", "distribution_income_score"),
        "reinvestment_potential": ("reinvestment_potential", "reinvestment_score"),
        "momentum_trend_quality": ("momentum_trend_quality", "momentum_score", "trend_score"),
        "fundamental_or_fund_quality": ("fundamental_or_fund_quality", "quality_score", "fundamental_score"),
        "sector_leadership": ("sector_leadership", "sector_strength_score"),
        "market_regime_support": ("market_regime_support", "regime_support_score"),
        "distribution_sustainability": ("distribution_sustainability", "distribution_safety_score"),
        "evidence_confidence": ("evidence_confidence", "confidence_score", "confidence"),
    }
    result: dict[str, float] = {}
    for canonical, names in aliases.items():
        value = 0.0
        for name in names:
            if name in candidate:
                value = candidate[name]
                break
        if canonical == "evidence_confidence" and 0.0 <= _number(value) <= 1.0:
            value = _number(value) * 100.0
        result[canonical] = _clamp_score(value)
    return result


def _penalty_scores(candidate: Mapping[str, Any], missing_count: int) -> dict[str, float]:
    aliases = {
        "volatility_risk": ("volatility_risk", "volatility_score"),
        "drawdown_risk": ("drawdown_risk", "maximum_drawdown_risk", "max_drawdown_risk"),
        "downside_risk": ("downside_risk",),
        "concentration_risk": ("concentration_risk",),
        "correlation_risk": ("correlation_risk",),
        "turnover_tax_friction": ("turnover_tax_friction", "turnover_friction", "tax_friction"),
    }
    result: dict[str, float] = {}
    for canonical, names in aliases.items():
        value = 0.0
        for name in names:
            if name in candidate:
                value = candidate[name]
                break
        result[canonical] = _clamp_score(value)
    result["missing_evidence"] = _clamp_score(min(100.0, missing_count * 20.0))
    return result


def _missing_evidence_count(candidate: Mapping[str, Any], scores: Mapping[str, float]) -> int:
    explicit = candidate.get("missing_evidence")
    if isinstance(explicit, list):
        return len(explicit)
    required = [
        "expected_capital_appreciation",
        "expected_income",
        "momentum_trend_quality",
        "fundamental_or_fund_quality",
        "sector_leadership",
        "market_regime_support",
        "evidence_confidence",
    ]
    return sum(1 for name in required if scores.get(name, 0.0) <= 0.0)


def _concentrated_confirmation(candidate_type: str, scores: Mapping[str, float], candidate: Mapping[str, Any]) -> bool:
    if candidate_type not in CONCENTRATED_TYPES:
        return True
    confirmation_values = [
        scores["momentum_trend_quality"],
        scores["fundamental_or_fund_quality"],
        scores["sector_leadership"],
        scores["market_regime_support"],
        scores["evidence_confidence"],
        _clamp_score(100.0 - _number(candidate.get("concentration_risk", 0.0))),
    ]
    return min(confirmation_values) >= CONCENTRATED_CONFIRMATION_MINIMUM


def _recommendation(score: float, qualifying: bool) -> str:
    if not qualifying:
        return "WATCHLIST"
    if score >= 85.0:
        return "STRONG_CANDIDATE"
    if score >= 70.0:
        return "QUALIFIED_CANDIDATE"
    if score >= 55.0:
        return "CONDITIONAL_CANDIDATE"
    return "WATCHLIST"


def score_capital_efficiency_candidate(
    candidate: Mapping[str, Any],
    index: int = 0,
    weights: Optional[Mapping[str, float]] = None,
    penalty_weights: Optional[Mapping[str, float]] = None,
) -> dict[str, Any]:
    if not isinstance(candidate, Mapping):
        raise ValueError("candidate must be a mapping")

    candidate_type = str(candidate.get("candidate_type", "SINGLE_INSTRUMENT")).strip().upper()
    if candidate_type not in SUPPORTED_CANDIDATE_TYPES:
        raise ValueError(f"unsupported candidate_type: {candidate_type}")

    symbols = _normalize_symbols(candidate.get("symbols", candidate.get("symbol", [])))
    identifier = _candidate_id(candidate, symbols, index)
    component_weights = _validate_weights(weights or DEFAULT_WEIGHTS, "component")
    risk_weights = _validate_weights(penalty_weights or DEFAULT_PENALTY_WEIGHTS, "penalty")
    scores = _component_scores(candidate)
    missing_count = _missing_evidence_count(candidate, scores)
    penalties = _penalty_scores(candidate, missing_count)

    gross = _weighted_sum(scores, component_weights)
    total_penalty = _weighted_sum(penalties, risk_weights)
    ces = round(max(0.0, min(100.0, gross - total_penalty)), 4)

    confirmation_passed = _concentrated_confirmation(candidate_type, scores, candidate)
    qualifying = bool(candidate.get("eligible", True)) and confirmation_passed and scores["evidence_confidence"] >= 40.0

    growth_contribution = round(scores["expected_capital_appreciation"] * component_weights.get("expected_capital_appreciation", 0.0), 4)
    income_contribution = round(scores["expected_income"] * component_weights.get("expected_income", 0.0), 4)
    quality_names = {"reinvestment_potential", "momentum_trend_quality", "fundamental_or_fund_quality", "distribution_sustainability"}
    quality_contribution = round(sum(scores[name] * component_weights.get(name, 0.0) for name in quality_names), 4)
    regime_contribution = round(
        scores["sector_leadership"] * component_weights.get("sector_leadership", 0.0)
        + scores["market_regime_support"] * component_weights.get("market_regime_support", 0.0),
        4,
    )
    confidence_contribution = round(scores["evidence_confidence"] * component_weights.get("evidence_confidence", 0.0), 4)

    reasons = [
        f"Growth contribution: {growth_contribution:.2f}",
        f"Income contribution: {income_contribution:.2f}",
        f"Quality contribution: {quality_contribution:.2f}",
        f"Regime contribution: {regime_contribution:.2f}",
        f"Risk and friction penalty: {total_penalty:.2f}",
    ]
    risk_flags: list[str] = []
    warnings: list[str] = []
    if penalties["drawdown_risk"] >= 70.0:
        risk_flags.append("HIGH_DRAWDOWN_RISK")
    if penalties["concentration_risk"] >= 70.0:
        risk_flags.append("HIGH_CONCENTRATION_RISK")
    if penalties["volatility_risk"] >= 70.0:
        risk_flags.append("HIGH_VOLATILITY_RISK")
    if missing_count:
        warnings.append(f"{missing_count} required evidence component(s) were missing or zero.")
    if not confirmation_passed:
        warnings.append("Concentrated opportunity confirmation requirements were not met.")

    result = asdict(CapitalEfficiencyCandidateResult(
        identifier,
        candidate_type,
        symbols,
        ces,
        round(gross, 4),
        round(total_penalty, 4),
        growth_contribution,
        income_contribution,
        quality_contribution,
        regime_contribution,
        confidence_contribution,
        {name: round(value, 4) for name, value in penalties.items()},
        {name: round(value, 4) for name, value in scores.items()},
        scores["evidence_confidence"],
        missing_count,
        confirmation_passed,
        qualifying,
        0,
        _recommendation(ces, qualifying),
        reasons,
        risk_flags,
        warnings,
    ))
    return result


def build_capital_efficiency_score_report(
    candidates: Optional[Iterable[Mapping[str, Any]]] = None,
    weights: Optional[Mapping[str, float]] = None,
    penalty_weights: Optional[Mapping[str, float]] = None,
    optimization_profile: str = DEFAULT_OPTIMIZATION_PROFILE,
    minimum_replacement_improvement: float = MINIMUM_REPLACEMENT_IMPROVEMENT,
) -> dict[str, Any]:
    rows = list(candidates or [])
    warnings: list[str] = []
    errors: list[str] = []
    results: list[dict[str, Any]] = []

    for index, candidate in enumerate(rows):
        try:
            results.append(score_capital_efficiency_candidate(candidate, index, weights, penalty_weights))
        except (TypeError, ValueError) as exc:
            errors.append(f"Candidate {index + 1} failed: {exc}")

    results.sort(key=lambda row: (-row["qualifying"], -row["capital_efficiency_score"], row["candidate_id"]))
    for rank, row in enumerate(results, start=1):
        row["rank"] = rank

    qualifying = [row for row in results if row["qualifying"]]
    if not rows:
        warnings.append("No candidates were supplied; an empty paper-only report was generated.")
    if results and not qualifying:
        warnings.append("No candidate met the current qualification rules.")

    payload = asdict(CapitalEfficiencyScoreReport(
        MODULE_NAME,
        MODULE_VERSION,
        SCHEMA_VERSION,
        GENERATED_BY,
        _now(),
        True,
        False,
        False,
        True,
        str(optimization_profile).strip().upper() or DEFAULT_OPTIMIZATION_PROFILE,
        len(rows),
        len(qualifying),
        qualifying[0]["candidate_id"] if qualifying else None,
        round(max(0.0, _number(minimum_replacement_improvement, MINIMUM_REPLACEMENT_IMPROVEMENT)), 4),
        results,
        warnings,
        errors,
        list(SAFETY_GUARANTEES),
    ))
    validate_capital_efficiency_score_report(payload)
    return payload


def compare_replacement_candidate(
    current_score: float,
    replacement_score: float,
    sale_gate_passed: bool,
    minimum_improvement: float = MINIMUM_REPLACEMENT_IMPROVEMENT,
) -> dict[str, Any]:
    current = _clamp_score(current_score)
    replacement = _clamp_score(replacement_score)
    improvement = round(replacement - current, 4)
    threshold = max(0.0, _number(minimum_improvement, MINIMUM_REPLACEMENT_IMPROVEMENT))
    approved = bool(sale_gate_passed) and improvement >= threshold
    return {
        "current_score": current,
        "replacement_score": replacement,
        "improvement": improvement,
        "minimum_improvement": threshold,
        "sale_gate_passed": bool(sale_gate_passed),
        "replacement_approved": approved,
        "decision": "REPLACE" if approved else "HOLD_OR_REVIEW",
    }


def validate_capital_efficiency_score_report(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    required = set(CapitalEfficiencyScoreReport.__dataclass_fields__)
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    for field, expected in {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
    }.items():
        if payload[field] is not expected:
            raise ValueError(f"{field} must be {expected}")
    if not isinstance(payload["results"], list):
        raise ValueError("results must be a list")
    if payload["candidate_count"] < 0 or payload["qualifying_candidate_count"] < 0:
        raise ValueError("candidate counts must be non-negative")
    for row in payload["results"]:
        if not isinstance(row, Mapping):
            raise ValueError("each result must be a mapping")
        score = row.get("capital_efficiency_score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0.0 <= score <= 100.0:
            raise ValueError("capital_efficiency_score must be between 0 and 100")
    return True


def format_capital_efficiency_score_markdown(payload: Mapping[str, Any]) -> str:
    validate_capital_efficiency_score_report(payload)
    lines = [
        "# Capital Efficiency Score Report",
        "",
        f"- Optimization Profile: {payload['optimization_profile']}",
        f"- Candidates: {payload['candidate_count']}",
        f"- Qualifying Candidates: {payload['qualifying_candidate_count']}",
        f"- Top Candidate: {payload['top_candidate_id'] or 'None'}",
        f"- Minimum Replacement Improvement: {payload['minimum_replacement_improvement']:.2f}",
        "",
        "## Rankings",
    ]
    if not payload["results"]:
        lines.append("- None")
    for row in payload["results"]:
        lines.append(
            f"- #{row['rank']} {row['candidate_id']} [{row['candidate_type']}] — "
            f"CES {row['capital_efficiency_score']:.2f} — {row['recommendation']}"
        )
        lines.append(
            f"  - Growth {row['growth_contribution']:.2f}; Income {row['income_contribution']:.2f}; "
            f"Penalty {row['total_penalty']:.2f}; Confidence {row['evidence_confidence']:.2f}"
        )
        for warning in row["warnings"]:
            lines.append(f"  - Warning: {warning}")
    lines += ["", "## Warnings"]
    lines.extend(f"- {item}" for item in payload["warnings"]) or lines.append("- None")
    lines += ["", "## Errors"]
    lines.extend(f"- {item}" for item in payload["errors"]) or lines.append("- None")
    return "\n".join(lines) + "\n"


def write_capital_efficiency_score_report(
    candidates: Optional[Iterable[Mapping[str, Any]]] = None,
    root_path: str = ".",
    output_files: Optional[Mapping[str, str]] = None,
    **kwargs: Any,
) -> dict[str, Any]:
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    root = Path(root_path)
    root.mkdir(parents=True, exist_ok=True)
    payload = build_capital_efficiency_score_report(candidates=candidates, **kwargs)
    (root / files["json"]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_capital_efficiency_score_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    report = write_capital_efficiency_score_report()
    print(f"Capital Efficiency Score Engine: {report['qualifying_candidate_count']} qualifying candidate(s)")
