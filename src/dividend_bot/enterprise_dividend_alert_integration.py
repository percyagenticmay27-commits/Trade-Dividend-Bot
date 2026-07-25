"""Governed enterprise dividend alerts for the Trade Dividend Bot.

This module converts existing paper-only analytics and reporting findings into
immutable, traceable alert records. It never places orders, contacts a broker,
or moves capital.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "enterprise_dividend_alert_integration"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True
ADVISORY_ONLY = True

ALERT_TYPES = {
    "DIVIDEND_CUT",
    "DIVIDEND_SUSPENSION",
    "MISSED_PAYMENT",
    "LOW_CONFIDENCE",
    "NEGATIVE_INCOME_GROWTH",
    "REDUCED_PROJECTED_INCOME",
    "EVIDENCE_GAP",
    "REVIEW_REQUIRED",
}
SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
ACTIVE_STATUSES = {"OPEN", "ACKNOWLEDGED", "UNDER_REVIEW", "ESCALATED"}
ALL_STATUSES = ACTIVE_STATUSES | {"RESOLVED", "DEFERRED"}

DEFAULT_OUTPUT_FILES = {
    "json": "enterprise_dividend_alerts.json",
    "markdown": "enterprise_dividend_alerts.md",
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


def _deduplication_key(symbol: str, alert_type: str, source_module: str, reporting_period: str) -> str:
    raw = "|".join((symbol, alert_type, source_module, reporting_period))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _alert_id(deduplication_key: str) -> str:
    return f"DIV-ALERT-{deduplication_key[:16].upper()}"


def _make_alert(
    *,
    symbol: str,
    alert_type: str,
    severity: str,
    source_module: str,
    source_report: str,
    reporting_period: str,
    message: str,
    recommended_action: str,
    evidence_links: Optional[Sequence[str]] = None,
    governance_notes: str = "Human review required before any portfolio action.",
    created_at_utc: str,
) -> dict[str, Any]:
    symbol = _upper(symbol)
    alert_type = _upper(alert_type)
    severity = _upper(severity)
    if alert_type not in ALERT_TYPES:
        raise ValueError(f"Unsupported alert type: {alert_type}")
    if severity not in SEVERITIES:
        raise ValueError(f"Unsupported severity: {severity}")
    key = _deduplication_key(symbol, alert_type, source_module, reporting_period)
    return {
        "alert_id": _alert_id(key),
        "deduplication_key": key,
        "symbol": symbol,
        "alert_type": alert_type,
        "severity": severity,
        "status": "OPEN",
        "message": message,
        "recommended_action": recommended_action,
        "source_module": source_module,
        "source_report": source_report,
        "reporting_period": reporting_period,
        "evidence_links": sorted({str(item) for item in (evidence_links or []) if str(item).strip()}),
        "governance_notes": governance_notes,
        "created_at_utc": created_at_utc,
        "last_updated_at_utc": created_at_utc,
        "paper_trade_mode": True,
        "advisory_only": True,
    }


def _extract_findings(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for key in ("alerts", "risk_flags", "review_flags", "findings", "issues"):
        findings.extend(_rows(source.get(key)))
    for container_key in ("dashboard", "summary", "analytics", "portfolio_summary"):
        container = source.get(container_key)
        if isinstance(container, Mapping):
            for key in ("alerts", "risk_flags", "review_flags", "findings", "issues"):
                findings.extend(_rows(container.get(key)))
    return findings


def _normalize_finding(
    finding: Mapping[str, Any], *, source_module: str, source_report: str, reporting_period: str, generated_at: str
) -> Optional[dict[str, Any]]:
    code = _upper(_first(finding, ("alert_type", "code", "type", "flag"), ""), "")
    aliases = {
        "DIVIDEND_REDUCTION": "DIVIDEND_CUT",
        "CUT": "DIVIDEND_CUT",
        "SUSPENSION": "DIVIDEND_SUSPENSION",
        "DIVIDEND_SUSPENDED": "DIVIDEND_SUSPENSION",
        "MISSED_DIVIDEND_PAYMENT": "MISSED_PAYMENT",
        "PAYMENT_MISSED": "MISSED_PAYMENT",
        "CONFIDENCE_LOW": "LOW_CONFIDENCE",
        "INCOME_GROWTH_NEGATIVE": "NEGATIVE_INCOME_GROWTH",
        "PROJECTED_INCOME_REDUCED": "REDUCED_PROJECTED_INCOME",
        "MISSING_EVIDENCE": "EVIDENCE_GAP",
        "SOURCE_REVIEW_FLAG": "REVIEW_REQUIRED",
    }
    alert_type = aliases.get(code, code)
    if alert_type not in ALERT_TYPES:
        return None
    default_severity = {
        "DIVIDEND_SUSPENSION": "CRITICAL",
        "DIVIDEND_CUT": "HIGH",
        "MISSED_PAYMENT": "HIGH",
        "NEGATIVE_INCOME_GROWTH": "MEDIUM",
        "REDUCED_PROJECTED_INCOME": "MEDIUM",
        "LOW_CONFIDENCE": "LOW",
        "EVIDENCE_GAP": "LOW",
        "REVIEW_REQUIRED": "INFO",
    }[alert_type]
    severity = _upper(finding.get("severity"), default_severity)
    if severity not in SEVERITIES:
        severity = default_severity
    symbol = _upper(_first(finding, ("symbol", "ticker", "asset"), "PORTFOLIO"))
    message = str(_first(finding, ("message", "reason", "description"), alert_type.replace("_", " ").title()))
    action = str(_first(finding, ("recommended_action", "action"), "Route this alert to the governed dividend review workflow."))
    evidence = finding.get("evidence_links") or finding.get("evidence") or []
    if isinstance(evidence, str):
        evidence = [evidence]
    return _make_alert(
        symbol=symbol,
        alert_type=alert_type,
        severity=severity,
        source_module=source_module,
        source_report=source_report,
        reporting_period=reporting_period,
        message=message,
        recommended_action=action,
        evidence_links=evidence,
        created_at_utc=generated_at,
    )


def _threshold_alerts(
    source: Mapping[str, Any], *, source_module: str, source_report: str, reporting_period: str, generated_at: str
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    summary = source.get("summary") if isinstance(source.get("summary"), Mapping) else source
    symbol = _upper(_first(summary, ("symbol", "ticker"), "PORTFOLIO"))

    confidence = _number(_first(summary, ("confidence_score", "confidence", "portfolio_confidence"), 100.0), 100.0)
    if confidence < 50.0:
        alerts.append(_make_alert(
            symbol=symbol, alert_type="LOW_CONFIDENCE", severity="LOW", source_module=source_module,
            source_report=source_report, reporting_period=reporting_period,
            message=f"Confidence score is {confidence:.2f}, below the 50.00 review threshold.",
            recommended_action="Review evidence quality and confidence inputs before approving any action.",
            created_at_utc=generated_at,
        ))

    growth = _number(_first(summary, ("income_growth_percent", "annual_income_growth_percent", "income_growth"), 0.0))
    if growth < 0.0:
        alerts.append(_make_alert(
            symbol=symbol, alert_type="NEGATIVE_INCOME_GROWTH", severity="MEDIUM", source_module=source_module,
            source_report=source_report, reporting_period=reporting_period,
            message=f"Income growth is negative at {growth:.2f}%.",
            recommended_action="Review the holdings responsible for declining paper dividend income.",
            created_at_utc=generated_at,
        ))

    current_income = _number(_first(summary, ("projected_annual_income", "annual_dividend_income", "projected_income"), 0.0))
    prior_income = _number(_first(summary, ("prior_projected_annual_income", "previous_annual_income", "prior_projected_income"), current_income))
    if prior_income > 0.0 and current_income < prior_income:
        decline = prior_income - current_income
        alerts.append(_make_alert(
            symbol=symbol, alert_type="REDUCED_PROJECTED_INCOME", severity="MEDIUM", source_module=source_module,
            source_report=source_report, reporting_period=reporting_period,
            message=f"Projected annual income decreased by {decline:.2f}.",
            recommended_action="Validate forecast changes and route material reductions for review.",
            created_at_utc=generated_at,
        ))

    evidence_complete = _first(summary, ("evidence_complete", "required_evidence_present"), True)
    missing_evidence = summary.get("missing_evidence") or summary.get("missing_required_evidence") or []
    if evidence_complete is False or bool(missing_evidence):
        alerts.append(_make_alert(
            symbol=symbol, alert_type="EVIDENCE_GAP", severity="LOW", source_module=source_module,
            source_report=source_report, reporting_period=reporting_period,
            message="Required supporting evidence is incomplete.",
            recommended_action="Collect or validate missing evidence before resolving the alert.",
            evidence_links=[str(item) for item in missing_evidence] if isinstance(missing_evidence, Sequence) and not isinstance(missing_evidence, str) else [],
            created_at_utc=generated_at,
        ))
    return alerts


def _merge_existing(new_alerts: Sequence[Mapping[str, Any]], existing_alerts: Sequence[Mapping[str, Any]], generated_at: str) -> list[dict[str, Any]]:
    existing_by_key = {
        str(item.get("deduplication_key")): dict(item)
        for item in existing_alerts
        if item.get("deduplication_key")
    }
    merged: list[dict[str, Any]] = []
    for candidate in new_alerts:
        item = dict(candidate)
        previous = existing_by_key.get(item["deduplication_key"])
        if previous and _upper(previous.get("status"), "OPEN") in ACTIVE_STATUSES:
            item["alert_id"] = previous.get("alert_id", item["alert_id"])
            item["created_at_utc"] = previous.get("created_at_utc", item["created_at_utc"])
            item["status"] = _upper(previous.get("status"), "OPEN")
            item["last_updated_at_utc"] = generated_at
        merged.append(item)
    merged.sort(key=lambda row: ({"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}.get(row["severity"], 9), row["symbol"], row["alert_type"]))
    return merged


def build_enterprise_dividend_alerts(
    *,
    dividend_dashboard: Optional[Mapping[str, Any]] = None,
    investor_dashboard: Optional[Mapping[str, Any]] = None,
    additional_sources: Optional[Sequence[Mapping[str, Any]]] = None,
    existing_alerts: Optional[Sequence[Mapping[str, Any]]] = None,
    reporting_period: str = "CURRENT",
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Build governed, deduplicated dividend alerts from read-only artifacts."""
    generated_at = generated_at_utc or _now_utc()
    source_specs: list[tuple[str, str, Mapping[str, Any]]] = []
    if dividend_dashboard is not None:
        source_specs.append(("enterprise_dividend_dashboard_integration", "enterprise_dividend_dashboard.json", dividend_dashboard))
    if investor_dashboard is not None:
        source_specs.append(("enterprise_investor_dashboard_integration", "enterprise_investor_dashboard.json", investor_dashboard))
    for index, source in enumerate(additional_sources or []):
        if isinstance(source, Mapping):
            source_specs.append((str(source.get("module_name") or f"additional_source_{index + 1}"), str(source.get("source_report") or "additional_source.json"), source))

    warnings: list[str] = []
    if dividend_dashboard is None:
        warnings.append("Enterprise dividend dashboard input was not supplied.")
    if investor_dashboard is None:
        warnings.append("Enterprise investor dashboard input was not supplied.")

    candidates: list[dict[str, Any]] = []
    for source_module, source_report, source in source_specs:
        for finding in _extract_findings(source):
            alert = _normalize_finding(
                finding,
                source_module=source_module,
                source_report=source_report,
                reporting_period=reporting_period,
                generated_at=generated_at,
            )
            if alert:
                candidates.append(alert)
        candidates.extend(_threshold_alerts(
            source,
            source_module=source_module,
            source_report=source_report,
            reporting_period=reporting_period,
            generated_at=generated_at,
        ))

    unique = {item["deduplication_key"]: item for item in candidates}
    alerts = _merge_existing(list(unique.values()), _rows(existing_alerts or []), generated_at)
    counts = {severity.lower(): sum(1 for item in alerts if item["severity"] == severity) for severity in SEVERITIES}
    active_count = sum(1 for item in alerts if item["status"] in ACTIVE_STATUSES)

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
        "advisory_only": True,
        "summary": {
            "total_alerts": len(alerts),
            "active_alerts": active_count,
            "critical": counts["critical"],
            "high": counts["high"],
            "medium": counts["medium"],
            "low": counts["low"],
            "info": counts["info"],
            "warning_count": len(warnings),
        },
        "alerts": alerts,
        "warnings": warnings,
        "governance": {
            "decision_authority": "NONE",
            "capital_movement_allowed": False,
            "automatic_policy_changes_allowed": False,
            "next_workflow": "ENTERPRISE_DIVIDEND_REVIEW_WORKFLOW",
        },
    }


