from __future__ import annotations

from src.dividend_bot.enterprise_portal_strategy_ui import render_strategy_workspace


def _journal(strategy_id: str, *, empty: bool = False) -> dict:
    decisions = [] if empty else [
        {
            "decision_id": "D-1",
            "decision_timestamp": "2026-08-01T12:00:00Z",
            "strategy_id": strategy_id,
            "strategy_kind": "DIVIDEND",
            "decision_type": "SELECT",
            "status": "RECORDED",
            "summary": "Selected the strongest governed ecosystem pair.",
            "final_rationale": "Income and leverage legs passed committee review.",
            "committee_evidence": [],
            "images": [],
            "lifecycle_event_id": None,
            "decision_object_type": "DIVIDEND_ECOSYSTEM",
            "ecosystem": {
                "ecosystem_id": "NVIDIA-INCOME",
                "ecosystem_name": "NVIDIA Income Ecosystem",
                "mode": "PAIR",
                "income_leg": "NVDY",
                "leverage_leg": "NVDX",
                "income_alternatives": [],
                "leverage_alternatives": [],
                "income_leg_reason": "Income evidence",
                "leverage_leg_reason": "Leverage evidence",
                "pair_compatibility_reason": "Compatible pair",
            },
            "underlying_context": {},
            "selection_comparison": [],
        }
    ]
    return {
        "strategy_id": strategy_id,
        "strategy_name": "Dividend Income Strategy",
        "strategy_kind": "DIVIDEND",
        "decision_count": len(decisions),
        "decisions": decisions,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "read_only": True,
    }


def test_selected_strategy_workspace_renders_canonical_decision_journal() -> None:
    report = {
        "strategy_kpis": [
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Income Strategy",
                "allocated_capital": 5000,
                "decision_journal_status": "AVAILABLE",
                "decision_count": 1,
                "decision_journal": _journal("DIVIDEND-001"),
            }
        ]
    }

    value = render_strategy_workspace(report, audience="executive")

    assert "Dividend Income Strategy Decision Journal" in value
    assert "NVIDIA Income Ecosystem" in value
    assert "NVDY" in value
    assert "NVDX" in value
    assert "Only decisions and evidence owned by DIVIDEND-001 are shown." in value


def test_missing_journal_renders_safe_empty_decisions_state() -> None:
    report = {
        "strategy_kpis": [
            {
                "strategy_id": "SWING-001",
                "display_name": "Swing Trading Strategy",
                "decision_journal_status": "NOT_REPORTED",
                "decision_journal": None,
            }
        ]
    }

    value = render_strategy_workspace(report, audience="executive")

    assert "Decision Journal status: NOT_REPORTED" in value
    assert "No strategy-owned decisions are currently available." in value


def test_cross_strategy_journal_is_not_rendered() -> None:
    report = {
        "strategy_kpis": [
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Income Strategy",
                "decision_journal_status": "AVAILABLE",
                "decision_journal": _journal("SWING-001"),
            }
        ]
    }

    value = render_strategy_workspace(report, audience="executive")

    assert "Cross-strategy Decision Journal evidence was rejected." in value
    assert "NVIDIA Income Ecosystem" not in value
