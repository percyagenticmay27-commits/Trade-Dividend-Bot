"""Authoritative current-state manager for paper portfolio allocations."""
from __future__ import annotations

import html
import json
import math
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "portfolio_lifecycle_manager"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_OUTPUT_FILES = {
    "json": "portfolio_lifecycle.json",
    "markdown": "portfolio_lifecycle.md",
    "html": "portfolio_lifecycle.html",
}

LIFECYCLE_STATES = {
    "CANDIDATE",
    "ACTIVE",
    "MONITORING",
    "PARKED_IN_SGOV",
    "REENTRY_PENDING",
    "REPLACEMENT_PENDING",
    "REPLACED",
    "CLOSED",
}

PENDING_STATES = {"REENTRY_PENDING", "REPLACEMENT_PENDING"}
CLOSED_STATES = {"REPLACED", "CLOSED"}

ALLOWED_TRANSITIONS = {
    "CANDIDATE": {"ACTIVE", "CLOSED"},
    "ACTIVE": {"MONITORING", "PARKED_IN_SGOV", "REPLACEMENT_PENDING", "REPLACED", "CLOSED"},
    "MONITORING": {"ACTIVE", "PARKED_IN_SGOV", "REPLACEMENT_PENDING", "REPLACED", "CLOSED"},
    "PARKED_IN_SGOV": {"REENTRY_PENDING", "REPLACEMENT_PENDING", "CLOSED"},
    "REENTRY_PENDING": {"ACTIVE", "REPLACEMENT_PENDING", "CLOSED"},
    "REPLACEMENT_PENDING": {"REPLACED", "PARKED_IN_SGOV", "ACTIVE", "CLOSED"},
    "REPLACED": set(),
    "CLOSED": set(),
}

