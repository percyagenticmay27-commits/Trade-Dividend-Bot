"""Paper-only AI CIO Weekly Board Letter.

Combines existing portfolio, wealth, decision, lifecycle, replacement, earnings,
market, risk, and self-assessment outputs into one investor-facing weekly report.
"""
from __future__ import annotations

import html
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "ai_cio_weekly_board_letter"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_OUTPUT_FILES = {
    "json": "ai_cio_weekly_board_letter.json",
    "markdown": "ai_cio_weekly_board_letter.md",
    "html": "ai_cio_weekly_board_letter.html",
}

DETAILS = {
    "total_wealth": {
        "label": "Total Wealth",
        "definition": "The combined weekly effect of capital growth, income, SGOV interest, protection value, replacement value, and turnover cost.",
        "calculation": "Uses the Net Total Wealth Contribution supplied by the Wealth Attribution Engine.",
        "why_it_matters": "It is the AI CIO's primary objective: maximize long-term growth plus income while controlling risk and churn.",
    },
    "portfolio_risk": {
        "label": "Portfolio Risk",
        "definition": "The portfolio's combined structural, concentration, event, leverage, reserve, and decision risk.",
        "calculation": "Uses the Portfolio Risk Intelligence score, label, and Risk Momentum.",
        "why_it_matters": "Strong opportunities must still fit within a healthy portfolio.",
    },
    "market_environment": {
        "label": "Market Environment",
        "definition": "The regime, breadth, volatility, macro, news, and sector context surrounding the portfolio.",
        "calculation": "Uses the Market Intelligence Center's score, label, and regime.",
        "why_it_matters": "Market context supports evidence but never creates sector quotas or capital entitlement.",
    },
    "decision_quality": {
        "label": "Decision Quality",
        "definition": "The quality and stability of recent AI CIO paper decisions.",
        "calculation": "Uses self-assessment, Decision Stability, Evidence Confidence, replacement outcomes, and turnover behavior.",
        "why_it_matters": "The AI CIO must measure whether its own process improves Total Wealth.",
    },
    "sgov_activity": {
        "label": "SGOV Activity",
        "definition": "Capital temporarily held in SGOV for reserve, protection, earnings, or pending redeployment.",
        "calculation": "Counts protected lifecycle records and earnings-related SGOV actions.",
        "why_it_matters": "SGOV is protected capital with a documented reason and release condition.",
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


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else []


def _pick(source: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in source and source[key] is not None:
            return source[key]
    return default


def _money(value: Any) -> str:
    number = _number(value)
    return f"{'-' if number < 0 else ''}${abs(number):,.2f}"


def _percent(value: Any) -> str:
    number = _number(value)
    return f"{'+' if number > 0 else ''}{number:.2f}%"


def build_ai_cio_weekly_board_letter(
    *,
    week_start: Optional[str] = None,
    week_end: Optional[str] = None,
    portfolio_summary: Optional[Mapping[str, Any]] = None,
    wealth_attribution: Optional[Mapping[str, Any]] = None,
    decision_journal: Optional[Mapping[str, Any]] = None,
    portfolio_lifecycle: Optional[Mapping[str, Any]] = None,
    opportunity_replacement: Optional[Mapping[str, Any]] = None,
    earnings_events: Optional[Mapping[str, Any]] = None,
    market_intelligence: Optional[Mapping[str, Any]] = None,
    portfolio_risk: Optional[Mapping[str, Any]] = None,
    performance_analytics: Optional[Mapping[str, Any]] = None,
    upcoming_items: Optional[Sequence[Mapping[str, Any]]] = None,
) -> dict[str, Any]:
    portfolio = _mapping(portfolio_summary)
    wealth = _mapping(wealth_attribution)
    journal = _mapping(decision_journal)
    lifecycle = _mapping(portfolio_lifecycle)
    replacement = _mapping(opportunity_replacement)
    earnings = _mapping(earnings_events)
    market = _mapping(market_intelligence)
    risk = _mapping(portfolio_risk)
    analytics = _mapping(performance_analytics)

    warnings = []
    for label, source in (("portfolio summary", portfolio), ("wealth attribution", wealth), ("market intelligence", market), ("portfolio risk", risk)):
        if not source:
            warnings.append(f"Missing optional {label}; neutral or unavailable wording was used.")

    start = week_start or str(_pick(portfolio, "week_start", "period_start", default="Unknown"))
    end = week_end or str(_pick(portfolio, "week_end", "period_end", default=date.today().isoformat()))
    portfolio_value = _number(_pick(portfolio, "portfolio_value", "total_portfolio_value", default=0.0))
    wealth_amount = _number(_pick(wealth, "net_total_wealth_contribution", "net_decision_value", "total_wealth_amount", default=0.0))
    wealth_percent = _number(_pick(wealth, "net_total_wealth_percent", "total_wealth_percent", default=0.0))
    primary_driver = str(_pick(wealth, "primary_driver", default="Not available"))
    largest_drag = str(_pick(wealth, "largest_drag", default="None identified"))

    market_label = str(_pick(market, "overall_market_intelligence_label", "overall_label", default="Unknown")).replace("_", " ").title()
    market_score = _number(_pick(market, "overall_market_intelligence_score", "overall_score", default=0.0))
    market_regime = str(_pick(market, "market_regime", "regime", default="Unknown")).replace("_", " ").title()

    risk_label = str(_pick(risk, "overall_portfolio_risk_label", "overall_risk_label", default="Unknown")).replace("_", " ").title()
    risk_score = _number(_pick(risk, "overall_portfolio_risk_score", "overall_risk_score", default=0.0))
    risk_momentum = str(_pick(_mapping(risk.get("risk_momentum")), "direction", default="Stable")).replace("_", " ").title()

    self_score = _number(_pick(analytics, "ai_cio_self_assessment_score", "self_assessment_score", default=0.0))
    self_grade = str(_pick(analytics, "grade", "self_assessment_grade", default="N/A"))

    decisions = []
    for row in _sequence(_pick(journal, "entries", "decision_history", default=[]))[-10:]:
        if isinstance(row, Mapping):
            decisions.append({
                "action": str(_pick(row, "capital_action", "action", "decision", default="Review")),
                "reason": str(_pick(row, "reason", "explanation", default="No explanation supplied.")),
                "portfolio_changed": bool(_pick(row, "applied_to_paper_portfolio", "portfolio_changed", default=False)),
            })

    lifecycle_rows = [row for row in _sequence(_pick(lifecycle, "allocations", "records", default=[])) if isinstance(row, Mapping)]
    active = [row for row in lifecycle_rows if str(_pick(row, "lifecycle_status", "status", default="")).upper() in {"ACTIVE", "MONITORING"}]
    protected = [row for row in lifecycle_rows if str(_pick(row, "lifecycle_status", "status", default="")).upper() in {"PROTECTED", "PARKED_IN_SGOV", "SGOV"} or bool(row.get("is_sgov"))]

    earnings_actions = [row for row in _sequence(_pick(earnings, "actions", "earnings_actions", default=[])) if isinstance(row, Mapping)]
    earnings_protections = sum(1 for row in earnings_actions if "SGOV" in str(_pick(row, "recommendation", "action", default="")).upper())

    replacement_action = str(_pick(replacement, "recommendation", "action", "replacement_action", default="No replacement review supplied")).replace("_", " ").title()
    replacement_reason = str(_pick(replacement, "explanation", "reason", default="No replacement explanation supplied."))

    learning = []
    for item in _sequence(_pick(analytics, "improvement_findings", "findings", default=[]))[:5]:
        learning.append(str(_pick(item, "title", "finding", "recommended_review", default="")) if isinstance(item, Mapping) else str(item))
    learning = [item for item in learning if item] or ["Insufficient completed history for a new evidence-based learning conclusion."]

    upcoming = []
    for item in _sequence(upcoming_items):
        if isinstance(item, Mapping):
            upcoming.append({
                "event": str(_pick(item, "event", "title", "name", default="Review")),
                "date": str(_pick(item, "date", "when", default="Not supplied")),
                "importance": str(_pick(item, "importance", "priority", default="Normal")),
            })

    change_count = sum(1 for item in decisions if item["portfolio_changed"])
    last_decision = decisions[-1] if decisions else {"action": "No decision history available", "reason": "No decision records were supplied."}

    executive_summary = (
        f"During the week ending {end}, Net Total Wealth changed by {_money(wealth_amount)} ({_percent(wealth_percent)}). "
        f"The primary driver was {primary_driver}. Portfolio risk was {risk_label} ({risk_score:.2f}/100) and {risk_momentum.lower()}, "
        f"while market intelligence was {market_label} under a {market_regime} regime. "
        f"The AI CIO reviewed {len(decisions)} decision(s), including {change_count} paper portfolio change(s)."
    )
    commentary = (
        f"The portfolio remains opportunity-driven rather than sector-driven. The most recent decision was {last_decision['action']}. "
        f"{last_decision['reason']} The replacement review currently says {replacement_action}. {replacement_reason}"
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
        "week_start": start,
        "week_end": end,
        "portfolio_value": round(portfolio_value, 2),
        "executive_summary": executive_summary,
        "weekly_scorecard": {
            "net_total_wealth_amount": round(wealth_amount, 2),
            "net_total_wealth_percent": round(wealth_percent, 4),
            "primary_driver": primary_driver,
            "largest_drag": largest_drag,
            "portfolio_risk_label": risk_label,
            "portfolio_risk_score": round(risk_score, 4),
            "risk_momentum": risk_momentum,
            "market_environment_label": market_label,
            "market_intelligence_score": round(market_score, 4),
            "market_regime": market_regime,
            "ai_cio_self_assessment_score": round(self_score, 4),
            "ai_cio_self_assessment_grade": self_grade,
        },
        "decision_review": {
            "decisions_reviewed": len(decisions),
            "paper_changes": change_count,
            "holds_or_no_change": max(0, len(decisions) - change_count),
            "recent_decisions": decisions,
            "replacement_action": replacement_action,
            "replacement_reason": replacement_reason,
        },
        "portfolio_state": {
            "active_allocations": len(active),
            "sgov_or_protected_allocations": len(protected),
            "earnings_reviews": len(earnings_actions),
            "earnings_protections": earnings_protections,
        },
        "what_the_ai_cio_learned": learning,
        "next_week_watchlist": upcoming,
        "ai_cio_commentary": commentary,
        "governance": {
            "automatic_policy_changes_allowed": False,
            "investor_approval_required_for_policy_changes": True,
            "sector_allocation_entitlement": False,
            "html_ui_modernization_deferred": True,
        },
        "details": DETAILS,
        "warnings": warnings,
        "errors": [],
    }


def format_ai_cio_weekly_board_letter_markdown(report: Mapping[str, Any]) -> str:
    score = _mapping(report.get("weekly_scorecard"))
    review = _mapping(report.get("decision_review"))
    state = _mapping(report.get("portfolio_state"))
    lines = [
        "# AI CIO Weekly Board Letter", "",
        f"**Reporting Period:** {report.get('week_start', 'Unknown')} through {report.get('week_end', 'Unknown')}", "",
        "## Dear Investor,", "", str(report.get("executive_summary", "No executive summary available.")), "",
        "## Weekly Scorecard", "",
        "| Metric | Result | More... |", "|---|---:|---|",
        f"| Total Wealth | {_money(score.get('net_total_wealth_amount'))} ({_percent(score.get('net_total_wealth_percent'))}) | [More...](#total-wealth) |",
        f"| Portfolio Risk | {score.get('portfolio_risk_label', 'Unknown')} ({_number(score.get('portfolio_risk_score')):.2f}/100) | [More...](#portfolio-risk) |",
        f"| Market Environment | {score.get('market_environment_label', 'Unknown')} / {score.get('market_regime', 'Unknown')} | [More...](#market-environment) |",
        f"| Decision Quality | Grade {score.get('ai_cio_self_assessment_grade', 'N/A')} ({_number(score.get('ai_cio_self_assessment_score')):.2f}/100) | [More...](#decision-quality) |",
        f"| SGOV Activity | {state.get('sgov_or_protected_allocations', 0)} protected allocation(s) | [More...](#sgov-activity) |", "",
        "## What Happened This Week", "",
        f"- **Decisions reviewed:** {review.get('decisions_reviewed', 0)}",
        f"- **Paper portfolio changes:** {review.get('paper_changes', 0)}",
        f"- **Holds or no-change decisions:** {review.get('holds_or_no_change', 0)}",
        f"- **Replacement review:** {review.get('replacement_action', 'Not available')}",
        f"- **Earnings reviews:** {state.get('earnings_reviews', 0)}",
        f"- **Earnings protections:** {state.get('earnings_protections', 0)}", "",
        "## AI CIO Commentary", "", str(report.get("ai_cio_commentary", "No commentary available.")), "",
        "## What I Learned This Week", "",
    ]
    lines.extend(f"- {item}" for item in _sequence(report.get("what_the_ai_cio_learned")))
    lines.extend(["", "## Next Week", ""])
    upcoming = _sequence(report.get("next_week_watchlist"))
    if upcoming:
        lines.extend(["| Event | Date | Importance |", "|---|---|---|"])
        for item in upcoming:
            if isinstance(item, Mapping):
                lines.append(f"| {item.get('event', 'Review')} | {item.get('date', 'Unknown')} | {item.get('importance', 'Normal')} |")
    else:
        lines.append("No dated upcoming items were supplied. Existing lifecycle, earnings, risk, and replacement reviews remain active.")
    for detail in DETAILS.values():
        lines.extend(["", f"## {detail['label']}", "", f"**What it means:** {detail['definition']}", "", f"**How it is calculated:** {detail['calculation']}", "", f"**Why it matters:** {detail['why_it_matters']}"])
    lines.extend(["", "## Governance and Paper-Only Safety", "", "This letter is advisory and paper-only. It does not place orders, communicate with a brokerage, create sector quotas, or modify investment policy. Any policy change requires investor approval and separate shadow validation.", "", "Respectfully,", "", "**AI Chief Investment Officer**", ""])
    return "\n".join(lines)


def format_ai_cio_weekly_board_letter_html(report: Mapping[str, Any]) -> str:
    markdown = format_ai_cio_weekly_board_letter_markdown(report)
    return "<!doctype html><html><head><meta charset='utf-8'><title>AI CIO Weekly Board Letter</title><style>body{font-family:Arial,sans-serif;max-width:1100px;margin:0 auto;padding:32px;background:#f5f7fb;color:#172033}pre{white-space:pre-wrap;background:white;padding:30px;border-radius:14px;box-shadow:0 4px 18px rgba(0,0,0,.08);line-height:1.55}</style></head><body><pre>" + html.escape(markdown) + "</pre></body></html>"


def write_ai_cio_weekly_board_letter(payload: Mapping[str, Any], root_path: str = ".", output_files: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    report = build_ai_cio_weekly_board_letter(**dict(payload))
    root = Path(root_path)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    (root / files["json"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_ai_cio_weekly_board_letter_markdown(report), encoding="utf-8")
    (root / files["html"]).write_text(format_ai_cio_weekly_board_letter_html(report), encoding="utf-8")
    return report


def build_and_write_ai_cio_weekly_board_letter(payload: Mapping[str, Any], root_path: str = ".", output_files: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    return write_ai_cio_weekly_board_letter(payload, root_path, output_files)


if __name__ == "__main__":
    sample = {
        "week_start": "2026-07-06", "week_end": "2026-07-12",
        "portfolio_summary": {"portfolio_value": 500.00},
        "wealth_attribution": {"net_total_wealth_contribution": 39.20, "net_total_wealth_percent": 7.84, "primary_driver": "Capital Growth", "largest_drag": "Portfolio Turnover Cost"},
        "decision_journal": {"entries": [{"capital_action": "KEEP", "reason": "The challenger advantage remained below the replacement threshold.", "applied_to_paper_portfolio": False}, {"capital_action": "PARK IN SGOV", "reason": "AMDW + PLTU entered its earnings protection window.", "applied_to_paper_portfolio": True}]},
        "portfolio_lifecycle": {"allocations": [{"allocation_id": "QQQI + TQQQ", "lifecycle_status": "ACTIVE"}, {"allocation_id": "AMDW + PLTU", "lifecycle_status": "PROTECTED"}]},
        "opportunity_replacement": {"recommendation": "KEEP_CURRENT", "reason": "No challenger produced a meaningful and persistent improvement."},
        "earnings_events": {"actions": [{"allocation_id": "AMDW + PLTU", "recommendation": "PARK_IN_SGOV"}]},
        "market_intelligence": {"overall_market_intelligence_label": "SUPPORTIVE", "overall_market_intelligence_score": 73.5, "market_regime": "BULL"},
        "portfolio_risk": {"overall_portfolio_risk_label": "LOW", "overall_portfolio_risk_score": 24.8, "risk_momentum": {"direction": "STABLE"}},
        "performance_analytics": {"ai_cio_self_assessment_score": 95.7, "grade": "A", "improvement_findings": ["Continue collecting replacement outcomes before proposing threshold changes."]},
        "upcoming_items": [{"event": "Post-earnings requalification", "date": "2026-07-14", "importance": "High"}],
    }
    result = write_ai_cio_weekly_board_letter(sample)
    print(f"AI CIO Weekly Board Letter: {result['week_start']} through {result['week_end']}")