def render_enterprise_dividend_alerts_markdown(report: Mapping[str, Any]) -> str:
    summary = dict(report.get("summary") or {})
    lines = [
        "# Enterprise Dividend Alerts",
        "",
        f"- Module: `{report.get('module_name', MODULE_NAME)}`",
        f"- Version: `{report.get('module_version', MODULE_VERSION)}`",
        f"- Generated: `{report.get('generated_at_utc', '')}`",
        f"- Paper Trade Mode: `{str(bool(report.get('paper_trade_mode', True))).lower()}`",
        "",
        "## Alert Summary",
        "",
        f"- Total: {summary.get('total_alerts', 0)}",
        f"- Active: {summary.get('active_alerts', 0)}",
        f"- Critical: {summary.get('critical', 0)}",
        f"- High: {summary.get('high', 0)}",
        f"- Medium: {summary.get('medium', 0)}",
        f"- Low: {summary.get('low', 0)}",
        f"- Info: {summary.get('info', 0)}",
    ]
    for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
        lines.extend(["", f"## {severity.title()} Alerts", ""])
        rows = [item for item in report.get("alerts", []) if item.get("severity") == severity]
        if not rows:
            lines.append("None.")
        for item in rows:
            lines.extend([
                f"### {item.get('symbol')} — {item.get('alert_type')}",
                f"- Alert ID: `{item.get('alert_id')}`",
                f"- Status: `{item.get('status')}`",
                f"- Message: {item.get('message')}",
                f"- Recommended review action: {item.get('recommended_action')}",
                f"- Source: `{item.get('source_module')}` / `{item.get('source_report')}`",
                "",
            ])
    lines.extend(["## Warnings", ""])
    warnings = list(report.get("warnings") or [])
    lines.extend([f"- {item}" for item in warnings] or ["None."])
    lines.extend([
        "",
        "## Governance Notes",
        "",
        "This report is paper-only and advisory-only. It cannot place orders, contact a broker, move capital, or silently change policy.",
        "",
    ])
    return "\n".join(lines)


def write_enterprise_dividend_alerts(report: Mapping[str, Any], output_dir: str | Path = "results") -> dict[str, str]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / DEFAULT_OUTPUT_FILES["json"]
    markdown_path = directory / DEFAULT_OUTPUT_FILES["markdown"]
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_enterprise_dividend_alerts_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def build_and_write_enterprise_dividend_alerts(output_dir: str | Path = "results", **kwargs: Any) -> dict[str, Any]:
    report = build_enterprise_dividend_alerts(**kwargs)
    write_enterprise_dividend_alerts(report, output_dir)
    return report
