"""Manual, paper-only review queue for Dividend suitability candidates."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "1.0"
STRATEGY_ID = "DIVIDEND-001"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return dict(payload)


def validate_suitability_report(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("strategy_id") != STRATEGY_ID:
        raise ValueError("suitability report must be schema 1.0 / DIVIDEND-001")
    locks = {
        "paper_trade_mode": True,
        "advisory_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "order_placement_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
    }
    if any(payload.get(key) is not expected for key, expected in locks.items()):
        raise ValueError("suitability report execution locks are not preserved")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("suitability candidates must be a list")
    return [dict(row) for row in candidates if isinstance(row, Mapping)]


def build_manual_review_queue(
    suitability_report: Mapping[str, Any], *, generated_at: str | None = None
) -> dict[str, Any]:
    candidates = validate_suitability_report(suitability_report)
    queue: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in candidates:
        base = {
            "underlying_symbol": row.get("underlying_symbol"),
            "income_symbol": row.get("income_symbol"),
            "mapping_type": row.get("mapping_type"),
            "suitability_status": row.get("suitability_status"),
            "suitability_score": row.get("suitability_score"),
            "decision_reasons": list(row.get("decision_reasons") or []),
            "suitability_evidence": row.get("suitability_evidence"),
            "manual_review_required": True,
            "operator_decision": None,
            "approved_for_paper_entry": False,
            "automatic_activation_allowed": False,
        }
        eligible = (
            row.get("suitability_status") == "ELIGIBLE_FOR_PAPER_REVIEW"
            and row.get("paper_review_allowed") is True
            and row.get("income_symbol")
        )
        if eligible:
            queue.append({
                **base,
                "queue_status": "PENDING_MANUAL_REVIEW",
                "review_checklist": [
                    "Confirm evidence remains current and complete.",
                    "Review dividend or distribution sustainability.",
                    "Review liquidity and concentration risk.",
                    "Confirm any later paper position size under DIVIDEND-001 authority.",
                    "Record an explicit operator decision in a separate approved workflow.",
                ],
            })
        else:
            excluded.append({
                **base,
                "queue_status": (
                    "WATCH_ONLY" if row.get("suitability_status") == "WATCH_ONLY"
                    else "REJECTED" if row.get("suitability_status") == "REJECTED"
                    else "EVIDENCE_REQUIRED"
                ),
            })
    return {
        "schema_version": SCHEMA_VERSION,
        "strategy_id": STRATEGY_ID,
        "generated_at": generated_at or _now(),
        "paper_trade_mode": True,
        "advisory_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "order_placement_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
        "manual_approval_required": True,
        "paper_entry_authorized": False,
        "queue_count": len(queue),
        "excluded_count": len(excluded),
        "review_queue": sorted(queue, key=lambda row: str(row.get("underlying_symbol") or "")),
        "excluded_candidates": sorted(excluded, key=lambda row: str(row.get("underlying_symbol") or "")),
    }


def write_manual_review_queue(
    suitability_path: str | Path, output_path: str | Path
) -> dict[str, Any]:
    report = build_manual_review_queue(_load(suitability_path))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
