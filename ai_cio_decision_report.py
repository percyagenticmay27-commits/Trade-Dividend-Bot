"""Investor-facing formatter for AI CIO Decision Engine output.

Reads the AI CIO decision JSON and writes a clear Markdown report. This module
changes presentation only; it does not alter portfolio decisions or place orders.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Optional

MODULE_NAME = "ai_cio_decision_report"
MODULE_VERSION = "1.0.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_INPUT_FILE = "ai_cio_decision.json"
DEFAULT_OUTPUT_FILE = "ai_cio_decision.md"


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _title(value: Any) -> str:
    return str(value or "UNKNOWN").replace("_", " ").title()


def _recommendation_text(action: str, current: str, challenger: str) -> str:
    action = str(action or "KEEP").upper()
    if action == "KEEP":
        return f"Continue holding {current}"
    if action == "WAIT":
        return f"Continue holding {current} while monitoring {challenger}" if challenger else "Keep the current allocation unchanged while waiting for stronger evidence"
    if action == "REPLACE":
        return f"Replace {current} with {challenger}"
    if action == "PARK_IN_SGOV":
        return f"Move the affected {current} allocation to SGOV"
    if action == "PREPARE_REPLACEMENT":
        return f"Prepare a qualified replacement for {current}"
    if action == "REENTER":
        return f"Re-enter capital from SGOV into {challenger}"
    if action == "INCREASE":
        return f"Increase the allocation to {current}"
    if action == "REDUCE":
        return f"Reduce the allocation to {current}"
    return _title(action)


def _why_lines(report: Mapping[str, Any]) -> list[str]:
    current = str(report.get("current_candidate_id", "UNKNOWN"))
    challenger = str(report.get("challenger_candidate_id") or "")
    action = str(report.get("final_capital_action", "KEEP")).upper()
    difference = _number(report.get("capital_efficiency_score_difference"))
    stability_score = _number(report.get("decision_stability_score"))
    confidence_label = _title(report.get("evidence_confidence_label", "UNKNOWN")).lower()
    market_regime = _title(report.get("market_regime", "UNKNOWN")).lower()

    if action == "KEEP" and challenger and difference > 0:
        return [
            f"The strongest challenger ({challenger}) currently has a **Capital Efficiency Score** that is **{difference:.1f} points higher**.",
            "",
            "However:",
            "",
            "- the improvement is below the replacement threshold",
            f"- **Decision Stability** remains high ({stability_score:.1f} / 100)",
            f"- **Evidence Confidence** is {confidence_label}",
            f"- market conditions remain {market_regime}",
            "- replacing today would increase turnover without materially improving long-term **Total Wealth**.",
            "",
            f"**Recommendation:** Continue holding the current investment.",
        ]

    if action == "WAIT":
        return [
            "The available evidence does not yet support a discretionary portfolio change.",
            "",
            "The current allocation will remain in place while the challenger, market conditions, and Decision Stability are monitored for persistent improvement.",
            "",
            "**Recommendation:** Wait for stronger and more durable evidence.",
        ]

    if action == "REPLACE":
        return [
            f"The strongest challenger ({challenger}) has a **Capital Efficiency Score** advantage of **{difference:.1f} points**.",
            "",
            "The improvement passed the replacement threshold, Decision Stability permits the change, and Evidence Confidence is sufficient.",
            "",
            f"**Recommendation:** Replace {current} with {challenger} in the paper portfolio.",
        ]

    if action == "PARK_IN_SGOV":
        reasons = ", ".join(_title(item) for item in report.get("protection_reasons", [])) or "a mandatory protection condition"
        return [
            f"The allocation is affected by **{reasons}**.",
            "",
            "Capital protection takes priority until the condition clears and the investment qualifies again.",
            "",
            "**Recommendation:** Move the affected allocation to SGOV.",
        ]

    return [
        str(report.get("ai_cio_verdict", "No explanation is available.")),
        "",
        f"**Recommendation:** {_recommendation_text(action, current, challenger)}.",
    ]


def format_ai_cio_decision_report(report: Mapping[str, Any]) -> str:
    if not isinstance(report, Mapping):
        raise ValueError("report must be a mapping")

    current = str(report.get("current_candidate_id", "UNKNOWN"))
    challenger = str(report.get("challenger_candidate_id") or "No qualified challenger")
    action_code = str(report.get("final_capital_action", "KEEP")).upper()
    action = _title(action_code)
    recommendation = _recommendation_text(action_code, current, challenger)
    challenger_score = report.get("challenger_capital_efficiency_score")
    challenger_score_text = "Not available" if challenger_score is None else f"{_number(challenger_score):.2f}"
    difference = report.get("capital_efficiency_score_difference")
    difference_text = "Not available" if difference is None else f"{_number(difference):+.2f}"
    confidence = _title(report.get("evidence_confidence_label", "UNKNOWN"))
    stability = _title(report.get("decision_stability_label", "UNKNOWN"))
    regime = _title(report.get("market_regime", "UNKNOWN"))

    lines = [
        "# AI CIO Daily Decision",
        "",
        "## Recommendation",
        "",
        f"**{recommendation}**",
        "",
        "### Why?",
        "",
        *_why_lines(report),
        "",
        "## Compare Candidates",
        "",
        "| Fields | Current | Challenger |",
        "|---|---:|---:|",
        f"| Investment | {current} | {challenger} |",
        f"| Capital Efficiency Score | {_number(report.get('current_capital_efficiency_score')):.2f} | {challenger_score_text} |",
        f"| Capital Efficiency Score Difference | — | {difference_text} |",
        f"| Decision Stability Score | {_number(report.get('decision_stability_score')):.2f} / 100 ({stability}) | Not yet established |",
        f"| Evidence Confidence | {confidence} ({_number(report.get('evidence_confidence_score')):.2f} / 100) | Requires continued confirmation |",
        f"| Market Regime | {regime} | {regime} |",
        f"| Portfolio Action | {action} | Monitor |",
        "",
        "## Investment Policy Review",
        "",
        f"- **Investment Policy Compliant:** {'Yes' if report.get('investment_policy_compliant') else 'No'}",
        f"- **Policy Action Allowed:** {'Yes' if report.get('policy_action_allowed') else 'No'}",
        f"- **Automatic Paper Action Authorized:** {'Yes' if report.get('automatic_paper_action_authorized') else 'No'}",
        f"- **Investor Override Available:** {'Yes' if report.get('investor_override_available') else 'No'}",
        "",
        "## Analysis Confidence",
        "",
        f"Evidence Confidence is **{confidence} ({_number(report.get('evidence_confidence_score')):.2f} / 100)**. Decision Stability is **{_number(report.get('decision_stability_score')):.2f} / 100 ({stability})**.",
        "",
        "## Decision Summary",
        "",
        f"- **Current Investment:** {current}",
        f"- **Best Challenger:** {challenger}",
        f"- **Final Capital Action:** {action}",
        f"- **Decision Reason:** {_title(report.get('decision_reason'))}",
        f"- **Market Regime:** {regime}",
        "",
        "## Paper-Only Safety",
        "",
        "This decision is advisory and paper-only. It does not place orders or communicate with a brokerage.",
        "",
    ]
    return "\n".join(lines)


def write_ai_cio_decision_report(
    report: Mapping[str, Any],
    root_path: str = ".",
    output_file: str = DEFAULT_OUTPUT_FILE,
) -> Path:
    output_path = Path(root_path) / output_file
    output_path.write_text(format_ai_cio_decision_report(report), encoding="utf-8")
    return output_path


def build_report_from_json(
    root_path: str = ".",
    input_file: str = DEFAULT_INPUT_FILE,
    output_file: str = DEFAULT_OUTPUT_FILE,
) -> Path:
    root = Path(root_path)
    payload = json.loads((root / input_file).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("AI CIO decision JSON must contain an object")
    return write_ai_cio_decision_report(payload, root_path=root_path, output_file=output_file)


if __name__ == "__main__":
    path = build_report_from_json()
    print(f"AI CIO report written: {path}")
