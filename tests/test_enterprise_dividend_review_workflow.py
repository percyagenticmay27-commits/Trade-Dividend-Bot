from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.dividend_bot.enterprise_dividend_review_workflow import (
    ADVISORY_ONLY,
    BROKER_EXECUTION_ENABLED,
    HUMAN_APPROVAL_REQUIRED,
    LIVE_TRADING_ENABLED,
    PAPER_TRADE_MODE,
    REPORTING_ONLY,
    REVIEW_STATUSES,
    VALID_TRANSITIONS,
    build_and_write_enterprise_dividend_reviews,
    build_enterprise_dividend_reviews,
    render_enterprise_dividend_reviews_markdown,
    transition_review,
    write_enterprise_dividend_reviews,
)

NOW = "2026-07-25T15:00:00Z"
LATER = "2026-07-25T16:00:00Z"


def alert(**overrides):
    value = {
        "alert_id": "DIV-ALERT-ABC123",
        "deduplication_key": "abc123",
        "symbol": "O",
        "alert_type": "DIVIDEND_CUT",
        "severity": "HIGH",
        "status": "OPEN",
        "message": "Dividend was reduced.",
        "recommended_action": "Review the declaration and income impact.",
        "source_module": "enterprise_dividend_alert_integration",
        "source_report": "enterprise_dividend_alerts.json",
        "reporting_period": "2026-07",
        "evidence_links": ["evidence/dividend_declaration.json"],
        "analytics_links": ["results/dividend_analytics.json"],
    }
    value.update(overrides)
    return value


def build_one(**kwargs):
    return build_enterprise_dividend_reviews(
        alerts=[alert()], generated_at_utc=NOW, **kwargs
    )


def test_safety_constants_are_locked():
    assert PAPER_TRADE_MODE is True
    assert LIVE_TRADING_ENABLED is False
    assert BROKER_EXECUTION_ENABLED is False
    assert REPORTING_ONLY is True
    assert ADVISORY_ONLY is True
    assert HUMAN_APPROVAL_REQUIRED is True


def test_supported_review_statuses_are_exact():
    assert REVIEW_STATUSES == {"OPEN", "UNDER_REVIEW", "RESOLVED", "DEFERRED", "ESCALATED"}


def test_empty_inputs_return_partial_workflow_with_warning():
    result = build_enterprise_dividend_reviews(generated_at_utc=NOW)
    assert result["workflow_status"] == "PARTIAL"
    assert result["summary"]["total_reviews"] == 0
    assert result["warnings"]


def test_alert_report_input_is_supported():
    result = build_enterprise_dividend_reviews(
        alert_report={"alerts": [alert()]}, generated_at_utc=NOW
    )
    assert result["workflow_status"] == "READY"
    assert result["summary"]["total_reviews"] == 1


def test_review_is_created_open_with_traceability():
    review = build_one()["reviews"][0]
    assert review["status"] == "OPEN"
    assert review["alert_id"] == "DIV-ALERT-ABC123"
    assert review["originating_evidence_links"] == ["evidence/dividend_declaration.json"]
    assert review["originating_analytics_links"] == ["results/dividend_analytics.json"]
    assert review["originating_report_links"] == ["enterprise_dividend_alerts.json"]
    assert review["status_history"][0]["to_status"] == "OPEN"


def test_review_identity_is_deterministic():
    first = build_one()["reviews"][0]
    second = build_one()["reviews"][0]
    assert first["review_id"] == second["review_id"]
    assert first["review_key"] == second["review_key"]


def test_duplicate_alerts_create_one_review():
    duplicate = alert(message="Updated message")
    result = build_enterprise_dividend_reviews(
        alerts=[alert(), duplicate], generated_at_utc=NOW
    )
    assert result["summary"]["total_reviews"] == 1


@pytest.mark.parametrize(
    ("severity", "priority"),
    [
        ("CRITICAL", "URGENT"),
        ("HIGH", "HIGH"),
        ("MEDIUM", "MEDIUM"),
        ("LOW", "LOW"),
        ("INFO", "ROUTINE"),
    ],
)
def test_severity_maps_to_priority(severity, priority):
    result = build_enterprise_dividend_reviews(
        alerts=[alert(severity=severity)], generated_at_utc=NOW
    )
    assert result["reviews"][0]["priority"] == priority


def test_resolved_alert_is_ignored_by_default():
    result = build_enterprise_dividend_reviews(
        alerts=[alert(status="RESOLVED")], generated_at_utc=NOW
    )
    assert result["summary"]["total_reviews"] == 0
    assert result["summary"]["ignored_resolved_alerts"] == 1


def test_resolved_alert_can_be_included_explicitly():
    result = build_enterprise_dividend_reviews(
        alerts=[alert(status="RESOLVED")],
        include_resolved_alerts=True,
        generated_at_utc=NOW,
    )
    assert result["summary"]["total_reviews"] == 1


def test_existing_review_identity_and_state_are_preserved():
    original = build_one()["reviews"][0]
    existing = dict(original)
    existing["status"] = "UNDER_REVIEW"
    existing["assigned_reviewer"] = "Investor"
    refreshed = build_enterprise_dividend_reviews(
        alerts=[alert(message="New alert message")],
        existing_reviews=[existing],
        generated_at_utc=LATER,
    )["reviews"][0]
    assert refreshed["review_id"] == original["review_id"]
    assert refreshed["created_at_utc"] == NOW
    assert refreshed["status"] == "UNDER_REVIEW"
    assert refreshed["assigned_reviewer"] == "Investor"
    assert refreshed["last_updated_at_utc"] == LATER


