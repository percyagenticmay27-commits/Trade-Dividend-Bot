"""Append-only governed learning records for the Trade Dividend Bot.

Compares paper-only forecasts with actual paper income, evaluates alert and review
outcomes, and recommends policy improvements without changing policy.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "enterprise_dividend_learning_integration"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ADVISORY_ONLY = True
APPEND_ONLY = True
POLICY_AUTO_CHANGE_ENABLED = False

DEFAULT_OUTPUT_FILES = {
    "json": "enterprise_dividend_learning.json",
    "markdown": "enterprise_dividend_learning.md",
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


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    text = str(value or default).strip()
    return text.upper() if text else default


def _stable_id(*parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _forecast_metrics(forecasts: Sequence[Mapping[str, Any]], actuals: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    actual_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in actuals:
        key = (_upper(row.get("symbol"), "PORTFOLIO"), str(row.get("period") or row.get("payment_date") or "CURRENT"))
        actual_by_key[key] = dict(row)
    metrics: list[dict[str, Any]] = []
    for forecast in forecasts:
        symbol = _upper(forecast.get("symbol"), "PORTFOLIO")
        period = str(forecast.get("period") or forecast.get("payment_date") or "CURRENT")
        actual = actual_by_key.get((symbol, period))
        if not actual:
            continue
        expected = _number(forecast.get("forecast_income", forecast.get("projected_income", forecast.get("amount", 0.0))))
        received = _number(actual.get("actual_income", actual.get("received_income", actual.get("amount", 0.0))))
        error = received - expected
        absolute_error = abs(error)
        percentage_error = 0.0 if expected == 0 else (absolute_error / abs(expected)) * 100.0
        accuracy = max(0.0, 100.0 - percentage_error)
        metrics.append({
            "symbol": symbol,
            "period": period,
            "forecast_income": round(expected, 2),
            "actual_income": round(received, 2),
            "forecast_error": round(error, 2),
            "absolute_error": round(absolute_error, 2),
            "absolute_percentage_error": round(percentage_error, 4),
            "accuracy_percent": round(accuracy, 4),
            "forecast_source": str(forecast.get("source_report") or "income_forecast.json"),
            "actual_source": str(actual.get("source_report") or "paper_income_actuals.json"),
        })
    metrics.sort(key=lambda row: (row["period"], row["symbol"]))
    return metrics


def _alert_metrics(alerts: Sequence[Mapping[str, Any]], reviews: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    reviews_by_alert = {str(row.get("alert_id")): dict(row) for row in reviews if row.get("alert_id")}
    results: list[dict[str, Any]] = []
    for alert in alerts:
        alert_id = str(alert.get("alert_id") or "")
        if not alert_id:
            continue
        review = reviews_by_alert.get(alert_id, {})
        status = _upper(review.get("status"), "OPEN")
        outcome = _upper(review.get("outcome") or review.get("resolution") or review.get("decision"), "UNDETERMINED")
        false_alert = bool(review.get("false_alert")) or outcome in {"FALSE_ALERT", "NO_ISSUE", "NOT_CONFIRMED"}
        confirmed = outcome in {"CONFIRMED", "VALID", "ACTION_REQUIRED", "RESOLVED_VALID"}
        results.append({
            "alert_id": alert_id,
            "symbol": _upper(alert.get("symbol"), "PORTFOLIO"),
            "alert_type": _upper(alert.get("alert_type")),
            "severity": _upper(alert.get("severity")),
            "review_id": review.get("review_id"),
            "review_status": status,
            "review_outcome": outcome,
            "false_alert": false_alert,
            "confirmed_alert": confirmed,
            "source_report": alert.get("source_report"),
            "evidence_links": list(alert.get("evidence_links") or []),
        })
    results.sort(key=lambda row: (row["symbol"], row["alert_type"], row["alert_id"]))
    return results


def _recommendations(forecast_metrics: Sequence[Mapping[str, Any]], alert_metrics: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    if forecast_metrics:
        avg_accuracy = sum(_number(row.get("accuracy_percent")) for row in forecast_metrics) / len(forecast_metrics)
        if avg_accuracy < 80.0:
            recommendations.append({
                "priority": "HIGH",
                "category": "FORECAST_METHOD",
                "recommendation": "Review forecast assumptions and evidence sources because average paper-income forecast accuracy is below 80%.",
                "requires_human_approval": True,
                "automatic_policy_change": False,
            })
        elif avg_accuracy < 90.0:
            recommendations.append({
                "priority": "MEDIUM",
                "category": "FORECAST_CALIBRATION",
                "recommendation": "Evaluate forecast calibration for recurring sources of error.",
                "requires_human_approval": True,
                "automatic_policy_change": False,
            })
    resolved = [row for row in alert_metrics if row.get("review_status") == "RESOLVED"]
    false_count = sum(1 for row in resolved if row.get("false_alert"))
    if resolved and false_count / len(resolved) >= 0.25:
        recommendations.append({
            "priority": "MEDIUM",
            "category": "ALERT_THRESHOLD",
            "recommendation": "Review alert thresholds because at least 25% of resolved alerts were classified as false alerts.",
            "requires_human_approval": True,
            "automatic_policy_change": False,
        })
    if not recommendations:
        recommendations.append({
            "priority": "INFO",
            "category": "MONITORING",
            "recommendation": "Continue collecting paper outcomes before recommending policy changes.",
            "requires_human_approval": True,
            "automatic_policy_change": False,
        })
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
    recommendations.sort(key=lambda row: (order.get(row["priority"], 9), row["category"]))
    return recommendations


def _learning_record(record_type: str, subject: str, period: str, payload: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    record_key = _stable_id(record_type, subject, period, json.dumps(payload, sort_keys=True, default=str))
    return {
        "learning_record_id": f"DIV-LEARN-{record_key[:16].upper()}",
        "record_key": record_key,
        "record_type": record_type,
        "subject": subject,
        "period": period,
        "payload": dict(payload),
        "created_at_utc": generated_at,
        "append_only": True,
        "paper_trade_mode": True,
        "advisory_only": True,
    }


def build_enterprise_dividend_learning(
    *,
    forecasts: Optional[Sequence[Mapping[str, Any]]] = None,
    actual_income: Optional[Sequence[Mapping[str, Any]]] = None,
    alerts: Optional[Sequence[Mapping[str, Any]]] = None,
    reviews: Optional[Sequence[Mapping[str, Any]]] = None,
    existing_learning_records: Optional[Sequence[Mapping[str, Any]]] = None,
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Build append-only learning records from governed paper outcomes."""
    generated_at = generated_at_utc or _now_utc()
    forecast_rows = _rows(forecasts or [])
    actual_rows = _rows(actual_income or [])
    alert_rows = _rows(alerts or [])
    review_rows = _rows(reviews or [])
    existing = _rows(existing_learning_records or [])

    forecast_metrics = _forecast_metrics(forecast_rows, actual_rows)
    alert_metrics = _alert_metrics(alert_rows, review_rows)
    recommendations = _recommendations(forecast_metrics, alert_metrics)

    new_records: list[dict[str, Any]] = []
    for metric in forecast_metrics:
        new_records.append(_learning_record("FORECAST_OUTCOME", metric["symbol"], metric["period"], metric, generated_at))
    for metric in alert_metrics:
        if metric["review_status"] in {"RESOLVED", "DEFERRED", "ESCALATED"}:
            new_records.append(_learning_record("ALERT_REVIEW_OUTCOME", metric["alert_id"], metric["review_status"], metric, generated_at))
    for recommendation in recommendations:
        new_records.append(_learning_record("IMPROVEMENT_RECOMMENDATION", recommendation["category"], "CURRENT", recommendation, generated_at))

    existing_keys = {str(row.get("record_key")) for row in existing if row.get("record_key")}
    appended = [row for row in new_records if row["record_key"] not in existing_keys]
    all_records = existing + appended

    avg_accuracy = round(sum(_number(row.get("accuracy_percent")) for row in forecast_metrics) / len(forecast_metrics), 4) if forecast_metrics else None
    resolved_alerts = [row for row in alert_metrics if row["review_status"] == "RESOLVED"]
    false_alert_count = sum(1 for row in resolved_alerts if row["false_alert"])
    warnings: list[str] = []
    if not forecast_rows:
        warnings.append("Forecast records were not supplied.")
    if not actual_rows:
        warnings.append("Actual paper-income records were not supplied.")
    if not alert_rows:
        warnings.append("Alert records were not supplied.")
    if not review_rows:
        warnings.append("Review records were not supplied.")

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "advisory_only": True,
        "append_only": True,
        "policy_auto_change_enabled": False,
        "status": "READY" if forecast_metrics or alert_metrics else "PARTIAL",
        "summary": {
            "forecast_comparison_count": len(forecast_metrics),
            "average_forecast_accuracy_percent": avg_accuracy,
            "evaluated_alert_count": len(alert_metrics),
            "resolved_alert_count": len(resolved_alerts),
            "false_alert_count": false_alert_count,
            "recommendation_count": len(recommendations),
            "existing_learning_record_count": len(existing),
            "appended_learning_record_count": len(appended),
            "total_learning_record_count": len(all_records),
        },
        "forecast_metrics": forecast_metrics,
        "alert_metrics": alert_metrics,
        "recommendations": recommendations,
        "appended_learning_records": appended,
        "learning_records": all_records,
        "warnings": warnings,
        "governance": {
            "human_approval_required": True,
            "recommendations_change_policy_automatically": False,
            "records_are_append_only": True,
            "capital_movement_allowed": False,
            "brokerage_execution_allowed": False,
        },
    }


