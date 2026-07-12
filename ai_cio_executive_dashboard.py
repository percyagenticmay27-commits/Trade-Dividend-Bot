"""AI CIO Executive Dashboard for the Trade Dividend Bot.

Builds a paper-only executive dashboard from existing portfolio, AI CIO decision,
Decision Journal, SGOV activity, confidence, event, and watchlist artifacts.
The module never places orders or communicates with a brokerage.
"""
from __future__ import annotations

import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "ai_cio_executive_dashboard"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_OUTPUT_FILES = {
    "json": "ai_cio_executive_dashboard.json",
    "markdown": "ai_cio_executive_dashboard.md",
    "html": "ai_cio_executive_dashboard.html",
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


def _title(value: Any) -> str:
    return str(value or "UNKNOWN").replace("_", " ").title()


def _allocation_strength(item: Mapping[str, Any]) -> float:
    explicit = item.get("ranking_score")
    if explicit is not None:
        return _number(explicit)
    return round(
        _number(item.get("capital_efficiency_score")) * 0.50
        + _number(item.get("decision_stability_score")) * 0.25
        + _number(item.get("evidence_confidence_score")) * 0.15
        + _number(item.get("risk_adjusted_contribution"), 50.0) * 0.10,
        4,
    )


def rank_allocations(allocations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for item in allocations:
        strategy = str(item.get("strategy") or item.get("symbol") or item.get("candidate_id") or "UNKNOWN").strip().upper()
        if not strategy:
            continue
        row = dict(item)
        row["strategy"] = strategy
        row["allocation_percent"] = round(_number(item.get("allocation_percent")), 4)
        row["ranking_score"] = _allocation_strength(item)
        row["status"] = str(item.get("status") or "MONITOR").upper()
        row["ai_cio_verdict"] = str(item.get("ai_cio_verdict") or item.get("verdict") or "REVIEW").strip()
        row["why_this_allocation"] = str(item.get("why_this_allocation") or item.get("explanation") or "No allocation explanation is available.").strip()
        ranked.append(row)
    ranked.sort(key=lambda value: (value["strategy"] == "SGOV", -value["ranking_score"], -value["allocation_percent"]))
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    return ranked


def build_ai_cio_executive_dashboard(
    *,
    portfolio_summary: Optional[Mapping[str, Any]] = None,
    allocations: Optional[Sequence[Mapping[str, Any]]] = None,
    ai_cio_decision: Optional[Mapping[str, Any]] = None,
    sgov_notifications: Optional[Sequence[Mapping[str, Any]]] = None,
    decision_history: Optional[Sequence[Mapping[str, Any]]] = None,
    upcoming_events: Optional[Sequence[Mapping[str, Any]]] = None,
    watchlist: Optional[Sequence[Mapping[str, Any]]] = None,
    analysis_confidence: Optional[Mapping[str, Any]] = None,
    portfolio_health: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Build the executive dashboard payload from existing read-only artifacts."""
    summary = dict(portfolio_summary or {})
    decision = dict(ai_cio_decision or {})
    confidence = dict(analysis_confidence or {})
    health = dict(portfolio_health or {})
    ranked = rank_allocations(list(allocations or []))

    portfolio_value = _number(summary.get("portfolio_value"))
    growth = _number(summary.get("capital_appreciation", summary.get("growth")))
    income = _number(summary.get("income", summary.get("projected_annual_income")))
    total_wealth = _number(summary.get("total_wealth"), portfolio_value + growth + income)
    sgov_allocation = sum(row["allocation_percent"] for row in ranked if row["strategy"] == "SGOV")

    warnings: list[str] = []
    if not ranked:
        warnings.append("No capital allocations were supplied.")
    if not decision:
        warnings.append("No AI CIO decision was supplied.")

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
        "portfolio_summary": {
            "portfolio_value": round(portfolio_value, 2),
            "total_wealth": round(total_wealth, 2),
            "capital_appreciation": round(growth, 2),
            "projected_annual_income": round(income, 2),
            "sgov_reserve_percent": round(sgov_allocation, 4),
            "active_allocation_count": sum(1 for row in ranked if row["strategy"] != "SGOV"),
            "market_regime": str(summary.get("market_regime") or decision.get("market_regime") or "UNKNOWN").upper(),
            "portfolio_health": str(health.get("overall_health") or summary.get("portfolio_health") or "UNKNOWN").upper(),
            "autonomy_level": str(decision.get("autonomy_level") or "LEVEL_1_ADVISOR").upper(),
        },
        "capital_allocation_rankings": ranked,
        "ai_cio_verdict": {
            "final_capital_action": str(decision.get("final_capital_action") or "REVIEW").upper(),
            "current_candidate_id": decision.get("current_candidate_id"),
            "challenger_candidate_id": decision.get("challenger_candidate_id"),
            "verdict": str(decision.get("ai_cio_verdict") or "No AI CIO verdict is available.").strip(),
            "decision_stability_score": _number(decision.get("decision_stability_score")),
            "decision_stability_label": str(decision.get("decision_stability_label") or "UNKNOWN").upper(),
            "evidence_confidence_score": _number(decision.get("evidence_confidence_score")),
            "evidence_confidence_label": str(decision.get("evidence_confidence_label") or "UNKNOWN").upper(),
            "automatic_paper_action_authorized": bool(decision.get("automatic_paper_action_authorized", False)),
            "investor_override_available": bool(decision.get("investor_override_available", True)),
        },
        "sgov_notifications": [dict(item) for item in (sgov_notifications or [])],
        "analysis_confidence": confidence,
        "portfolio_health": health,
        "decision_history": [dict(item) for item in (decision_history or [])][-10:],
        "upcoming_events": [dict(item) for item in (upcoming_events or [])],
        "watchlist": [dict(item) for item in (watchlist or [])],
        "warnings": warnings,
        "errors": [],
    }


def format_dashboard_markdown(report: Mapping[str, Any]) -> str:
    summary = dict(report.get("portfolio_summary") or {})
    verdict = dict(report.get("ai_cio_verdict") or {})
    lines = [
        "# AI CIO Executive Dashboard",
        "",
        "## Portfolio Summary",
        "",
        f"- **Portfolio Value:** ${_number(summary.get('portfolio_value')):,.2f}",
        f"- **Total Wealth:** ${_number(summary.get('total_wealth')):,.2f}",
        f"- **Capital Appreciation:** ${_number(summary.get('capital_appreciation')):,.2f}",
        f"- **Projected Annual Income:** ${_number(summary.get('projected_annual_income')):,.2f}",
        f"- **SGOV Reserve:** {_number(summary.get('sgov_reserve_percent')):.2f}%",
        f"- **Market Regime:** {_title(summary.get('market_regime'))}",
        f"- **Portfolio Health:** {_title(summary.get('portfolio_health'))}",
        f"- **Operating Mode:** {_title(summary.get('autonomy_level'))}",
        "",
        "## Capital Allocation Rankings",
        "",
        "| Rank | Allocation | Portfolio % | Status | AI CIO Verdict |",
        "|---:|---|---:|---|---|",
    ]
    for row in report.get("capital_allocation_rankings", []):
        lines.append(
            f"| {row.get('rank')} | {row.get('strategy')} | {_number(row.get('allocation_percent')):.2f}% | "
            f"{_title(row.get('status'))} | {row.get('ai_cio_verdict')} |"
        )

    lines.extend([
        "",
        "## AI CIO Verdict",
        "",
        f"**Capital Action:** {_title(verdict.get('final_capital_action'))}",
        "",
        str(verdict.get("verdict") or "No verdict is available."),
        "",
        "## SGOV Notifications",
        "",
    ])
    notifications = list(report.get("sgov_notifications") or [])
    if not notifications:
        lines.append("No positions are currently parked in SGOV for a special protection or replacement reason.")
    else:
        lines.extend(["| Source | Allocation | Reason | Status | Next Review |", "|---|---:|---|---|---|"])
        for item in notifications:
            lines.append(
                f"| {item.get('source_strategy', item.get('source', 'Unknown'))} | "
                f"{_number(item.get('allocation_percent')):.2f}% | {item.get('reason', 'Not provided')} | "
                f"{item.get('status', 'Pending')} | {item.get('next_review', 'Not scheduled')} |"
            )

    lines.extend(["", "## Analysis Confidence", ""])
    confidence = dict(report.get("analysis_confidence") or {})
    lines.append(str(confidence.get("summary") or "Analysis confidence details are not available."))

    lines.extend(["", "## Recent Decision History", ""])
    history = list(report.get("decision_history") or [])
    if not history:
        lines.append("No recent AI CIO decisions are available.")
    else:
        for item in reversed(history):
            lines.append(f"- **{item.get('date', item.get('generated_at_utc', 'Unknown date'))}:** {item.get('summary', item.get('reason', 'Decision recorded.'))}")

    lines.extend(["", "## Upcoming Events", ""])
    events = list(report.get("upcoming_events") or [])
    if not events:
        lines.append("No upcoming portfolio events were supplied.")
    else:
        for item in events:
            lines.append(f"- **{item.get('event', item.get('name', 'Event'))}:** {item.get('when', item.get('date', 'Date unavailable'))}")

    lines.extend(["", "## AI CIO Watchlist", ""])
    watched = list(report.get("watchlist") or [])
    if not watched:
        lines.append("No watchlist candidates were supplied.")
    else:
        lines.extend(["| Candidate | Status | Reason |", "|---|---|---|"])
        for item in watched:
            lines.append(f"| {item.get('symbol', item.get('candidate_id', 'Unknown'))} | {item.get('status', 'Monitor')} | {item.get('reason', 'Not provided')} |")

    lines.extend([
        "",
        "## Paper-Only Safety",
        "",
        "This dashboard is reporting-only and paper-only. It does not place orders or communicate with a brokerage.",
        "",
    ])
    return "\n".join(lines)


def format_dashboard_html(report: Mapping[str, Any]) -> str:
    markdown = format_dashboard_markdown(report)
    escaped = html.escape(markdown)
    return f"""<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>AI CIO Executive Dashboard</title>
<style>
body{{font-family:Arial,sans-serif;margin:0;background:#f4f6f8;color:#172033}}
header{{background:#111a2b;color:white;padding:24px 32px}}
main{{max-width:1200px;margin:24px auto;background:white;padding:28px;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.08)}}
pre{{white-space:pre-wrap;font-family:Arial,sans-serif;line-height:1.5}}
</style>
</head>
<body><header><h1>AI CIO Executive Dashboard</h1><p>Paper-only portfolio intelligence</p></header><main><pre>{escaped}</pre></main></body></html>"""


def write_ai_cio_executive_dashboard(
    payload: Mapping[str, Any],
    root_path: str = ".",
    output_files: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    report = build_ai_cio_executive_dashboard(**dict(payload))
    root = Path(root_path)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    (root / files["json"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_dashboard_markdown(report), encoding="utf-8")
    (root / files["html"]).write_text(format_dashboard_html(report), encoding="utf-8")
    return report


if __name__ == "__main__":
    sample = {
        "portfolio_summary": {
            "portfolio_value": 500.0,
            "capital_appreciation": 0.10,
            "projected_annual_income": 19.25,
            "market_regime": "BULL",
            "portfolio_health": "GOOD",
        },
        "allocations": [
            {"strategy": "AMDW + PLTU", "allocation_percent": 45, "capital_efficiency_score": 84.3, "decision_stability_score": 82.7, "evidence_confidence_score": 94, "status": "STRONG", "ai_cio_verdict": "Continue Holding"},
            {"strategy": "QQQI + TQQQ", "allocation_percent": 35, "capital_efficiency_score": 80.5, "decision_stability_score": 79, "evidence_confidence_score": 91, "status": "STABLE", "ai_cio_verdict": "Continue Holding"},
            {"strategy": "SGOV", "allocation_percent": 20, "capital_efficiency_score": 50, "status": "RESERVE", "ai_cio_verdict": "Reserve"},
        ],
        "ai_cio_decision": {
            "final_capital_action": "KEEP",
            "current_candidate_id": "AMDW + PLTU",
            "challenger_candidate_id": "AMDW + GGLL",
            "ai_cio_verdict": "Recommendation: Continue holding AMDW + PLTU. The strongest challenger remains below the replacement threshold after considering Decision Stability, Evidence Confidence, market conditions, and Portfolio Turnover.",
            "decision_stability_score": 82.7,
            "decision_stability_label": "STABLE",
            "evidence_confidence_score": 94,
            "evidence_confidence_label": "VERY_HIGH",
            "market_regime": "BULL",
            "autonomy_level": "LEVEL_1_ADVISOR",
        },
        "sgov_notifications": [],
        "analysis_confidence": {"summary": "Overall Analysis Confidence is Very High. Market, portfolio, and decision evidence are consistent."},
        "decision_history": [{"date": "2026-07-12", "summary": "Continued holding AMDW + PLTU because the challenger improvement remained below the replacement threshold."}],
        "upcoming_events": [{"event": "Portfolio Review", "when": "Tomorrow after market close"}],
        "watchlist": [{"symbol": "AMDW + GGLL", "status": "Challenger", "reason": "Capital Efficiency Score is improving but has not cleared the replacement threshold."}],
    }
    result = write_ai_cio_executive_dashboard(sample)
    print(f"AI CIO Executive Dashboard: {len(result['capital_allocation_rankings'])} allocations")