EVENT_TO_STATE = {
    "ALLOCATION_OPENED": "ACTIVE",
    "EARNINGS_LOCK_STARTED": "PARKED_IN_SGOV",
    "CAPITAL_PARKED_IN_SGOV": "PARKED_IN_SGOV",
    "PROTECTION_CLEARED": "REENTRY_PENDING",
    "REENTRY_APPROVED": "ACTIVE",
    "REPLACEMENT_PREPARED": "REPLACEMENT_PENDING",
    "REPLACEMENT_APPLIED": "REPLACED",
    "ALLOCATION_CLOSED": "CLOSED",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _finite(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _percent(value: Any) -> float:
    return round(max(0.0, min(100.0, _finite(value))), 4)


def _state(value: Any) -> str:
    normalized = str(value or "CANDIDATE").strip().upper().replace(" ", "_")
    if normalized not in LIFECYCLE_STATES:
        raise ValueError(f"invalid lifecycle state: {normalized}")
    return normalized


def classify_allocation_maturity(days_held: Any) -> str:
    days = max(0, int(_finite(days_held)))
    if days <= 5:
        return "NEW"
    if days <= 20:
        return "DEVELOPING"
    if days <= 89:
        return "ESTABLISHED"
    return "LONG_TERM_LEADER"


def _days_held(opened_date: Any, as_of_date: Optional[str] = None) -> int:
    if not opened_date:
        return 0
    try:
        opened = date.fromisoformat(str(opened_date)[:10])
        as_of = date.fromisoformat(str(as_of_date)[:10]) if as_of_date else date.today()
    except ValueError:
        return 0
    return max(0, (as_of - opened).days)


def _record(raw: Mapping[str, Any], as_of_date: Optional[str] = None) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("allocation record must be a mapping")
    allocation_id = str(raw.get("allocation_id") or raw.get("strategy_name") or "").strip()
    if not allocation_id:
        raise ValueError("allocation_id is required")

    lifecycle_state = _state(raw.get("lifecycle_state", "CANDIDATE"))
    opened_date = str(raw.get("opened_date") or "")
    days_held = max(0, int(_finite(raw.get("days_held"), _days_held(opened_date, as_of_date))))
    maturity = classify_allocation_maturity(days_held)

    return {
        "allocation_id": allocation_id,
        "strategy_name": str(raw.get("strategy_name") or allocation_id),
        "component_symbols": [str(v).upper() for v in raw.get("component_symbols", []) if str(v).strip()],
        "strategy_type": str(raw.get("strategy_type") or "UNKNOWN").upper(),
        "sector_context": str(raw.get("sector_context") or "UNKNOWN"),
        "current_rank": max(0, int(_finite(raw.get("current_rank")))),
        "lifecycle_state": lifecycle_state,
        "current_allocation_percentage": _percent(raw.get("current_allocation_percentage")),
        "current_paper_value": round(max(0.0, _finite(raw.get("current_paper_value"))), 4),
        "sgov_linked_percentage": _percent(raw.get("sgov_linked_percentage")),
        "sgov_linked_value": round(max(0.0, _finite(raw.get("sgov_linked_value"))), 4),
        "portfolio_before_latest_change": deepcopy(raw.get("portfolio_before_latest_change", {})),
        "portfolio_after_latest_change": deepcopy(raw.get("portfolio_after_latest_change", {})),
        "opened_date": opened_date or None,
        "last_updated_at_utc": str(raw.get("last_updated_at_utc") or _now()),
        "last_reviewed_date": raw.get("last_reviewed_date"),
        "days_held": days_held,
        "allocation_maturity": maturity,
        "next_review": raw.get("next_review"),
        "original_thesis": str(raw.get("original_thesis") or ""),
        "current_thesis": str(raw.get("current_thesis") or raw.get("original_thesis") or ""),
        "capital_efficiency_score": round(_finite(raw.get("capital_efficiency_score")), 4),
        "decision_stability_score": _percent(raw.get("decision_stability_score")),
        "decision_stability_label": str(raw.get("decision_stability_label") or "UNKNOWN").upper(),
        "evidence_confidence_score": _percent(raw.get("evidence_confidence_score")),
        "evidence_confidence_label": str(raw.get("evidence_confidence_label") or "UNKNOWN").upper(),
        "market_regime": str(raw.get("market_regime") or "UNKNOWN").upper(),
        "current_recommendation": str(raw.get("current_recommendation") or "MONITOR").upper(),
        "natural_explanation": str(raw.get("natural_explanation") or "No allocation explanation is available."),
        "strongest_challenger": raw.get("strongest_challenger"),
        "challenger_score_difference": round(_finite(raw.get("challenger_score_difference")), 4),
        "replacement_eligible": bool(raw.get("replacement_eligible", False)),
        "earnings_lock_active": bool(raw.get("earnings_lock_active", False)),
        "confirmed_sale_signal_active": bool(raw.get("confirmed_sale_signal_active", False)),
        "risk_breach_active": bool(raw.get("risk_breach_active", False)),
        "invalid_data_protection_active": bool(raw.get("invalid_data_protection_active", False)),
        "sgov_reason": raw.get("sgov_reason"),
        "sgov_release_condition": raw.get("sgov_release_condition"),
        "sgov_move_authorization": raw.get("sgov_move_authorization"),
        "sgov_current_status": raw.get("sgov_current_status"),
        "candidate_competing_for_released_capital": raw.get("candidate_competing_for_released_capital"),
        "reentry_eligible": bool(raw.get("reentry_eligible", False)),
        "latest_decision_journal_entry_id": raw.get("latest_decision_journal_entry_id"),
        "prior_allocation_id": raw.get("prior_allocation_id"),
        "replacement_allocation_id": raw.get("replacement_allocation_id"),
        "sgov_parking_event_count": max(0, int(_finite(raw.get("sgov_parking_event_count")))),
        "replacement_count": max(0, int(_finite(raw.get("replacement_count")))),
        "review_count": max(0, int(_finite(raw.get("review_count")))),
        "event_history": deepcopy(list(raw.get("event_history", []))),
    }


def build_portfolio_lifecycle(
    allocations: Optional[Sequence[Mapping[str, Any]]] = None,
    *,
    as_of_date: Optional[str] = None,
) -> dict[str, Any]:
    records = [_record(item, as_of_date) for item in (allocations or [])]
    records.sort(key=lambda item: (item["current_rank"] == 0, item["current_rank"], item["allocation_id"]))
    return _assemble(records)


def _assemble(records: Sequence[Mapping[str, Any]], warnings: Optional[list[str]] = None) -> dict[str, Any]:
    items = [deepcopy(dict(item)) for item in records]
    active = [item for item in items if item["lifecycle_state"] in {"ACTIVE", "MONITORING"}]
    sgov = [item for item in items if item["lifecycle_state"] == "PARKED_IN_SGOV"]
    pending = [item for item in items if item["lifecycle_state"] in PENDING_STATES]
    closed = [item for item in items if item["lifecycle_state"] in CLOSED_STATES]
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "execution_enabled": False,
        "reporting_only": True,
        "portfolio_summary": {
            "allocation_count": len(items),
            "active_count": len(active),
            "sgov_count": len(sgov),
            "pending_count": len(pending),
            "closed_or_replaced_count": len(closed),
            "active_allocation_percentage": round(sum(_finite(v["current_allocation_percentage"]) for v in active), 4),
            "sgov_linked_percentage": round(sum(_finite(v["sgov_linked_percentage"]) for v in sgov), 4),
        },
        "allocations": items,
        "active_allocations": active,
        "sgov_allocations": sgov,
        "pending_allocations": pending,
        "closed_or_replaced_allocations": closed,
        "warnings": list(warnings or []),
        "errors": [],
    }


def apply_lifecycle_event(
    lifecycle: Mapping[str, Any],
    allocation_id: str,
    event: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(lifecycle, Mapping) or not isinstance(event, Mapping):
        raise ValueError("lifecycle and event must be mappings")
    event_type = str(event.get("event_type") or "").strip().upper()
    if not event_type:
        raise ValueError("event_type is required")

    records = [deepcopy(item) for item in lifecycle.get("allocations", [])]
    index = next((i for i, item in enumerate(records) if item.get("allocation_id") == allocation_id), None)
    if index is None:
        if event_type != "ALLOCATION_OPENED":
            raise KeyError(f"allocation not found: {allocation_id}")
        seed = dict(event.get("allocation", {}))
        seed["allocation_id"] = allocation_id
        seed["lifecycle_state"] = "CANDIDATE"
        records.append(_record(seed))
        index = len(records) - 1

    record = records[index]
    prior_state = _state(record.get("lifecycle_state"))
    target_state = EVENT_TO_STATE.get(event_type, prior_state)
    if target_state != prior_state and target_state not in ALLOWED_TRANSITIONS[prior_state]:
        raise ValueError(f"invalid lifecycle transition: {prior_state} -> {target_state}")

    record["lifecycle_state"] = target_state
    record["last_updated_at_utc"] = str(event.get("occurred_at_utc") or _now())
    record["latest_decision_journal_entry_id"] = event.get(
        "decision_journal_entry_id", record.get("latest_decision_journal_entry_id")
    )

    updates = dict(event.get("updates", {}))
    for key, value in updates.items():
        if key in record and key not in {"allocation_id", "event_history"}:
            record[key] = deepcopy(value)

    if event_type == "ALLOCATION_REVIEWED":
        record["review_count"] = int(record.get("review_count", 0)) + 1
        record["last_reviewed_date"] = event.get("review_date") or str(record["last_updated_at_utc"])[:10]
    elif event_type == "ALLOCATION_INCREASED":
        record["current_allocation_percentage"] = _percent(event.get("allocation_percentage", record["current_allocation_percentage"]))
    elif event_type == "ALLOCATION_REDUCED":
        record["current_allocation_percentage"] = _percent(event.get("allocation_percentage", record["current_allocation_percentage"]))
    elif event_type in {"EARNINGS_LOCK_STARTED", "CAPITAL_PARKED_IN_SGOV"}:
        record["sgov_parking_event_count"] = int(record.get("sgov_parking_event_count", 0)) + 1
        record["earnings_lock_active"] = event_type == "EARNINGS_LOCK_STARTED" or bool(event.get("earnings_lock_active", False))
        record["sgov_reason"] = event.get("reason") or record.get("sgov_reason") or "PROTECTION"
        record["sgov_release_condition"] = event.get("release_condition") or record.get("sgov_release_condition")
        record["sgov_move_authorization"] = event.get("authorization") or record.get("sgov_move_authorization")
        record["sgov_current_status"] = event.get("status") or "PARKED"
        record["sgov_linked_percentage"] = _percent(event.get("percentage", record.get("current_allocation_percentage")))
        record["current_allocation_percentage"] = 0.0
    elif event_type == "PROTECTION_CLEARED":
        record["earnings_lock_active"] = False
        record["risk_breach_active"] = False
        record["invalid_data_protection_active"] = False
        record["reentry_eligible"] = bool(event.get("reentry_eligible", False))
        record["sgov_current_status"] = "AWAITING_REQUALIFICATION"
    elif event_type == "REENTRY_APPROVED":
        record["reentry_eligible"] = True
        record["current_allocation_percentage"] = _percent(event.get("allocation_percentage"))
        record["sgov_linked_percentage"] = 0.0
        record["sgov_linked_value"] = 0.0
        record["sgov_current_status"] = "REDEPLOYED"
    elif event_type == "REPLACEMENT_PREPARED":
        record["replacement_eligible"] = True
        record["replacement_allocation_id"] = event.get("replacement_allocation_id")
    elif event_type == "REPLACEMENT_APPLIED":
        record["replacement_count"] = int(record.get("replacement_count", 0)) + 1
        record["replacement_allocation_id"] = event.get("replacement_allocation_id")
        record["current_allocation_percentage"] = 0.0

    history_entry = {
        "event_type": event_type,
        "occurred_at_utc": record["last_updated_at_utc"],
        "prior_state": prior_state,
        "new_state": target_state,
        "reason": event.get("reason"),
        "decision_journal_entry_id": event.get("decision_journal_entry_id"),
    }
    record.setdefault("event_history", []).append(history_entry)
    record = _record(record)
    records[index] = record
    return _assemble(records, list(lifecycle.get("warnings", [])))


def apply_decision_journal_entry(lifecycle: Mapping[str, Any], entry: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(entry, Mapping):
        raise ValueError("journal entry must be a mapping")
    allocation_id = str(entry.get("current_allocation_id") or entry.get("current_candidate_id") or "").strip()
    if not allocation_id:
        raise ValueError("journal entry must identify the current allocation")

    action = str(entry.get("final_capital_action") or entry.get("decision") or "KEEP").upper().replace(" ", "_")
    event_type = {
        "KEEP": "ALLOCATION_REVIEWED",
        "WAIT": "ALLOCATION_REVIEWED",
        "INCREASE": "ALLOCATION_INCREASED",
        "REDUCE": "ALLOCATION_REDUCED",
        "PARK_IN_SGOV": "CAPITAL_PARKED_IN_SGOV",
        "PREPARE_REPLACEMENT": "REPLACEMENT_PREPARED",
        "REPLACE": "REPLACEMENT_APPLIED",
        "REENTER": "REENTRY_APPROVED",
    }.get(action, "ALLOCATION_REVIEWED")

    event = {
        "event_type": event_type,
        "occurred_at_utc": entry.get("generated_at_utc") or entry.get("timestamp_utc") or _now(),
        "decision_journal_entry_id": entry.get("journal_entry_id") or entry.get("entry_id"),
        "reason": entry.get("ai_cio_verdict") or entry.get("reason") or entry.get("natural_explanation"),
        "replacement_allocation_id": entry.get("challenger_candidate_id"),
        "allocation_percentage": entry.get("allocation_percentage", 0.0),
        "updates": {
            "capital_efficiency_score": entry.get("current_capital_efficiency_score", 0.0),
            "decision_stability_score": entry.get("decision_stability_score", 0.0),
            "decision_stability_label": entry.get("decision_stability_label", "UNKNOWN"),
            "evidence_confidence_score": entry.get("evidence_confidence_score", 0.0),
            "evidence_confidence_label": entry.get("evidence_confidence_label", "UNKNOWN"),
            "market_regime": entry.get("market_regime", "UNKNOWN"),
            "current_recommendation": action,
            "natural_explanation": entry.get("ai_cio_verdict") or entry.get("reason") or "No explanation available.",
            "strongest_challenger": entry.get("challenger_candidate_id"),
            "challenger_score_difference": entry.get("capital_efficiency_score_difference", 0.0),
        },
    }
    return apply_lifecycle_event(lifecycle, allocation_id, event)


def get_allocation_state(lifecycle: Mapping[str, Any], allocation_id: str) -> Optional[dict[str, Any]]:
    for item in lifecycle.get("allocations", []):
        if str(item.get("allocation_id")) == str(allocation_id):
            return deepcopy(item)
    return None


def list_active_allocations(lifecycle: Mapping[str, Any]) -> list[dict[str, Any]]:
    return deepcopy(list(lifecycle.get("active_allocations", [])))


def list_sgov_allocations(lifecycle: Mapping[str, Any]) -> list[dict[str, Any]]:
    return deepcopy(list(lifecycle.get("sgov_allocations", [])))


def list_pending_allocations(lifecycle: Mapping[str, Any]) -> list[dict[str, Any]]:
    return deepcopy(list(lifecycle.get("pending_allocations", [])))


def format_portfolio_lifecycle_markdown(lifecycle: Mapping[str, Any]) -> str:
    summary = lifecycle.get("portfolio_summary", {})
    lines = [
        "# Portfolio Lifecycle Manager",
        "",
        "## Portfolio Lifecycle Summary",
        "",
        f"- **Total Allocations:** {summary.get('allocation_count', 0)}",
        f"- **Active Allocations:** {summary.get('active_count', 0)}",
        f"- **SGOV-Protected Allocations:** {summary.get('sgov_count', 0)}",
        f"- **Pending Allocations:** {summary.get('pending_count', 0)}",
        f"- **Closed or Replaced Allocations:** {summary.get('closed_or_replaced_count', 0)}",
        "",
        "## Active Allocations",
        "",
        "| Rank | Allocation | Portfolio % | Capital Efficiency Score | Decision Stability Score | Maturity | Recommendation |",
        "|---:|---|---:|---:|---:|---|---|",
    ]
    active = lifecycle.get("active_allocations", [])
    if active:
        for item in active:
            lines.append(
                f"| {item.get('current_rank') or '—'} | {item.get('strategy_name')} | "
                f"{_finite(item.get('current_allocation_percentage')):.2f}% | "
                f"{_finite(item.get('capital_efficiency_score')):.2f} | "
                f"{_finite(item.get('decision_stability_score')):.2f} / 100 | "
                f"{str(item.get('allocation_maturity')).replace('_', ' ').title()} | "
                f"{str(item.get('current_recommendation')).replace('_', ' ').title()} |"
            )
    else:
        lines.append("| — | No active allocations | 0.00% | — | — | — | — |")

    lines.extend(["", "## SGOV and Protection Activity", ""])
    sgov = lifecycle.get("sgov_allocations", [])
    if sgov:
        for item in sgov:
            lines.extend([
                f"### {item.get('strategy_name')}",
                "",
                f"- **Capital Parked:** {_finite(item.get('sgov_linked_percentage')):.2f}%",
                f"- **Reason:** {item.get('sgov_reason') or 'Not provided'}",
                f"- **Current Status:** {item.get('sgov_current_status') or 'Protected'}",
                f"- **Release Condition:** {item.get('sgov_release_condition') or 'Requalification required'}",
                f"- **Next Review:** {item.get('next_review') or 'Not scheduled'}",
                "",
            ])
    else:
        lines.extend(["No allocation capital is currently parked in SGOV for a special protection workflow.", ""])

    lines.extend(["## Re-entry and Replacement Pending", ""])
    pending = lifecycle.get("pending_allocations", [])
    if pending:
        for item in pending:
            lines.append(f"- **{item.get('strategy_name')}** — {str(item.get('lifecycle_state')).replace('_', ' ').title()}")
    else:
        lines.append("No allocations are currently awaiting re-entry or replacement.")

    lines.extend(["", "## Recently Replaced or Closed Allocations", ""])
    closed = lifecycle.get("closed_or_replaced_allocations", [])
    if closed:
        for item in closed:
            lines.append(
                f"- **{item.get('strategy_name')}** — {str(item.get('lifecycle_state')).title()}"
                + (f"; replaced by {item.get('replacement_allocation_id')}" if item.get("replacement_allocation_id") else "")
            )
    else:
        lines.append("No allocations have been replaced or closed in the current lifecycle record.")

    lines.extend(["", "## Next Reviews", ""])
    next_reviews = [item for item in lifecycle.get("allocations", []) if item.get("next_review")]
    if next_reviews:
        for item in next_reviews:
            lines.append(f"- **{item.get('strategy_name')}:** {item.get('next_review')}")
    else:
        lines.append("No next-review dates or triggers are currently recorded.")

    lines.extend([
        "",
        "## Paper-Only Safety",
        "",
        "This lifecycle record is advisory and paper-only. It maintains portfolio state and does not perform external execution.",
        "",
    ])
    return "\n".join(lines)


def format_portfolio_lifecycle_html(lifecycle: Mapping[str, Any]) -> str:
    markdown = format_portfolio_lifecycle_markdown(lifecycle)
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Portfolio Lifecycle</title>"
        "<style>body{font-family:Arial,sans-serif;max-width:1100px;margin:32px auto;padding:0 20px;"
        "line-height:1.5;background:#f4f6f8;color:#172033}pre{white-space:pre-wrap;background:white;padding:24px;"
        "border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,.08)}</style></head><body>"
        "<h1>Portfolio Lifecycle Manager</h1><pre>"
        + html.escape(markdown)
        + "</pre></body></html>"
    )


def write_portfolio_lifecycle(
    lifecycle: Mapping[str, Any],
    root_path: str = ".",
    output_files: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    if not isinstance(lifecycle, Mapping):
        raise ValueError("lifecycle must be a mapping")
    root = Path(root_path)
    root.mkdir(parents=True, exist_ok=True)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    (root / files["json"]).write_text(json.dumps(dict(lifecycle), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_portfolio_lifecycle_markdown(lifecycle), encoding="utf-8")
    (root / files["html"]).write_text(format_portfolio_lifecycle_html(lifecycle), encoding="utf-8")
    return dict(lifecycle)


def build_and_write_portfolio_lifecycle(
    allocations: Optional[Sequence[Mapping[str, Any]]] = None,
    *,
    as_of_date: Optional[str] = None,
    root_path: str = ".",
    output_files: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    lifecycle = build_portfolio_lifecycle(allocations, as_of_date=as_of_date)
    return write_portfolio_lifecycle(lifecycle, root_path=root_path, output_files=output_files)


if __name__ == "__main__":
    sample = [
        {
            "allocation_id": "ALLOC-001",
            "strategy_name": "AMDW + PLTU",
            "component_symbols": ["AMDW", "PLTU"],
            "strategy_type": "GROWTH_INCOME_PAIR",
            "sector_context": "Technology",
            "current_rank": 1,
            "lifecycle_state": "ACTIVE",
            "current_allocation_percentage": 45.0,
            "current_paper_value": 225.0,
            "opened_date": "2026-06-01",
            "capital_efficiency_score": 84.3,
            "decision_stability_score": 82.7,
            "decision_stability_label": "STABLE",
            "evidence_confidence_score": 94.0,
            "evidence_confidence_label": "VERY_HIGH",
            "market_regime": "BULL",
            "current_recommendation": "KEEP",
            "natural_explanation": "The current allocation remains preferred after considering expected Total Wealth, evidence quality, and portfolio stability.",
            "strongest_challenger": "AMDW + GGLL",
            "challenger_score_difference": 2.0,
            "next_review": "Next daily paper review",
        },
        {
            "allocation_id": "ALLOC-RESERVE",
            "strategy_name": "SGOV Reserve",
            "component_symbols": ["SGOV"],
            "strategy_type": "RESERVE",
            "current_rank": 2,
            "lifecycle_state": "ACTIVE",
            "current_allocation_percentage": 55.0,
            "current_paper_value": 275.0,
            "opened_date": "2026-06-01",
            "current_recommendation": "RESERVE",
        },
    ]
    result = build_and_write_portfolio_lifecycle(sample, as_of_date="2026-07-12")
    print(f"Portfolio Lifecycle Manager: {result['portfolio_summary']['allocation_count']} allocations")
