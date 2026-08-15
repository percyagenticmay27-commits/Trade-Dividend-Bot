from __future__ import annotations

from src.dividend_bot.enterprise_swing_alerts_ui import (
    render_swing_alerts_panel,
    swing_alerts_ui_css,
)


def _row(*, alerts=None, warnings=None, count=0) -> dict:
    return {
        "strategy_id": "SWING-001",
        "allocated_capital": 4500.0,
        "paper_trade_mode": True,
        "advisory_only": True,
        "alerts_report": {
            "strategy_id": "SWING-001",
            "paper_trade_mode": True,
            "advisory_only": True,
            "alert_authority_policy": "CURRENT_AUTHORITATIVE_EVIDENCE_ONLY",
            "actionable_alert_count": count,
            "alerts": alerts or [],
            "evidence_warning_count": len(warnings or []),
            "evidence_warnings": warnings or [],
            "evaluation_status": "COMPLETE_WITH_EVIDENCE_WARNINGS",
        },
    }


def test_verified_zero_alert_message_and_disclosures_are_separate() -> None:
    output = render_swing_alerts_panel(_row(warnings=[
        "KPI disclosure: Win rate is unavailable until authentic closed trades exist.",
        "KPI valuation/evidence disclosure.",
        "Legacy dashboard is not current: TIMESTAMP_UNAVAILABLE",
    ]))

    assert "Current authoritative Swing evidence was evaluated and no actionable alerts were found." in output
    assert "<h4>Actionable Alerts</h4>" in output
    assert "<h4>Evidence Disclosures</h4>" in output
    assert "Win rate is unavailable" in output
    assert "Legacy dashboard is not current" in output
    assert "No strategy-owned alerts are currently reported." not in output


def test_actionable_alert_fields_and_classes_render_exactly() -> None:
    output = render_swing_alerts_panel(_row(count=1, alerts=[{
        "strategy_id": "SWING-001",
        "symbol": "SOXL",
        "alert_category": "OPERATIONAL_EVIDENCE",
        "severity": "ERROR",
        "priority": "HIGH",
        "status": "OPEN",
        "message": "Current scheduled cycle failed",
        "recommended_review_action": "Review authoritative Swing evidence; no automatic action is permitted.",
        "evidence_source": "operational_health_report.json",
        "evidence_timestamp": "2026-08-15T12:45:00Z",
        "paper_trade_mode": True,
        "advisory_only": True,
    }]))

    for expected in (
        "SOXL", "OPERATIONAL_EVIDENCE", "ERROR", "HIGH", "OPEN",
        "Current scheduled cycle failed", "Review authoritative Swing evidence",
        "operational_health_report.json", "2026-08-15T12:45:00Z",
    ):
        assert expected in output
    assert "swing-alert-severity-error" in output
    assert "swing-alert-priority-high" in output


def test_stale_legacy_flags_are_not_substituted_for_current_alerts() -> None:
    row = _row(warnings=["Legacy dashboard is not current: TIMESTAMP_UNAVAILABLE"])
    row["risk_flags"] = [
        "Exit review attention required",
        "Reentry-ready paper setup detected",
        "Thesis monitor attention required",
        "Theme allocation exceeds 40% cap: Unclassified",
    ]

    output = render_swing_alerts_panel(row)

    assert "Exit review attention required" not in output
    assert "Reentry-ready paper setup detected" not in output
    assert "Thesis monitor attention required" not in output
    assert "Theme allocation exceeds 40% cap" not in output


def test_missing_optional_evidence_does_not_fabricate_alerts() -> None:
    output = render_swing_alerts_panel({
        "strategy_id": "SWING-001",
        "paper_trade_mode": True,
        "advisory_only": True,
    })

    assert "Authoritative Swing Alerts evidence is unavailable" in output
    assert "No alerts were fabricated" in output


def test_renderer_escapes_strategy_owned_text_and_locks_safety() -> None:
    output = render_swing_alerts_panel(_row(count=1, alerts=[{
        "symbol": "<script>alert(1)</script>",
        "severity": "WARNING",
        "priority": "MEDIUM",
        "message": "<b>unsafe</b>",
    }]))

    assert "<script>" not in output
    assert "&lt;script&gt;" in output
    assert "&lt;b&gt;unsafe&lt;/b&gt;" in output
    assert "PAPER ONLY" in output
    assert "ADVISORY ONLY" in output


def test_non_swing_strategy_does_not_receive_swing_alerts() -> None:
    row = _row()
    row["strategy_id"] = "DIVIDEND-001"

    assert render_swing_alerts_panel(row) == ""


def test_alert_css_defines_severity_and_priority_states() -> None:
    css = swing_alerts_ui_css()

    assert ".swing-alert-severity-error" in css
    assert ".swing-alert-severity-warning" in css
    assert ".swing-alert-priority-high" in css
    assert ".swing-alert-priority-medium" in css
