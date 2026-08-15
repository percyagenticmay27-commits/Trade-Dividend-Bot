from __future__ import annotations

from src.dividend_bot.enterprise_swing_decision_journal_ui import (
    render_swing_decision_journal_panel,
    swing_decision_journal_ui_css,
)


def _decision(symbol: str, scope: str, state: str, decision: str, owner: str) -> dict:
    return {
        "decision_id": f"DECISION-{symbol}",
        "decision_scope": scope,
        "symbol": symbol,
        "current_state": state,
        "current_decision": decision,
        "current_owner": owner,
        "rationale": "Current authoritative evidence supports this state.",
        "alternatives_considered": ["Continue monitoring"],
        "evidence_timestamp": "2026-08-15T15:00:00Z",
        "timeline": [{
            "sequence": 1,
            "owner": owner,
            "status": decision,
            "reason_codes": ["CURRENT_AUTHORITATIVE_EVIDENCE"],
            "evidence_timestamp": "2026-08-15T15:00:00Z",
        }],
    }


def _row() -> dict:
    positions = [
        _decision("SOXL", "OPEN_POSITION", "OPEN", "HOLD", "Strategy A"),
        _decision("TQQQ", "OPEN_POSITION", "OPEN", "HOLD", "Strategy A"),
    ]
    candidates = [
        _decision(
            "NBIS", "CANDIDATE", "REJECTED", "WAITING_FOR_ENTRY",
            "OPPORTUNITY_COMMITTEE",
        )
    ]
    return {
        "strategy_id": "SWING-001",
        "allocated_capital": 4500.0,
        "paper_trade_mode": True,
        "decision_journal_status": "AVAILABLE",
        "decision_journal": {
            "module_name": "swing_decision_journal_report",
            "strategy_id": "SWING-001",
            "paper_trade_mode": True,
            "advisory_only": True,
            "decision_authority_policy":
                "CURRENT_MATCHED_AUTHORITATIVE_EVIDENCE_ONLY",
            "evaluation_status": "COMPLETE_WITH_EVIDENCE_WARNINGS",
            "position_decisions": positions,
            "candidate_decisions": candidates,
            "decisions": [*positions, *candidates],
            "evidence_warnings": ["Candidate evidence timestamp requires review."],
            "excluded_planning_sources": ["results/rebalance_actions.json"],
        },
    }


def test_renders_position_and_candidate_decisions_separately() -> None:
    output = render_swing_decision_journal_panel(_row())

    position_start = output.index("Open Position Decisions")
    candidate_start = output.index("Candidate Decisions")
    assert position_start < output.index("SOXL") < candidate_start
    assert position_start < output.index("TQQQ") < candidate_start
    assert output.index("NBIS") > candidate_start
    assert "HOLD" in output
    assert "WAITING_FOR_ENTRY" in output
    assert "REJECTED" in output
    assert "OPPORTUNITY_COMMITTEE" in output


def test_renders_committee_timeline_and_required_fields() -> None:
    output = render_swing_decision_journal_panel(_row())

    assert "Committee Evidence Timeline" in output
    assert "Current state" in output
    assert "Current owner" in output
    assert "Rationale:" in output
    assert "Alternatives considered:" in output
    assert "Evidence timestamp" in output
    assert "CURRENT_AUTHORITATIVE_EVIDENCE" in output


def test_evidence_warnings_are_separate_disclosures() -> None:
    output = render_swing_decision_journal_panel(_row())

    assert "Evidence Disclosures" in output
    assert "Candidate evidence timestamp requires review." in output
    assert "COMPLETE_WITH_EVIDENCE_WARNINGS" in output


def test_zero_decision_message_is_authoritative() -> None:
    row = _row()
    journal = row["decision_journal"]
    journal["position_decisions"] = []
    journal["candidate_decisions"] = []
    journal["decisions"] = []
    journal["no_decisions_message"] = (
        "Current authoritative Swing evidence was evaluated and no reportable "
        "decisions were found."
    )

    output = render_swing_decision_journal_panel(row)

    assert "Current authoritative Swing evidence was evaluated" in output
    assert "no reportable decisions were found" in output


def test_missing_evidence_is_disclosed_without_fabrication() -> None:
    output = render_swing_decision_journal_panel({
        "strategy_id": "SWING-001",
        "decision_journal": None,
    })

    assert "Decision Journal unavailable" in output
    assert "No decision was inferred or fabricated" in output
    assert ">BUY<" not in output
    assert ">SELL<" not in output


def test_prohibited_buy_sell_report_fails_closed() -> None:
    row = _row()
    row["decision_journal"]["candidate_decisions"][0]["current_decision"] = "BUY"

    output = render_swing_decision_journal_panel(row)

    assert "outside the registered advisory contract" in output
    assert "NBIS" not in output
    assert "No BUY, SELL, sale, exit, or closure was inferred" in output


def test_swing_view_has_no_dividend_pair_lifecycle_terminology() -> None:
    output = render_swing_decision_journal_panel(_row())

    assert "Pair Lifecycle Overview" not in output
    assert "ECOSYSTEM PAIR" not in output
    assert "Income ETF" not in output
    assert "Leverage ETF" not in output


def test_html_escaping_and_strategy_isolation() -> None:
    row = _row()
    row["decision_journal"]["position_decisions"][0]["rationale"] = (
        "<script>alert(1)</script>"
    )
    output = render_swing_decision_journal_panel(row)

    assert "<script>" not in output
    assert "&lt;script&gt;" in output
    assert render_swing_decision_journal_panel({
        "strategy_id": "DIVIDEND-001",
        "decision_journal": row["decision_journal"],
    }) == ""


def test_paper_safety_and_css_are_visible() -> None:
    output = render_swing_decision_journal_panel(_row())
    css = swing_decision_journal_ui_css()

    assert "PAPER ONLY" in output
    assert "ADVISORY ONLY" in output
    assert "READ ONLY" in output
    assert "rebalance_actions.json" in output
    assert ".swing-decision-card" in css
    assert ".swing-decision-waiting-for-entry" in css
