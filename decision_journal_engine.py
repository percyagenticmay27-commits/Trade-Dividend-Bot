"""Decision Journal Engine for the paper-only AI CIO.

Records every AI CIO recommendation and paper-portfolio action as an immutable,
auditable journal entry. This module never places orders or communicates with a broker.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "decision_journal_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_OUTPUT_FILES = {
    "json": "decision_journal.json",
    "markdown": "decision_journal.md",
}

VALID_INVESTOR_RESPONSES = {"NONE", "APPROVED", "REJECTED", "DEFERRED", "OVERRIDDEN", "REVERT_REQUESTED"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _copy_mapping(value: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    return dict(value or {})


def build_decision_journal_entry(
    *,
    ai_cio_decision: Mapping[str, Any],
    portfolio_before: Mapping[str, Any],
    portfolio_after: Optional[Mapping[str, Any]] = None,
    supporting_evidence: Optional[Mapping[str, Any]] = None,
    investor_response: str = "NONE",
    investor_note: str = "",
    applied_to_paper_portfolio: bool = False,
    previous_entry_id: str = "",
    timestamp_utc: str = "",
) -> dict[str, Any]:
    """Build one immutable decision-journal entry."""
    if not isinstance(ai_cio_decision, Mapping):
        raise ValueError("ai_cio_decision must be a mapping")
    if not isinstance(portfolio_before, Mapping):
        raise ValueError("portfolio_before must be a mapping")

    response = str(investor_response or "NONE").strip().upper()
    if response not in VALID_INVESTOR_RESPONSES:
        raise ValueError("invalid investor_response")

    action = str(ai_cio_decision.get("final_capital_action", "KEEP")).upper()
    generated_at = timestamp_utc or _now()
    after = _copy_mapping(portfolio_after)
    before = _copy_mapping(portfolio_before)

    return {
        "entry_id": str(uuid.uuid4()),
        "previous_entry_id": str(previous_entry_id or "") or None,
        "recorded_at_utc": generated_at,
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
        "autonomy_level": str(ai_cio_decision.get("autonomy_level", "LEVEL_1_ADVISOR")),
        "final_capital_action": action,
        "decision_reason": str(ai_cio_decision.get("decision_reason", "UNKNOWN")),
        "ai_cio_verdict": str(ai_cio_decision.get("ai_cio_verdict", "")),
        "current_candidate_id": ai_cio_decision.get("current_candidate_id"),
        "challenger_candidate_id": ai_cio_decision.get("challenger_candidate_id"),
        "capital_efficiency_score_difference": ai_cio_decision.get("capital_efficiency_score_difference"),
        "decision_stability_score": ai_cio_decision.get("decision_stability_score"),
        "decision_stability_label": ai_cio_decision.get("decision_stability_label"),
        "evidence_confidence_score": ai_cio_decision.get("evidence_confidence_score"),
        "evidence_confidence_label": ai_cio_decision.get("evidence_confidence_label"),
        "market_regime": ai_cio_decision.get("market_regime"),
        "investment_policy_compliant": bool(ai_cio_decision.get("investment_policy_compliant", False)),
        "policy_action_allowed": bool(ai_cio_decision.get("policy_action_allowed", False)),
        "automatic_paper_action_authorized": bool(ai_cio_decision.get("automatic_paper_action_authorized", False)),
        "investor_override_available": bool(ai_cio_decision.get("investor_override_available", True)),
        "investor_response": response,
        "investor_note": str(investor_note or ""),
        "applied_to_paper_portfolio": bool(applied_to_paper_portfolio),
        "portfolio_before": before,
        "portfolio_after": after,
        "supporting_evidence": _copy_mapping(supporting_evidence),
        "warnings": list(ai_cio_decision.get("warnings", [])),
        "errors": [],
    }


def append_decision_journal_entry(
    entry: Mapping[str, Any],
    *,
    journal_path: str = DEFAULT_OUTPUT_FILES["json"],
) -> dict[str, Any]:
    """Append an entry to the local JSON journal without altering prior entries."""
    if not isinstance(entry, Mapping):
        raise ValueError("entry must be a mapping")

    path = Path(journal_path)
    journal: dict[str, Any] = {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "paper_trade_mode": True,
        "entries": [],
    }
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8") or "{}")
        if isinstance(loaded, Mapping):
            journal.update(dict(loaded))
            journal["entries"] = list(loaded.get("entries", []))

    journal["entries"].append(dict(entry))
    journal["entry_count"] = len(journal["entries"])
    journal["latest_entry_id"] = entry.get("entry_id")
    journal["updated_at_utc"] = _now()
    path.write_text(json.dumps(journal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return journal


def format_decision_journal_markdown(entries: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "# AI CIO Decision Journal",
        "",
        "Every entry records what the AI CIO decided, why it decided it, and whether the paper portfolio changed.",
        "",
    ]
    for entry in reversed(list(entries)):
        lines.extend([
            f"## {entry.get('recorded_at_utc', 'Unknown time')} — {str(entry.get('final_capital_action', 'UNKNOWN')).replace('_', ' ').title()}",
            "",
            f"- **Current Allocation:** {entry.get('current_candidate_id') or 'Not available'}",
            f"- **Best Challenger:** {entry.get('challenger_candidate_id') or 'No qualified challenger'}",
            f"- **Decision Stability Score:** {entry.get('decision_stability_score', 'Not available')}",
            f"- **Evidence Confidence:** {entry.get('evidence_confidence_label') or 'Not available'}",
            f"- **Market Regime:** {entry.get('market_regime') or 'Unknown'}",
            f"- **Applied to Paper Portfolio:** {'Yes' if entry.get('applied_to_paper_portfolio') else 'No'}",
            f"- **Investor Response:** {str(entry.get('investor_response', 'NONE')).replace('_', ' ').title()}",
            "",
            "### Reason",
            "",
            str(entry.get("ai_cio_verdict") or "No explanation available."),
            "",
        ])
    lines.extend([
        "## Paper-Only Safety",
        "",
        "This journal records advisory and paper-only decisions. It does not place orders or communicate with a brokerage.",
        "",
    ])
    return "\n".join(lines)


def write_decision_journal(
    entry: Mapping[str, Any],
    *,
    root_path: str = ".",
    output_files: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    root = Path(root_path)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    journal = append_decision_journal_entry(entry, journal_path=str(root / files["json"]))
    (root / files["markdown"]).write_text(
        format_decision_journal_markdown(journal.get("entries", [])),
        encoding="utf-8",
    )
    return journal


if __name__ == "__main__":
    sample_decision = {
        "autonomy_level": "LEVEL_1_ADVISOR",
        "final_capital_action": "KEEP",
        "decision_reason": "CURRENT_ALLOCATION_REMAINS_PREFERRED",
        "ai_cio_verdict": "Recommendation: Continue holding AMDW + PLTU. The challenger has not provided a meaningful enough improvement to justify additional turnover.",
        "current_candidate_id": "AMDW + PLTU",
        "challenger_candidate_id": "AMDW + GGLL",
        "capital_efficiency_score_difference": 2.0,
        "decision_stability_score": 82.7,
        "decision_stability_label": "STABLE",
        "evidence_confidence_score": 94.0,
        "evidence_confidence_label": "VERY_HIGH",
        "market_regime": "BULL",
        "investment_policy_compliant": True,
        "policy_action_allowed": True,
        "automatic_paper_action_authorized": False,
        "investor_override_available": True,
    }
    sample_entry = build_decision_journal_entry(
        ai_cio_decision=sample_decision,
        portfolio_before={"AMDW + PLTU": 100.0},
        portfolio_after={"AMDW + PLTU": 100.0},
    )
    result = write_decision_journal(sample_entry)
    print(f"Decision Journal Entries: {result['entry_count']}")
