"""Governed Enterprise Dividend CIO advisory integration.

Consumes existing paper-only income, forecast, analytics, alert, review, and
learning artifacts to produce traceable recommendations. The module is advisory
only and cannot place orders, contact a broker, move capital, approve policy
changes, or make an investor decision.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "enterprise_dividend_cio_advisory_integration"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ADVISORY_ONLY = True
HUMAN_APPROVAL_REQUIRED = True
POLICY_CHANGE_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False

RECOMMENDATION_TYPES = {
    "HOLD",
    "REVIEW",
    "REDUCE",
    "EXIT_REVIEW",
    "REPLACEMENT_REVIEW",
}
SEVERITY_RANK = {"CRITICAL": 5, "HIGH": 4, "MEDIUM": 3, "LOW": 2, "INFO": 1}
RECOMMENDATION_RANK = {
    "EXIT_REVIEW": 5,
    "REPLACEMENT_REVIEW": 4,
    "REDUCE": 3,
    "REVIEW": 2,
    "HOLD": 1,
}
DEFAULT_OUTPUT_FILES = {
    "json": "enterprise_dividend_cio_advisory.json",
    "markdown": "enterprise_dividend_cio_advisory.md",
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


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    text = str(value or default).strip()
    return text.upper() if text else default


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _first(mapping: Mapping[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _extract_rows(source: Optional[Mapping[str, Any]], keys: Sequence[str]) -> list[dict[str, Any]]:
    if not isinstance(source, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for key in keys:
        rows.extend(_rows(source.get(key)))
    for container_name in ("summary", "dashboard", "analytics", "portfolio_summary"):
        container = source.get(container_name)
        if isinstance(container, Mapping):
            for key in keys:
                rows.extend(_rows(container.get(key)))
    return rows


def _stable_id(symbol: str, recommendation: str, reporting_period: str, evidence_ids: Sequence[str]) -> str:
    raw = "|".join((symbol, recommendation, reporting_period, *sorted(evidence_ids)))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()
    return f"DIV-CIO-{digest}"


def _alert_signal(alerts: Sequence[Mapping[str, Any]]) -> tuple[int, set[str], list[str]]:
    score = 0
    types: set[str] = set()
    evidence: list[str] = []
    for item in alerts:
        status = _upper(item.get("status"), "OPEN")
        if status in {"RESOLVED", "DEFERRED"}:
            continue
        severity = _upper(item.get("severity"), "INFO")
        alert_type = _upper(item.get("alert_type") or item.get("code"), "UNKNOWN")
        score += SEVERITY_RANK.get(severity, 0)
        types.add(alert_type)
        if item.get("alert_id"):
            evidence.append(str(item["alert_id"]))
    return score, types, evidence


def _review_signal(reviews: Sequence[Mapping[str, Any]]) -> tuple[int, set[str], list[str]]:
    score = 0
    states: set[str] = set()
    evidence: list[str] = []
    for item in reviews:
        state = _upper(item.get("status") or item.get("review_status"), "OPEN")
        states.add(state)
        if state == "ESCALATED":
            score += 5
        elif state == "UNDER_REVIEW":
            score += 3
        elif state == "OPEN":
            score += 2
        elif state == "DEFERRED":
            score += 1
        if item.get("review_id"):
            evidence.append(str(item["review_id"]))
    return score, states, evidence


def _learning_signal(learning: Sequence[Mapping[str, Any]]) -> tuple[int, set[str], list[str]]:
    score = 0
    findings: set[str] = set()
    evidence: list[str] = []
    for item in learning:
        finding = _upper(item.get("learning_type") or item.get("finding_type") or item.get("classification"), "UNKNOWN")
        findings.add(finding)
        if finding in {"FALSE_ALERT", "FORECAST_BIAS", "POLICY_REVIEW", "MODEL_WEAKNESS"}:
            score += 2
        if item.get("learning_record_id"):
            evidence.append(str(item["learning_record_id"]))
        elif item.get("record_id"):
            evidence.append(str(item["record_id"]))
    return score, findings, evidence


def _recommendation_for_symbol(
    *,
    symbol: str,
    alerts: Sequence[Mapping[str, Any]],
    reviews: Sequence[Mapping[str, Any]],
    learning: Sequence[Mapping[str, Any]],
    income_growth_percent: float,
    forecast_accuracy_percent: float,
    confidence_score: float,
    reporting_period: str,
    generated_at: str,
) -> dict[str, Any]:
    alert_score, alert_types, alert_ids = _alert_signal(alerts)
    review_score, review_states, review_ids = _review_signal(reviews)
    learning_score, learning_types, learning_ids = _learning_signal(learning)
    evidence_ids = sorted(set(alert_ids + review_ids + learning_ids))

    recommendation = "HOLD"
    rationale: list[str] = []
    priority = "LOW"

    if "DIVIDEND_SUSPENSION" in alert_types or "MISSED_PAYMENT" in alert_types and "ESCALATED" in review_states:
        recommendation = "EXIT_REVIEW"
        priority = "CRITICAL"
        rationale.append("A suspension or escalated missed-payment condition requires an exit review.")
    elif "DIVIDEND_CUT" in alert_types and (income_growth_percent < 0 or confidence_score < 50):
        recommendation = "REPLACEMENT_REVIEW"
        priority = "HIGH"
        rationale.append("A dividend cut combined with weakening income or confidence warrants replacement analysis.")
    elif alert_score + review_score >= 9 or "ESCALATED" in review_states:
        recommendation = "REDUCE"
        priority = "HIGH"
        rationale.append("Combined governed risk and review signals justify advisory exposure reduction review.")
    elif alert_score + review_score + learning_score >= 4 or income_growth_percent < 0 or forecast_accuracy_percent < 70 or confidence_score < 60:
        recommendation = "REVIEW"
        priority = "MEDIUM"
        rationale.append("One or more income, forecast, confidence, alert, review, or learning signals require human review.")
    else:
        rationale.append("No material governed deterioration was identified from supplied evidence.")

    if income_growth_percent < 0:
        rationale.append(f"Income growth is negative at {income_growth_percent:.2f}%.")
    if forecast_accuracy_percent < 70:
        rationale.append(f"Forecast accuracy is below the 70% advisory threshold at {forecast_accuracy_percent:.2f}%.")
    if confidence_score < 60:
        rationale.append(f"Confidence is below the 60-point advisory threshold at {confidence_score:.2f}.")
    if learning_types:
        rationale.append("Learning evidence was considered without changing policy automatically.")

    return {
        "recommendation_id": _stable_id(symbol, recommendation, reporting_period, evidence_ids),
        "symbol": symbol,
        "recommendation": recommendation,
        "priority": priority,
        "status": "PENDING_INVESTOR_APPROVAL",
        "rationale": rationale,
        "alert_score": alert_score,
        "review_score": review_score,
        "learning_score": learning_score,
        "income_growth_percent": round(income_growth_percent, 4),
        "forecast_accuracy_percent": round(forecast_accuracy_percent, 4),
        "confidence_score": round(confidence_score, 4),
        "originating_alert_ids": alert_ids,
        "originating_review_ids": review_ids,
        "originating_learning_record_ids": learning_ids,
        "evidence_ids": evidence_ids,
        "reporting_period": reporting_period,
        "generated_at_utc": generated_at,
        "advisory_only": True,
        "human_approval_required": True,
        "capital_movement_authorized": False,
    }


def build_enterprise_dividend_cio_advisory(
    *,
    income_report: Optional[Mapping[str, Any]] = None,
    forecast_report: Optional[Mapping[str, Any]] = None,
    analytics_report: Optional[Mapping[str, Any]] = None,
    alert_report: Optional[Mapping[str, Any]] = None,
    review_report: Optional[Mapping[str, Any]] = None,
    learning_report: Optional[Mapping[str, Any]] = None,
    reporting_period: str = "CURRENT",
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Build governed advisory recommendations from read-only artifacts."""
    generated_at = generated_at_utc or _now_utc()
    alerts = _extract_rows(alert_report, ("alerts",))
    reviews = _extract_rows(review_report, ("reviews", "review_records"))
    learning = _extract_rows(learning_report, ("learning_records", "records"))

    symbol_set: set[str] = set()
    for rows in (alerts, reviews, learning):
        for item in rows:
            symbol_set.add(_upper(item.get("symbol"), "PORTFOLIO"))
    for source in (income_report, forecast_report, analytics_report):
        if isinstance(source, Mapping):
            positions = _extract_rows(source, ("holdings", "positions", "symbols"))
            for item in positions:
                symbol_set.add(_upper(item.get("symbol") or item.get("ticker"), "PORTFOLIO"))
    if not symbol_set and any(source is not None for source in (income_report, forecast_report, analytics_report, alert_report, review_report, learning_report)):
        symbol_set.add("PORTFOLIO")

    def rows_for(symbol: str, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        return [dict(item) for item in rows if _upper(item.get("symbol"), "PORTFOLIO") == symbol]

    analytics_summary = dict(analytics_report.get("summary") or analytics_report) if isinstance(analytics_report, Mapping) else {}
    income_summary = dict(income_report.get("summary") or income_report) if isinstance(income_report, Mapping) else {}
    forecast_summary = dict(forecast_report.get("summary") or forecast_report) if isinstance(forecast_report, Mapping) else {}

    recommendations: list[dict[str, Any]] = []
    for symbol in sorted(symbol_set):
        income_growth = _number(_first(analytics_summary, ("income_growth_percent", "annual_income_growth_percent"), _first(income_summary, ("income_growth_percent",), 0.0)))
        accuracy = _number(_first(forecast_summary, ("forecast_accuracy_percent", "accuracy_percent"), _first(analytics_summary, ("forecast_accuracy_percent",), 100.0)), 100.0)
        confidence = _number(_first(analytics_summary, ("confidence_score", "portfolio_confidence"), 100.0), 100.0)
        recommendations.append(_recommendation_for_symbol(
            symbol=symbol,
            alerts=rows_for(symbol, alerts),
            reviews=rows_for(symbol, reviews),
            learning=rows_for(symbol, learning),
            income_growth_percent=income_growth,
            forecast_accuracy_percent=accuracy,
            confidence_score=confidence,
            reporting_period=reporting_period,
            generated_at=generated_at,
        ))

    recommendations.sort(key=lambda item: (-RECOMMENDATION_RANK[item["recommendation"]], item["symbol"]))
    counts = {name.lower(): sum(1 for item in recommendations if item["recommendation"] == name) for name in RECOMMENDATION_TYPES}
    warnings: list[str] = []
    for label, source in (
        ("income report", income_report),
        ("forecast report", forecast_report),
        ("analytics report", analytics_report),
        ("alert report", alert_report),
        ("review report", review_report),
        ("learning report", learning_report),
    ):
        if source is None:
            warnings.append(f"Optional {label} was not supplied.")

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "reporting_period": reporting_period,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "advisory_only": True,
        "human_approval_required": True,
        "policy_change_enabled": False,
        "capital_movement_enabled": False,
        "advisory_status": "READY" if recommendations else "PARTIAL",
        "summary": {
            "recommendation_count": len(recommendations),
            **counts,
            "pending_investor_approval_count": len(recommendations),
        },
        "recommendations": recommendations,
        "warnings": warnings,
        "governance": {
            "decision_authority": "INVESTOR",
            "recommendations_are_non_executing": True,
            "automatic_policy_changes_prohibited": True,
            "automatic_capital_movement_prohibited": True,
        },
    }


