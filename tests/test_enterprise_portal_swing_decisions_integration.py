from __future__ import annotations

from src.dividend_bot.enterprise_portal_strategy_ui_v2 import (
    render_strategy_workspace,
    strategy_ui_css,
)


def _swing_journal() -> dict:
    position = {
        "decision_id": "SWING-POSITION-SOXL",
        "decision_scope": "OPEN_POSITION",
        "symbol": "SOXL",
        "current_state": "OPEN",
        "current_decision": "HOLD",
        "current_owner": "Strategy A",
        "rationale": "No current authoritative exit decision is reported.",
        "alternatives_considered": [],
        "evidence_timestamp": "2026-08-15T15:00:00Z",
        "timeline": [{
            "sequence": 1,
            "owner": "Strategy A",
            "status": "HOLD",
            "reason_codes": ["AUTHORITATIVE_OPEN_POSITION"],
        }],
    }
    candidate = {
        "decision_id": "SWING-CANDIDATE-NBIS",
        "decision_scope": "CANDIDATE",
        "symbol": "NBIS",
        "current_state": "REJECTED",
        "current_decision": "WAITING_FOR_ENTRY",
        "current_owner": "OPPORTUNITY_COMMITTEE",
        "rationale": "ENTRY_EVIDENCE_PENDING",
        "alternatives_considered": [],
        "evidence_timestamp": "2026-08-15T15:00:00Z",
        "timeline": [{
            "sequence": 1,
            "owner": "OPPORTUNITY_COMMITTEE",
            "status": "REJECTED",
            "reason_codes": ["ENTRY_EVIDENCE_PENDING"],
        }],
    }
    return {
        "module_name": "swing_decision_journal_report",
        "strategy_id": "SWING-001",
        "paper_trade_mode": True,
        "advisory_only": True,
        "decision_authority_policy":
            "CURRENT_MATCHED_AUTHORITATIVE_EVIDENCE_ONLY",
        "position_decisions": [position],
        "candidate_decisions": [candidate],
        "decisions": [position, candidate],
        "decision_count": 2,
        "evaluation_status": "COMPLETE",
        "evidence_warnings": [],
    }


def _report() -> dict:
    return {
        "strategy_kpis": [
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Income Strategy",
                "allocated_capital": 5000.0,
                "paper_trade_mode": True,
                "evidence_status": "AVAILABLE",
                "decision_journal_status": "AVAILABLE",
                "decision_journal": {
                    "strategy_id": "DIVIDEND-001",
                    "strategy_name": "Dividend Income Strategy",
                    "strategy_type": "DIVIDEND",
                    "paper_trade_mode": True,
                    "decisions": [{
                        "strategy_id": "DIVIDEND-001",
                        "decision_timestamp": "2026-08-15T14:00:00Z",
                        "decision_type": "HOLD",
                        "status": "MONITOR",
                        "ecosystem_name": "AMD Income Ecosystem",
                        "income_leg": "AMDW",
                        "leverage_leg": "AMDL",
                        "final_rationale": "Dividend-owned rationale.",
                        "committee_evidence": [],
                    }],
                },
            },
            {
                "strategy_id": "SWING-001",
                "display_name": "Trade Swing Bot",
                "allocated_capital": 4500.0,
                "paper_trade_mode": True,
                "advisory_only": True,
                "evidence_status": "AVAILABLE",
                "decision_journal_status": "AVAILABLE",
                "decision_journal": _swing_journal(),
            },
        ]
    }


def test_swing_decisions_tab_routes_to_stock_lifecycle_renderer() -> None:
    output = render_strategy_workspace(_report(), audience="executive")
    swing_start = output.index("id='strategy-SWING-001'")
    swing = output[swing_start:]

    assert "Trade Swing Bot Decision Journal" in swing
    assert "Open Position Decisions" in swing
    assert "Candidate Decisions" in swing
    assert "SOXL" in swing
    assert "NBIS" in swing
    assert "OPPORTUNITY_COMMITTEE" in swing
    assert "CURRENT_MATCHED_AUTHORITATIVE_EVIDENCE_ONLY" in swing
    assert "Pair Lifecycle Overview" not in swing
    assert "ECOSYSTEM PAIR" not in swing


def test_dividend_decisions_remain_on_pair_lifecycle_renderer() -> None:
    output = render_strategy_workspace(_report(), audience="executive")
    dividend_start = output.index("id='strategy-DIVIDEND-001'")
    swing_start = output.index("id='strategy-SWING-001'")
    dividend = output[dividend_start:swing_start]

    assert "Dividend Income Strategy Decision Journal" in dividend
    assert "AMDW" in dividend
    assert "AMDL" in dividend
    assert "Dividend-owned rationale." in dividend
    assert "Trade Swing Bot Decision Journal" not in dividend


def test_decisions_workspace_preserves_allocations_safety_and_styles() -> None:
    output = render_strategy_workspace(_report(), audience="executive")
    css = strategy_ui_css()

    assert "$5,000.00 allocated" in output
    assert "$4,500.00 allocated" in output
    assert "PAPER ONLY" in output
    assert "ADVISORY ONLY" in output
    assert "READ ONLY" in output
    assert ".swing-decision-card" in css
