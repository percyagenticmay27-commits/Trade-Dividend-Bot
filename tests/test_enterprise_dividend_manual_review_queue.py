from __future__ import annotations

import json
from pathlib import Path

import pytest

from enterprise_dividend_manual_review_queue import (
    build_manual_review_queue,
    validate_suitability_report,
    write_manual_review_queue,
)


def _report(status="ELIGIBLE_FOR_PAPER_REVIEW", allowed=True, symbol="SJM"):
    return {
        "schema_version": "1.0",
        "strategy_id": "DIVIDEND-001",
        "paper_trade_mode": True,
        "advisory_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "order_placement_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
        "candidates": [{
            "underlying_symbol": symbol,
            "income_symbol": symbol,
            "mapping_type": "DIRECT_DIVIDEND_EQUITY",
            "suitability_status": status,
            "suitability_score": 100,
            "paper_review_allowed": allowed,
            "decision_reasons": ["Reviewed evidence passed."],
            "suitability_evidence": {"forward_dividend_yield_percent": 3.7},
        }],
    }


def test_eligible_candidate_is_pending_not_approved():
    report = build_manual_review_queue(_report(), generated_at="2026-08-18T20:00:00Z")
    row = report["review_queue"][0]
    assert row["queue_status"] == "PENDING_MANUAL_REVIEW"
    assert row["operator_decision"] is None
    assert row["approved_for_paper_entry"] is False
    assert row["automatic_activation_allowed"] is False
    assert report["paper_entry_authorized"] is False


def test_watch_and_missing_evidence_are_excluded():
    watch = _report("WATCH_ONLY", False, "AMAT")
    required = _report("EVIDENCE_REQUIRED", False, "ULTA")
    required["candidates"][0]["income_symbol"] = None
    combined = {**watch, "candidates": [*watch["candidates"], *required["candidates"]]}
    report = build_manual_review_queue(combined)
    assert report["review_queue"] == []
    assert {row["queue_status"] for row in report["excluded_candidates"]} == {
        "WATCH_ONLY", "EVIDENCE_REQUIRED"
    }


def test_inconsistent_eligibility_cannot_enter_queue():
    report = build_manual_review_queue(_report(allowed=False))
    assert report["queue_count"] == 0
    assert report["excluded_count"] == 1


def test_execution_lock_failure_is_rejected():
    payload = _report()
    payload["order_placement_enabled"] = True
    with pytest.raises(ValueError, match="execution locks"):
        validate_suitability_report(payload)


def test_written_queue_preserves_all_locks(tmp_path: Path):
    source = tmp_path / "suitability.json"
    output = tmp_path / "queue.json"
    source.write_text(json.dumps(_report()), encoding="utf-8")
    report = write_manual_review_queue(source, output)
    assert json.loads(output.read_text(encoding="utf-8")) == report
    assert report["paper_trade_mode"] is True
    assert report["advisory_only"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["order_placement_enabled"] is False
    assert report["capital_movement_enabled"] is False
    assert report["automatic_activation_allowed"] is False
    assert report["manual_approval_required"] is True