def test_existing_traceability_links_are_union_merged():
    original = build_one()["reviews"][0]
    original["originating_evidence_links"] = ["old.json"]
    refreshed = build_enterprise_dividend_reviews(
        alerts=[alert(evidence_links=["new.json"])],
        existing_reviews=[original],
        generated_at_utc=LATER,
    )["reviews"][0]
    assert refreshed["originating_evidence_links"] == ["new.json", "old.json"]


def test_transition_open_to_under_review():
    review = build_one()["reviews"][0]
    updated = transition_review(
        review,
        to_status="UNDER_REVIEW",
        actor="Investor",
        reason="Evidence review started.",
        assigned_reviewer="Investor",
        note="Checking declaration history.",
        generated_at_utc=LATER,
    )
    assert updated["status"] == "UNDER_REVIEW"
    assert updated["assigned_reviewer"] == "Investor"
    assert len(updated["status_history"]) == 2
    assert len(updated["review_notes"]) == 1


def test_transition_to_resolved_requires_resolution():
    review = build_one()["reviews"][0]
    with pytest.raises(ValueError, match="resolution is required"):
        transition_review(review, to_status="RESOLVED", actor="Investor", reason="Done")


def test_transition_to_resolved_records_decision_link():
    review = build_one()["reviews"][0]
    updated = transition_review(
        review,
        to_status="RESOLVED",
        actor="Investor",
        reason="Evidence validated.",
        resolution="No portfolio change approved.",
        decision_reference="decisions/review-001.json",
        generated_at_utc=LATER,
    )
    assert updated["resolution"] == "No portfolio change approved."
    assert updated["decision_links"] == ["decisions/review-001.json"]


def test_transition_to_deferred_requires_date():
    review = build_one()["reviews"][0]
    with pytest.raises(ValueError, match="deferred_until_utc is required"):
        transition_review(review, to_status="DEFERRED", actor="Investor", reason="Wait")


def test_transition_to_escalated_requires_reason():
    review = build_one()["reviews"][0]
    with pytest.raises(ValueError, match="escalation_reason is required"):
        transition_review(review, to_status="ESCALATED", actor="Investor", reason="Escalate")


def test_resolved_review_cannot_transition():
    review = build_one()["reviews"][0]
    resolved = transition_review(
        review,
        to_status="RESOLVED",
        actor="Investor",
        reason="Complete",
        resolution="Closed",
        generated_at_utc=LATER,
    )
    with pytest.raises(ValueError, match="Invalid review transition"):
        transition_review(
            resolved,
            to_status="UNDER_REVIEW",
            actor="Investor",
            reason="Reopen",
        )


def test_same_status_transition_is_rejected():
    review = build_one()["reviews"][0]
    with pytest.raises(ValueError, match="must change status"):
        transition_review(review, to_status="OPEN", actor="Investor", reason="No change")


def test_blank_actor_and_reason_are_rejected():
    review = build_one()["reviews"][0]
    with pytest.raises(ValueError, match="actor is required"):
        transition_review(review, to_status="UNDER_REVIEW", actor="", reason="Start")
    with pytest.raises(ValueError, match="reason is required"):
        transition_review(review, to_status="UNDER_REVIEW", actor="Investor", reason="")


def test_valid_transition_table_has_no_unsupported_statuses():
    assert set(VALID_TRANSITIONS) == REVIEW_STATUSES
    assert all(targets <= REVIEW_STATUSES for targets in VALID_TRANSITIONS.values())


def test_summary_counts_match_reviews():
    result = build_enterprise_dividend_reviews(
        alerts=[
            alert(deduplication_key="a", alert_id="A", severity="CRITICAL"),
            alert(deduplication_key="b", alert_id="B", symbol="MAIN", severity="LOW"),
        ],
        generated_at_utc=NOW,
    )
    assert result["summary"]["total_reviews"] == 2
    assert result["summary"]["active_reviews"] == 2
    assert result["summary"]["urgent_reviews"] == 1
    assert result["summary"]["open"] == 2


def test_markdown_contains_queue_and_governance():
    markdown = render_enterprise_dividend_reviews_markdown(build_one())
    assert "# Enterprise Dividend Review Workflow" in markdown
    assert "## Review Queue" in markdown
    assert "DIV-REVIEW-" in markdown
    assert "## Governance Notes" in markdown


def test_write_outputs_json_and_markdown(tmp_path: Path):
    payload = build_one()
    paths = write_enterprise_dividend_reviews(payload, tmp_path)
    assert Path(paths["json"]).exists()
    assert Path(paths["markdown"]).exists()
    loaded = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert loaded["summary"]["total_reviews"] == 1


def test_build_and_write_returns_output_paths(tmp_path: Path):
    result = build_and_write_enterprise_dividend_reviews(
        alerts=[alert()], output_dir=tmp_path, generated_at_utc=NOW
    )
    assert Path(result["output_files"]["json"]).exists()
    assert Path(result["output_files"]["markdown"]).exists()


def test_output_metadata_is_complete():
    result = build_one()
    assert result["module_name"] == "enterprise_dividend_review_workflow"
    assert result["module_version"] == "1.0.0"
    assert result["schema_version"] == "1.0"
    assert result["paper_trade_mode"] is True
    assert result["human_approval_required"] is True