def render_enterprise_dividend_cio_advisory_markdown(report: Mapping[str, Any]) -> str:
    summary = dict(report.get("summary") or {})
    lines = [
        "# Enterprise Dividend CIO Advisory",
        "",
        f"- Generated: {report.get('generated_at_utc', '')}",
        f"- Reporting period: {report.get('reporting_period', '')}",
        "- Paper trade mode: True",
        "- Advisory only: True",
        "- Human approval required: True",
        "",
        "## Summary",
        "",
        f"- Recommendations: {summary.get('recommendation_count', 0)}",
        f"- Hold: {summary.get('hold', 0)}",
        f"- Review: {summary.get('review', 0)}",
        f"- Reduce: {summary.get('reduce', 0)}",
        f"- Exit review: {summary.get('exit_review', 0)}",
        f"- Replacement review: {summary.get('replacement_review', 0)}",
        "",
        "## Recommendations",
        "",
    ]
    recommendations = _rows(report.get("recommendations"))
    if not recommendations:
        lines.append("No advisory recommendations were generated.")
    for item in recommendations:
        lines.extend([
            f"### {item.get('symbol')} — {item.get('recommendation')}",
            "",
            f"- Priority: {item.get('priority')}",
            f"- Status: {item.get('status')}",
            f"- Recommendation ID: {item.get('recommendation_id')}",
            f"- Evidence IDs: {', '.join(item.get('evidence_ids') or []) or 'None'}",
            "- Rationale:",
        ])
        for reason in item.get("rationale") or []:
            lines.append(f"  - {reason}")
        lines.append("")
    lines.extend(["## Governance", "", "Recommendations are advisory and require investor approval. No orders, capital movement, or automatic policy changes are authorized.", ""])
    warnings = list(report.get("warnings") or [])
    if warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
    return "\n".join(lines)


def write_enterprise_dividend_cio_advisory(report: Mapping[str, Any], output_dir: Path | str) -> dict[str, str]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / DEFAULT_OUTPUT_FILES["json"]
    markdown_path = directory / DEFAULT_OUTPUT_FILES["markdown"]
    json_path.write_text(json.dumps(dict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_enterprise_dividend_cio_advisory_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def build_and_write_enterprise_dividend_cio_advisory(*, output_dir: Path | str, **kwargs: Any) -> dict[str, Any]:
    report = build_enterprise_dividend_cio_advisory(**kwargs)
    output_files = write_enterprise_dividend_cio_advisory(report, output_dir)
    return {"report": report, "output_files": output_files}
