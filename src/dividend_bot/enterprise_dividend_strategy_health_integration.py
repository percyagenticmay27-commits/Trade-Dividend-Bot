"""Enterprise Dividend Strategy Health Integration.

Aggregates completed paper-only Dividend platform artifacts into a governed,
read-only strategy health assessment. This module never trades, moves capital,
or changes strategy policy.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "enterprise_dividend_strategy_health_integration"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True
ADVISORY_ONLY = True
POLICY_CHANGE_ENABLED = False

HEALTH_STATUSES = {"HEALTHY", "WATCH", "DEGRADED", "CRITICAL"}
DEFAULT_OUTPUT_FILES = {
    "json": "enterprise_dividend_strategy_health.json",
    "markdown": "enterprise_dividend_strategy_health.md",
}
DEFAULT_THRESHOLDS = {
    "healthy_min_score": 80.0,
    "watch_min_score": 65.0,
    "degraded_min_score": 45.0,
    "critical_alert_ratio": 20.0,
    "high_alert_ratio": 35.0,
    "review_completion_min": 70.0,
    "forecast_accuracy_min": 75.0,
    "evidence_completeness_min": 85.0,
    "max_position_concentration": 25.0,
    "max_sector_concentration": 40.0,
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _percent(value: Any, default: float = 0.0) -> float:
    return round(max(0.0, min(100.0, _number(value, default))), 2)


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _first(mapping: Mapping[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _source_rows(source: Optional[Mapping[str, Any]], keys: Sequence[str]) -> list[dict[str, Any]]:
    if not isinstance(source, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for key in keys:
        rows.extend(_rows(source.get(key)))
    for container_key in ("summary", "dashboard", "analytics", "portfolio_summary"):
        container = source.get(container_key)
        if isinstance(container, Mapping):
            for key in keys:
                rows.extend(_rows(container.get(key)))
    return rows


def _summary(source: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    if not isinstance(source, Mapping):
        return {}
    for key in ("summary", "investor_summary", "portfolio_summary", "analytics"):
        value = source.get(key)
        if isinstance(value, Mapping):
            return value
    return source


def _status_score(value: str) -> float:
    return {"HEALTHY": 100.0, "STABLE": 90.0, "WATCH": 65.0, "DEGRADED": 40.0, "CRITICAL": 10.0}.get(str(value).upper(), 50.0)


def _classify(score: float, thresholds: Mapping[str, float], *, force_critical: bool = False) -> str:
    if force_critical:
        return "CRITICAL"
    if score >= thresholds["healthy_min_score"]:
        return "HEALTHY"
    if score >= thresholds["watch_min_score"]:
        return "WATCH"
    if score >= thresholds["degraded_min_score"]:
        return "DEGRADED"
    return "CRITICAL"


def _metric(name: str, value: float, score: float, weight: float, status: str, source: str) -> dict[str, Any]:
    return {
        "metric": name,
        "value": round(value, 2),
        "score": _percent(score),
        "weight": round(weight, 4),
        "weighted_score": round(_percent(score) * weight, 4),
        "status": status,
        "source": source,
    }


def build_enterprise_dividend_strategy_health(
    *,
    dividend_dashboard: Optional[Mapping[str, Any]] = None,
    investor_dashboard: Optional[Mapping[str, Any]] = None,
    alerts_report: Optional[Mapping[str, Any]] = None,
    reviews_report: Optional[Mapping[str, Any]] = None,
    learning_report: Optional[Mapping[str, Any]] = None,
    cio_advisory_report: Optional[Mapping[str, Any]] = None,
    replacement_report: Optional[Mapping[str, Any]] = None,
    confidence_report: Optional[Mapping[str, Any]] = None,
    forecast_report: Optional[Mapping[str, Any]] = None,
    analytics_report: Optional[Mapping[str, Any]] = None,
    thresholds: Optional[Mapping[str, Any]] = None,
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Build a governed strategy-level health report from read-only artifacts."""
    limits = dict(DEFAULT_THRESHOLDS)
    for key, value in dict(thresholds or {}).items():
        if key in limits:
            limits[key] = _number(value, limits[key])

    warnings: list[str] = []
    named_sources = {
        "dividend_dashboard": dividend_dashboard,
        "investor_dashboard": investor_dashboard,
        "alerts_report": alerts_report,
        "reviews_report": reviews_report,
        "learning_report": learning_report,
        "cio_advisory_report": cio_advisory_report,
        "replacement_report": replacement_report,
        "confidence_report": confidence_report,
        "forecast_report": forecast_report,
        "analytics_report": analytics_report,
    }
    for name, source in named_sources.items():
        if source is None:
            warnings.append(f"Optional source not supplied: {name}.")

    alerts = _source_rows(alerts_report, ("alerts",))
    reviews = _source_rows(reviews_report, ("reviews", "review_records"))
    learning = _source_rows(learning_report, ("learning_records", "records"))
    recommendations = _source_rows(cio_advisory_report, ("recommendations",))
    comparisons = _source_rows(replacement_report, ("comparisons", "replacement_comparisons"))

    alert_total = len(alerts)
    critical_alerts = sum(1 for item in alerts if str(item.get("severity", "")).upper() == "CRITICAL")
    high_alerts = sum(1 for item in alerts if str(item.get("severity", "")).upper() == "HIGH")
    critical_ratio = 0.0 if alert_total == 0 else critical_alerts / alert_total * 100.0
    high_ratio = 0.0 if alert_total == 0 else high_alerts / alert_total * 100.0
    alert_score = max(0.0, 100.0 - critical_ratio * 2.5 - high_ratio)

    review_total = len(reviews)
    completed_reviews = sum(1 for item in reviews if str(item.get("status", "")).upper() == "RESOLVED")
    escalated_reviews = sum(1 for item in reviews if str(item.get("status", "")).upper() == "ESCALATED")
    review_completion = 100.0 if review_total == 0 else completed_reviews / review_total * 100.0
    escalation_rate = 0.0 if review_total == 0 else escalated_reviews / review_total * 100.0
    review_score = max(0.0, min(100.0, review_completion - escalation_rate * 0.5))

    forecast_summary = _summary(forecast_report)
    learning_summary = _summary(learning_report)
    forecast_accuracy = _percent(_first(forecast_summary, ("forecast_accuracy_percent", "accuracy_percent"), _first(learning_summary, ("forecast_accuracy_percent", "average_forecast_accuracy_percent"), 50.0)), 50.0)
    forecast_score = forecast_accuracy

    false_alerts = sum(1 for item in learning if bool(item.get("false_alert")) or str(item.get("classification", "")).upper() == "FALSE_ALERT")
    evaluated_alerts = sum(1 for item in learning if item.get("alert_id") or item.get("alert_evaluated"))
    false_alert_rate = 0.0 if evaluated_alerts == 0 else false_alerts / evaluated_alerts * 100.0
    learning_score = max(0.0, 100.0 - false_alert_rate)

    investor_summary = _summary(investor_dashboard)
    dashboard_summary = _summary(dividend_dashboard)
    analytics_summary = _summary(analytics_report)
    income_growth = _number(_first(analytics_summary, ("income_growth_percent", "annual_income_growth_percent"), _first(dashboard_summary, ("income_growth_percent",), 0.0)))
    income_score = max(0.0, min(100.0, 70.0 + income_growth * 3.0))

    confidence_summary = _summary(confidence_report)
    confidence = _percent(_first(confidence_summary, ("confidence_score", "portfolio_confidence", "overall_confidence"), _first(investor_summary, ("confidence_score",), 50.0)), 50.0)

    evidence_complete = _percent(_first(analytics_summary, ("evidence_completeness_percent",), _first(confidence_summary, ("evidence_completeness_percent",), 100.0)), 100.0)

    largest_position = _percent(_first(investor_summary, ("largest_position_percent",), 0.0))
    largest_sector = _percent(_first(investor_summary, ("largest_sector_percent", "sector_concentration_percent"), 0.0))
    concentration_penalty = max(0.0, largest_position - limits["max_position_concentration"]) * 2.0 + max(0.0, largest_sector - limits["max_sector_concentration"])
    concentration_score = max(0.0, 100.0 - concentration_penalty)

    replacement_count = sum(1 for item in comparisons if str(item.get("recommendation", item.get("action", ""))).upper() == "REPLACEMENT_REVIEW")
    replacement_rate = 0.0 if not comparisons else replacement_count / len(comparisons) * 100.0
    replacement_score = max(0.0, 100.0 - replacement_rate * 0.75)

    action_counts = {action: sum(1 for item in recommendations if str(item.get("recommendation", item.get("action", ""))).upper() == action) for action in ("HOLD", "REVIEW", "REDUCE", "EXIT_REVIEW", "REPLACEMENT_REVIEW")}
    adverse_recommendations = action_counts["REDUCE"] + action_counts["EXIT_REVIEW"] + action_counts["REPLACEMENT_REVIEW"]
    cio_score = 100.0 if not recommendations else max(0.0, 100.0 - adverse_recommendations / len(recommendations) * 75.0)

    metrics = [
        _metric("forecast_accuracy", forecast_accuracy, forecast_score, 0.15, _classify(forecast_score, limits), "forecast/learning"),
        _metric("income_growth", income_growth, income_score, 0.15, _classify(income_score, limits), "analytics/dashboard"),
        _metric("alert_quality", 100.0 - critical_ratio, alert_score, 0.15, _classify(alert_score, limits), "alerts"),
        _metric("review_effectiveness", review_completion, review_score, 0.15, _classify(review_score, limits), "reviews"),
        _metric("learning_quality", 100.0 - false_alert_rate, learning_score, 0.10, _classify(learning_score, limits), "learning"),
        _metric("confidence", confidence, confidence, 0.10, _classify(confidence, limits), "confidence"),
        _metric("evidence_completeness", evidence_complete, evidence_complete, 0.10, _classify(evidence_complete, limits), "analytics/confidence"),
        _metric("concentration_control", 100.0 - concentration_penalty, concentration_score, 0.05, _classify(concentration_score, limits), "investor_dashboard"),
        _metric("cio_advisory_stability", cio_score, cio_score, 0.025, _classify(cio_score, limits), "cio_advisory"),
        _metric("replacement_stability", 100.0 - replacement_rate, replacement_score, 0.025, _classify(replacement_score, limits), "replacement"),
    ]
    overall_score = round(sum(item["weighted_score"] for item in metrics), 2)
    force_critical = critical_ratio >= limits["critical_alert_ratio"] or evidence_complete < 40.0
    overall_status = _classify(overall_score, limits, force_critical=force_critical)

    flags: list[dict[str, str]] = []
    if critical_alerts:
        flags.append({"severity": "CRITICAL", "code": "CRITICAL_ALERTS_PRESENT", "message": f"{critical_alerts} critical alert(s) require review."})
    if forecast_accuracy < limits["forecast_accuracy_min"]:
        flags.append({"severity": "HIGH", "code": "LOW_FORECAST_ACCURACY", "message": f"Forecast accuracy is {forecast_accuracy:.2f}%."})
    if review_completion < limits["review_completion_min"] and review_total:
        flags.append({"severity": "HIGH", "code": "LOW_REVIEW_COMPLETION", "message": f"Review completion is {review_completion:.2f}%."})
    if evidence_complete < limits["evidence_completeness_min"]:
        flags.append({"severity": "HIGH", "code": "EVIDENCE_INCOMPLETE", "message": f"Evidence completeness is {evidence_complete:.2f}%."})
    if largest_position > limits["max_position_concentration"]:
        flags.append({"severity": "MEDIUM", "code": "POSITION_CONCENTRATION", "message": f"Largest position is {largest_position:.2f}%."})
    if largest_sector > limits["max_sector_concentration"]:
        flags.append({"severity": "MEDIUM", "code": "SECTOR_CONCENTRATION", "message": f"Largest sector is {largest_sector:.2f}%."})
    if income_growth < 0:
        flags.append({"severity": "MEDIUM", "code": "NEGATIVE_INCOME_GROWTH", "message": f"Income growth is {income_growth:.2f}%."})
    if false_alert_rate > 25.0:
        flags.append({"severity": "LOW", "code": "HIGH_FALSE_ALERT_RATE", "message": f"False-alert rate is {false_alert_rate:.2f}%."})
    priority = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    flags.sort(key=lambda item: (priority.get(item["severity"], 9), item["code"]))

    actions = []
    if flags:
        actions.append({"priority": "HIGH" if any(item["severity"] in {"CRITICAL", "HIGH"} for item in flags) else "MEDIUM", "action": "Route strategy health findings into the governed investor review process."})
    if forecast_accuracy < limits["forecast_accuracy_min"]:
        actions.append({"priority": "MEDIUM", "action": "Review forecast assumptions and learning recommendations before approving policy changes."})
    if not actions:
        actions.append({"priority": "INFO", "action": "Continue paper-only monitoring; no strategy health intervention is currently indicated."})

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at_utc or _now_utc(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
        "advisory_only": True,
        "policy_change_enabled": False,
        "health_status": overall_status,
        "health_score": overall_score,
        "summary": {
            "metric_count": len(metrics),
            "alert_count": alert_total,
            "critical_alert_count": critical_alerts,
            "high_alert_count": high_alerts,
            "review_count": review_total,
            "review_completion_percent": round(review_completion, 2),
            "escalation_rate_percent": round(escalation_rate, 2),
            "forecast_accuracy_percent": forecast_accuracy,
            "income_growth_percent": round(income_growth, 2),
            "false_alert_rate_percent": round(false_alert_rate, 2),
            "confidence_score": confidence,
            "evidence_completeness_percent": evidence_complete,
            "replacement_review_rate_percent": round(replacement_rate, 2),
            "risk_flag_count": len(flags),
        },
        "metrics": metrics,
        "cio_recommendation_distribution": action_counts,
        "risk_flags": flags,
        "suggested_actions": actions,
        "warnings": warnings,
        "thresholds": {key: round(value, 2) for key, value in limits.items()},
        "governance": {
            "human_approval_required": True,
            "may_execute_trades": False,
            "may_move_capital": False,
            "may_change_strategy": False,
            "may_change_policy": False,
        },
    }


