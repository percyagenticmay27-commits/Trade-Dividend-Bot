"""Governed advisory review of AI CIO paper-allocation recommendations.

This service does not allocate capital, create allocation requests, activate strategies,
move money, contact a broker, or place orders. It converts existing advisory and risk
reports into an investor/governance review decision.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

MODULE_NAME = "capital_allocation_review_service"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
AUTOMATIC_APPROVAL_ENABLED = False

REQUIRED_INPUTS = ("ai_cio_portfolio_manager.json", "cross_strategy_risk.json")
ALLOWED_DECISIONS = {"APPROVE_FOR_INVESTOR_REVIEW", "HOLD", "REJECT"}


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(str(source))
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON input: {source}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {source}")
    return value


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _text(value: Any, default: str = "UNKNOWN") -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def build_capital_allocation_review(
    portfolio_manager: Mapping[str, Any],
    risk_report: Mapping[str, Any],
    *,
    review_policy: Optional[Mapping[str, Any]] = None,
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    policy = dict(review_policy or {})
    allowed_risk = {
        _text(item).upper()
        for item in policy.get("risk_levels_eligible_for_review", ["ACCEPTABLE", "WATCH"])
    }
    require_recommendations = bool(policy.get("require_recommendations", True))
    max_critical_findings = int(policy.get("max_critical_findings", 0))
    max_high_findings = int(policy.get("max_high_findings", 0))

    governance = portfolio_manager.get("governance", {})
    if not isinstance(governance, Mapping):
        governance = {}
    safe = (
        bool(governance.get("paper_trade_mode", portfolio_manager.get("paper_trade_mode", False)))
        and not bool(governance.get("live_trading_enabled", portfolio_manager.get("live_trading_enabled", True)))
        and not bool(governance.get("broker_execution_enabled", portfolio_manager.get("broker_execution_enabled", True)))
        and not bool(governance.get("capital_movement_enabled", False))
    )

    recommendations = _as_list(
        portfolio_manager.get("recommendations", portfolio_manager.get("strategy_recommendations", []))
    )
    blockers = [_text(item, "") for item in _as_list(portfolio_manager.get("blockers")) if _text(item, "")]
    warnings = [_text(item, "") for item in _as_list(portfolio_manager.get("warnings")) if _text(item, "")]

    risk_level = _text(
        risk_report.get("overall_risk", risk_report.get("risk_classification", risk_report.get("status")))
    ).upper()
    findings = _as_list(risk_report.get("findings", risk_report.get("risk_findings", [])))
    critical_count = 0
    high_count = 0
    normalized_findings: list[dict[str, Any]] = []
    for raw in findings:
        item = dict(raw) if isinstance(raw, Mapping) else {"message": _text(raw)}
        severity = _text(item.get("severity", item.get("risk_level", "WATCH"))).upper()
        if severity == "CRITICAL":
            critical_count += 1
        elif severity == "HIGH":
            high_count += 1
        item["severity"] = severity
        normalized_findings.append(item)

    reasons: list[str] = []
    if not safe:
        reasons.append("paper-safety governance validation failed")
    if blockers:
        reasons.extend(f"portfolio blocker: {message}" for message in blockers)
    if risk_level not in allowed_risk:
        reasons.append(f"risk level {risk_level} is not eligible for investor review")
    if critical_count > max_critical_findings:
        reasons.append("critical risk findings exceed review policy")
    if high_count > max_high_findings:
        reasons.append("high risk findings exceed review policy")
    if require_recommendations and not recommendations:
        reasons.append("no allocation recommendations are available")

    if not safe or critical_count > max_critical_findings or risk_level == "CRITICAL":
        decision = "REJECT"
    elif reasons:
        decision = "HOLD"
    else:
        decision = "APPROVE_FOR_INVESTOR_REVIEW"

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at_utc or _now_utc(),
        "decision": decision,
        "decision_allowed_values": sorted(ALLOWED_DECISIONS),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "automatic_approval_enabled": False,
        "summary": {
            "recommendation_count": len(recommendations),
            "portfolio_blocker_count": len(blockers),
            "portfolio_warning_count": len(warnings),
            "risk_level": risk_level,
            "risk_finding_count": len(normalized_findings),
            "critical_finding_count": critical_count,
            "high_finding_count": high_count,
            "paper_safe": safe,
        },
        "recommendations": recommendations,
        "risk_findings": normalized_findings,
        "warnings": warnings,
        "reasons": reasons,
        "governance": {
            "advisory_only": True,
            "investor_approval_required": True,
            "governance_review_required": True,
            "creates_allocation_request": False,
            "automatic_activation_allowed": False,
            "order_execution_allowed": False,
            "brokerage_communication_allowed": False,
            "capital_movement_allowed": False,
            "allocation_request_owner": "paper_capital_allocation.py",
        },
    }


def build_review_from_files(
    portfolio_manager_path: str | Path,
    risk_report_path: str | Path,
    *,
    review_policy_path: Optional[str | Path] = None,
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    policy = _load_json(review_policy_path) if review_policy_path else None
    return build_capital_allocation_review(
        _load_json(portfolio_manager_path),
        _load_json(risk_report_path),
        review_policy=policy,
        generated_at_utc=generated_at_utc,
    )


def write_capital_allocation_review_json(review: Mapping[str, Any], output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(review), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def render_capital_allocation_review_markdown(review: Mapping[str, Any]) -> str:
    summary = review.get("summary", {}) if isinstance(review.get("summary"), Mapping) else {}
    lines = [
        "# Capital Allocation Review",
        "",
        f"- Decision: **{review.get('decision', 'UNKNOWN')}**",
        f"- Risk Level: {summary.get('risk_level', 'UNKNOWN')}",
        f"- Recommendations: {summary.get('recommendation_count', 0)}",
        f"- Critical Findings: {summary.get('critical_finding_count', 0)}",
        f"- High Findings: {summary.get('high_finding_count', 0)}",
        f"- Paper Safe: {summary.get('paper_safe', False)}",
        "",
        "## Decision Reasons",
        "",
    ]
    reasons = _as_list(review.get("reasons"))
    lines.extend([f"- {item}" for item in reasons] or ["- No blocking reasons."])
    lines.extend([
        "",
        "## Governance",
        "",
        "- Advisory only",
        "- Investor approval required",
        "- Governance review required",
        "- Does not create an allocation request",
        "- No broker communication, order execution, or capital movement",
        "",
    ])
    return "\n".join(lines)


def write_capital_allocation_review_markdown(review: Mapping[str, Any], output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_capital_allocation_review_markdown(review), encoding="utf-8")
    return str(path)


def build_and_write_capital_allocation_review(
    portfolio_manager_path: str | Path,
    risk_report_path: str | Path,
    output_dir: str | Path = "results",
    *,
    review_policy_path: Optional[str | Path] = None,
    generated_at_utc: Optional[str] = None,
) -> dict[str, str]:
    review = build_review_from_files(
        portfolio_manager_path,
        risk_report_path,
        review_policy_path=review_policy_path,
        generated_at_utc=generated_at_utc,
    )
    directory = Path(output_dir)
    return {
        "json": write_capital_allocation_review_json(review, directory / "capital_allocation_review.json"),
        "markdown": write_capital_allocation_review_markdown(review, directory / "capital_allocation_review.md"),
    }
