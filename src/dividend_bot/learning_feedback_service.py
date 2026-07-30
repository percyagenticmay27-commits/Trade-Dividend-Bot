"""Governed learning feedback for AI CIO recommendations.

This service compares prior advisory recommendations with later strategy-performance
analytics. It produces evidence-based suggestions only. It never changes policy,
weights, strategy logic, allocation requests, or execution state.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "learning_feedback_service"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
AUTOMATIC_POLICY_CHANGES_ENABLED = False
AUTOMATIC_WEIGHT_CHANGES_ENABLED = False


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_object(path: str | Path, label: str) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"missing required {label}: {source}")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"invalid {label}: root must be an object")
    return value


def _rows(document: Mapping[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        value = document.get(key)
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class StrategyFeedback:
    strategy_id: str
    recommended_weight_pct: float
    performance_score: float
    classification: str
    sample_size: int
    outcome: str
    suggested_action: str
    confidence: str
    rationale: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["rationale"] = list(self.rationale)
        return result


@dataclass(frozen=True)
class LearningFeedbackReport:
    generated_at_utc: str
    feedback: tuple[StrategyFeedback, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        counts = {name: sum(item.outcome == name for item in self.feedback) for name in ("OUTPERFORMED", "MET_EXPECTATIONS", "UNDERPERFORMED", "INSUFFICIENT_EVIDENCE")}
        return {
            "module_name": MODULE_NAME,
            "module_version": MODULE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": self.generated_at_utc,
            "paper_trade_mode": True,
            "live_trading_enabled": False,
            "broker_execution_enabled": False,
            "automatic_policy_changes_enabled": False,
            "automatic_weight_changes_enabled": False,
            "summary": {"strategy_count": len(self.feedback), **counts},
            "feedback": [item.to_dict() for item in self.feedback],
            "warnings": list(self.warnings),
            "governance": {
                "advisory_only": True,
                "human_review_required": True,
                "investor_approval_required": True,
                "automatic_application_allowed": False,
            },
        }


def build_learning_feedback(
    recommendation: Mapping[str, Any],
    performance_analytics: Mapping[str, Any],
    *,
    min_sample_size: int = 20,
    generated_at_utc: Optional[str] = None,
) -> LearningFeedbackReport:
    recommendations = _rows(recommendation, "recommendations", "strategy_recommendations", "allocations")
    analytics = _rows(performance_analytics, "strategies", "performance", "analytics")
    performance_by_id = {str(item.get("strategy_id") or "").strip(): item for item in analytics if str(item.get("strategy_id") or "").strip()}
    warnings: list[str] = []
    feedback: list[StrategyFeedback] = []

    if not recommendations:
        warnings.append("no prior strategy recommendations were available")

    for rec in recommendations:
        strategy_id = str(rec.get("strategy_id") or "").strip()
        if not strategy_id:
            continue
        weight = _number(rec.get("recommended_weight_pct", rec.get("weight_pct", rec.get("percentage", 0.0))))
        perf = performance_by_id.get(strategy_id)
        if perf is None:
            feedback.append(StrategyFeedback(strategy_id, weight, 0.0, "UNKNOWN", 0, "INSUFFICIENT_EVIDENCE", "NO_CHANGE", "LOW", ("no matching performance record",)))
            continue
        score = _number(perf.get("performance_score"))
        classification = str(perf.get("classification") or "UNKNOWN").upper()
        sample_size = int(_number(perf.get("sample_size", perf.get("trade_count", 0))))
        rationale: list[str] = [f"performance classification is {classification}", f"performance score is {score:.2f}", f"sample size is {sample_size}"]
        if sample_size < min_sample_size:
            outcome, action, confidence = "INSUFFICIENT_EVIDENCE", "NO_CHANGE", "LOW"
            rationale.append(f"sample size is below minimum {min_sample_size}")
        elif classification == "STRONG" or score >= 80:
            outcome, action, confidence = "OUTPERFORMED", "CONSIDER_MODEST_INCREASE", "HIGH"
        elif classification == "STABLE" or score >= 60:
            outcome, action, confidence = "MET_EXPECTATIONS", "MAINTAIN", "MEDIUM"
        else:
            outcome, action, confidence = "UNDERPERFORMED", "CONSIDER_MODEST_DECREASE", "HIGH" if sample_size >= min_sample_size * 2 else "MEDIUM"
        feedback.append(StrategyFeedback(strategy_id, round(weight, 2), round(score, 2), classification, sample_size, outcome, action, confidence, tuple(rationale)))

    return LearningFeedbackReport(generated_at_utc or _now_utc(), tuple(sorted(feedback, key=lambda item: item.strategy_id)), tuple(sorted(set(warnings))))


def build_learning_feedback_from_files(
    recommendation_path: str | Path,
    performance_analytics_path: str | Path,
    *,
    min_sample_size: int = 20,
    generated_at_utc: Optional[str] = None,
) -> LearningFeedbackReport:
    return build_learning_feedback(
        _read_object(recommendation_path, "AI CIO recommendation"),
        _read_object(performance_analytics_path, "performance analytics"),
        min_sample_size=min_sample_size,
        generated_at_utc=generated_at_utc,
    )


def render_learning_feedback_markdown(report: LearningFeedbackReport) -> str:
    data = report.to_dict()
    lines = [
        "# AI CIO Learning and Feedback",
        "",
        f"- Generated: {report.generated_at_utc}",
        f"- Strategies reviewed: {data['summary']['strategy_count']}",
        "- Mode: Advisory, paper-only",
        "",
        "| Strategy | Prior Weight | Score | Classification | Outcome | Suggestion | Confidence |",
        "|---|---:|---:|---|---|---|---|",
    ]
    for item in report.feedback:
        lines.append(f"| {item.strategy_id} | {item.recommended_weight_pct:.2f}% | {item.performance_score:.2f} | {item.classification} | {item.outcome} | {item.suggested_action} | {item.confidence} |")
    if report.warnings:
        lines.extend(["", "## Warnings", "", *[f"- {warning}" for warning in report.warnings]])
    lines.extend(["", "## Governance", "", "Suggestions require human governance and investor review. No weight or policy is changed automatically.", ""])
    return "\n".join(lines)


def write_learning_feedback(report: LearningFeedbackReport, output_dir: str | Path = "results") -> dict[str, str]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "learning_feedback.json"
    markdown_path = directory / "learning_feedback.md"
    json_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_learning_feedback_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def build_and_write_learning_feedback(
    recommendation_path: str | Path,
    performance_analytics_path: str | Path,
    output_dir: str | Path = "results",
    *,
    min_sample_size: int = 20,
    generated_at_utc: Optional[str] = None,
) -> dict[str, str]:
    report = build_learning_feedback_from_files(recommendation_path, performance_analytics_path, min_sample_size=min_sample_size, generated_at_utc=generated_at_utc)
    return write_learning_feedback(report, output_dir)
