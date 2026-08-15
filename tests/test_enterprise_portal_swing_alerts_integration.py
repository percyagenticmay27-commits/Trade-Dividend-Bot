from __future__ import annotations

from src.dividend_bot.enterprise_portal_strategy_ui_v2 import (
    render_strategy_workspace,
    strategy_ui_css,
)


def _report() -> dict:
    return {
        "strategy_kpis": [
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Income Strategy",
                "allocated_capital": 5000.0,
                "evidence_status": "AVAILABLE",
                "health_status": "HEALTHY",
                "alerts": [{
                    "symbol": "AMDW",
                    "severity": "HIGH",
                    "message": "Dividend-owned review remains active.",
                }],
                "risk_flags": [],
            },
            {
                "strategy_id": "SWING-001",
                "display_name": "Trade Swing Bot",
                "allocated_capital": 4500.0,
                "evidence_status": "AVAILABLE",
                "health_status": "HEALTHY",
                "paper_trade_mode": True,
                "advisory_only": True,
                "alerts_status": "AVAILABLE",
                "alerts": [],
                "risk_flags": [
                    "Exit review attention required",
                    "Reentry-ready paper setup detected",
                    "Thesis monitor attention required",
                    "Theme allocation exceeds 40% cap: Unclassified",
                ],
                "alerts_report": {
                    "strategy_id": "SWING-001",
                    "paper_trade_mode": True,
                    "advisory_only": True,
                    "live_trading_enabled": False,
                    "broker_execution_enabled": False,
                    "order_placement_enabled": False,
                    "capital_movement_enabled": False,
                    "alert_authority_policy": "CURRENT_AUTHORITATIVE_EVIDENCE_ONLY",
                    "actionable_alert_count": 0,
                    "alerts": [],
                    "evidence_warning_count": 3,
                    "evidence_warnings": [
                        "KPI disclosure: Win rate is unavailable until authentic closed trades exist.",
                        "KPI valuation/evidence disclosure.",
                        "Legacy dashboard is not current: TIMESTAMP_UNAVAILABLE",
                    ],
                    "evaluation_status": "COMPLETE_WITH_EVIDENCE_WARNINGS",
                },
            },
        ]
    }


def test_swing_alerts_tab_routes_to_authoritative_renderer() -> None:
    output = render_strategy_workspace(_report(), audience="executive")
    swing_start = output.index("id='strategy-SWING-001'")
    swing = output[swing_start:]

    assert "CURRENT_AUTHORITATIVE_EVIDENCE_ONLY" in swing
    assert "COMPLETE_WITH_EVIDENCE_WARNINGS" in swing
    assert "Current authoritative Swing evidence was evaluated and no actionable alerts were found." in swing
    assert "Evidence Disclosures" in swing
    assert "Win rate is unavailable" in swing
    assert "Legacy dashboard is not current" in swing


def test_swing_stale_legacy_flags_are_not_current_alerts() -> None:
    output = render_strategy_workspace(_report(), audience="executive")
    swing_start = output.index("id='strategy-SWING-001'")
    swing = output[swing_start:]

    for stale in (
        "Exit review attention required",
        "Reentry-ready paper setup detected",
        "Thesis monitor attention required",
        "Theme allocation exceeds 40% cap: Unclassified",
    ):
        assert stale not in swing


def test_dividend_alerts_remain_unchanged_and_strategy_scoped() -> None:
    output = render_strategy_workspace(_report(), audience="executive")
    dividend_start = output.index("id='strategy-DIVIDEND-001'")
    swing_start = output.index("id='strategy-SWING-001'")
    dividend = output[dividend_start:swing_start]

    assert "Dividend-owned review remains active." in dividend
    assert "AMDW" in dividend
    assert "CURRENT_AUTHORITATIVE_EVIDENCE_ONLY" not in dividend
    assert "Evidence Disclosures" not in dividend


def test_alerts_workspace_preserves_allocations_safety_and_css() -> None:
    output = render_strategy_workspace(_report(), audience="executive")
    css = strategy_ui_css()

    assert "$5,000.00 allocated" in output
    assert "$4,500.00 allocated" in output
    assert "PAPER ONLY" in output
    assert "ADVISORY ONLY" in output
    assert ".swing-alert-severity-error" in css
    assert ".swing-alert-priority-high" in css