def render_enterprise_dividend_strategy_health_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Enterprise Dividend Strategy Health",
        "",
        f"- Status: **{report.get('health_status', 'UNKNOWN')}**",
        f"- Health Score: **{_number(report.get('health_score')):.2f}/100**",
        f"- Generated: {report.get('generated_at_utc', '')}",
        "- Mode: Paper-only, advisory-only",
        "",
        "## Executive Summary",
        "",
        f"- Forecast accuracy: {summary.get('forecast_accuracy_percent', 0):.2f}%",
        f"- Income growth: {summary.get('income_growth_percent', 0):.2f}%",
        f"- Review completion: {summary.get('review_completion_percent', 0):.2f}%",
        f"- Risk flags: {summary.get('risk_flag_count', 0)}",
        "",
        "## Metric Breakdown",
        "",
        "| Metric | Value | Score | Status |",
        "|---|---:|---:|---|",
    ]
    for item in report.get("metrics", []):
        lines.append(f"| {item.get('metric')} | {item.get('value', 0):.2f} | {item.get('score', 0):.2f} | {item.get('status')} |")
    lines.extend(["", "## Risk Flags", ""])
    flags = report.get("risk_flags", [])
    if flags:
        for item in flags:
            lines.append(f"- **{item.get('severity')} — {item.get('code')}**: {item.get('message')}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Suggested Actions", ""])
    for item in report.get("suggested_actions", []):
        lines.append(f"- **{item.get('priority')}**: {item.get('action')}")
    lines.extend(["", "## Warnings", ""])
    warnings = report.get("warnings", [])
    lines.extend([f"- {item}" for item in warnings] or ["- None."])
    lines.extend(["", "## Governance Notes", "", "This report is paper-only and advisory-only. It cannot trade, move capital, alter allocations, change strategy, or silently modify policy.", ""])
    return "\n".join(lines)


def write_enterprise_dividend_strategy_health(
    report: Mapping[str, Any], output_dir: str | Path = "results"
) -> dict[str, str]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / DEFAULT_OUTPUT_FILES["json"]
    markdown_path = directory / DEFAULT_OUTPUT_FILES["markdown"]
    json_path.write_text(json.dumps(dict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_enterprise_dividend_strategy_health_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def build_and_write_enterprise_dividend_strategy_health(
    *, output_dir: str | Path = "results", **kwargs: Any
) -> dict[str, Any]:
    report = build_enterprise_dividend_strategy_health(**kwargs)
    report["output_files"] = write_enterprise_dividend_strategy_health(report, output_dir)
    return report