def render_enterprise_dividend_learning_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        "# Enterprise Dividend Learning",
        "",
        f"- Module: `{report.get('module_name')}`",
        f"- Version: `{report.get('module_version')}`",
        f"- Generated: `{report.get('generated_at_utc')}`",
        f"- Status: **{report.get('status')}**",
        "- Paper only: **True**",
        "- Append only: **True**",
        "- Automatic policy changes: **False**",
        "",
        "## Summary",
        "",
        f"- Forecast comparisons: {summary.get('forecast_comparison_count', 0)}",
        f"- Average forecast accuracy: {summary.get('average_forecast_accuracy_percent')}",
        f"- Evaluated alerts: {summary.get('evaluated_alert_count', 0)}",
        f"- False alerts: {summary.get('false_alert_count', 0)}",
        f"- Appended learning records: {summary.get('appended_learning_record_count', 0)}",
        "",
        "## Recommendations",
        "",
    ]
    for item in report.get("recommendations") or []:
        lines.append(f"- **{item.get('priority')} / {item.get('category')}** — {item.get('recommendation')}")
    lines.extend(["", "## Warnings", ""])
    warnings = report.get("warnings") or []
    lines.extend(f"- {warning}" for warning in warnings) if warnings else lines.append("- None")
    lines.extend(["", "## Governance", "", "Learning output is advisory only. Human approval is required before any policy change or portfolio action.", ""])
    return "\n".join(lines)


def write_enterprise_dividend_learning(report: Mapping[str, Any], output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / DEFAULT_OUTPUT_FILES["json"]
    markdown_path = output / DEFAULT_OUTPUT_FILES["markdown"]
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_enterprise_dividend_learning_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def build_and_write_enterprise_dividend_learning(output_dir: str | Path, **kwargs: Any) -> dict[str, Any]:
    report = build_enterprise_dividend_learning(**kwargs)
    report["output_files"] = write_enterprise_dividend_learning(report, output_dir)
    return report
