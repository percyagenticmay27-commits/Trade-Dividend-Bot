from __future__ import annotations

from dataclasses import replace

import pytest

from src.dividend_bot.enterprise_decision_engine import (
    EnterpriseDecision,
    EnterpriseDecisionAction,
    StrategyAdvisory,
)
from src.dividend_bot.enterprise_decision_governance import (
    CommitteeReviewOutcome,
    ConstitutionalOutcome,
    EnterpriseDecisionGovernance,
    InvestorDecision,
)
from src.dividend_bot.platform_entities import DecisionState, new_identity
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now


def _decision(*, state: DecisionState = DecisionState.READY_FOR_CIO) -> EnterpriseDecision:
    decision = EnterpriseDecision(
        identity=new_identity("DEC"),
        company_id=new_identity("COM").internal_id,
        profile_id=new_identity("MCIP").internal_id,
        action=EnterpriseDecisionAction.BUY,
        confidence=82,
        opportunity_quality=78,
        rationale="Shared intelligence supports a governed paper decision.",
        strategy_advisories=(
            StrategyAdvisory(
                strategy_id="DIVIDEND",
                action="BUY",
                confidence=80,
                opportunity_quality=78,
                rationale="Income profile is attractive.",
                service_id="DIVIDEND_ADAPTER",
            ),
        ),
        evidence_count=5,
        intelligence_completeness=100,
        intelligence_quality=82,
        stability_checked=True,
        constitution_version="1.0.0",
        state=state,
    )
    decision.validate()
    return decision


def _ready_for_investor(governance: EnterpriseDecisionGovernance, decision: EnterpriseDecision) -> None:
    decision_id = decision.identity.internal_id
    governance.transition(
        decision_id,
        DecisionState.UNDER_COMMITTEE_COLLABORATION,
        actor_id="AI_CIO",
        reason="Begin committee collaboration.",
    )
    governance.add_committee_review(
        decision_id,
        committee_id="RISK_COMMITTEE",
        outcome=CommitteeReviewOutcome.SUPPORT,
        analysis="Risk is acceptable for paper review.",
    )
    governance.transition(
        decision_id,
        DecisionState.UNDER_CONSTITUTIONAL_REVIEW,
        actor_id="AI_CIO",
        reason="Committee analysis complete.",
    )
    governance.add_constitutional_review(
        decision_id,
        outcome=ConstitutionalOutcome.PASSED,
        checks={"paper_only": True, "evidence": True, "stability": True},
        rationale="All constitutional checks passed.",
    )


def test_register_preserves_original_decision() -> None:
    governance = EnterpriseDecisionGovernance()
    decision = _decision()
    governance.register(decision)
    snapshot = governance.snapshot(decision.identity.internal_id)
    assert snapshot.decision is decision
    assert snapshot.current_state is DecisionState.READY_FOR_CIO


def test_duplicate_registration_is_rejected() -> None:
    governance = EnterpriseDecisionGovernance()
    decision = _decision()
    governance.register(decision)
    with pytest.raises(PlatformValidationError):
        governance.register(decision)


def test_invalid_transition_is_rejected() -> None:
    governance = EnterpriseDecisionGovernance()
    decision = _decision()
    governance.register(decision)
    with pytest.raises(PlatformValidationError):
        governance.transition(
            decision.identity.internal_id,
            DecisionState.IMPLEMENTED,
            actor_id="AI_CIO",
            reason="Invalid shortcut.",
        )


def test_committee_review_requires_collaboration_state() -> None:
    governance = EnterpriseDecisionGovernance()
    decision = _decision()
    governance.register(decision)
    with pytest.raises(PlatformValidationError):
        governance.add_committee_review(
            decision.identity.internal_id,
            committee_id="RISK_COMMITTEE",
            outcome=CommitteeReviewOutcome.SUPPORT,
            analysis="Review attempted too early.",
        )


def test_committee_requests_more_evidence_requires_requests() -> None:
    governance = EnterpriseDecisionGovernance()
    decision = _decision()
    governance.register(decision)
    governance.transition(
        decision.identity.internal_id,
        DecisionState.UNDER_COMMITTEE_COLLABORATION,
        actor_id="AI_CIO",
        reason="Begin review.",
    )
    with pytest.raises(PlatformValidationError):
        governance.add_committee_review(
            decision.identity.internal_id,
            committee_id="RISK_COMMITTEE",
            outcome=CommitteeReviewOutcome.REQUEST_MORE_EVIDENCE,
            analysis="More evidence is needed.",
        )


def test_constitutional_pass_moves_to_investor_pending() -> None:
    governance = EnterpriseDecisionGovernance()
    decision = _decision()
    governance.register(decision)
    _ready_for_investor(governance, decision)
    assert governance.state(decision.identity.internal_id) is DecisionState.INVESTOR_OVERRIDE_PENDING


def test_constitutional_failure_returns_to_review() -> None:
    governance = EnterpriseDecisionGovernance()
    decision = _decision()
    governance.register(decision)
    governance.transition(
        decision.identity.internal_id,
        DecisionState.UNDER_CONSTITUTIONAL_REVIEW,
        actor_id="AI_CIO",
        reason="Direct constitutional review.",
    )
    governance.add_constitutional_review(
        decision.identity.internal_id,
        outcome=ConstitutionalOutcome.FAILED,
        checks={"paper_only": True, "evidence": False},
        rationale="Evidence requirement failed.",
    )
    assert governance.state(decision.identity.internal_id) is DecisionState.READY_FOR_REVIEW


def test_investor_approval_moves_to_implemented() -> None:
    governance = EnterpriseDecisionGovernance()
    decision = _decision()
    governance.register(decision)
    _ready_for_investor(governance, decision)
    governance.record_investor_decision(
        decision.identity.internal_id,
        investor_id="INVESTOR-1",
        decision=InvestorDecision.APPROVE,
        reason="Approved for paper implementation.",
    )
    assert governance.state(decision.identity.internal_id) is DecisionState.IMPLEMENTED


def test_investor_rejection_archives_decision() -> None:
    governance = EnterpriseDecisionGovernance()
    decision = _decision()
    governance.register(decision)
    _ready_for_investor(governance, decision)
    governance.record_investor_decision(
        decision.identity.internal_id,
        investor_id="INVESTOR-1",
        decision=InvestorDecision.REJECT,
        reason="Investor rejected the recommendation.",
    )
    assert governance.state(decision.identity.internal_id) is DecisionState.ARCHIVED


def test_investor_override_preserves_original_and_effective_action() -> None:
    governance = EnterpriseDecisionGovernance()
    decision = _decision()
    governance.register(decision)
    _ready_for_investor(governance, decision)
    governance.record_investor_decision(
        decision.identity.internal_id,
        investor_id="INVESTOR-1",
        decision=InvestorDecision.OVERRIDE,
        reason="Investor prefers HOLD in paper mode.",
        override_action=EnterpriseDecisionAction.HOLD,
    )
    snapshot = governance.snapshot(decision.identity.internal_id)
    assert snapshot.decision.action is EnterpriseDecisionAction.BUY
    assert snapshot.effective_action is EnterpriseDecisionAction.HOLD
    assert snapshot.current_state is DecisionState.OVERRIDDEN_BY_INVESTOR


def test_override_requires_override_action() -> None:
    governance = EnterpriseDecisionGovernance()
    decision = _decision()
    governance.register(decision)
    _ready_for_investor(governance, decision)
    with pytest.raises(PlatformValidationError):
        governance.record_investor_decision(
            decision.identity.internal_id,
            investor_id="INVESTOR-1",
            decision=InvestorDecision.OVERRIDE,
            reason="Missing override action.",
        )


def test_governance_history_is_append_only_tuple_snapshot() -> None:
    governance = EnterpriseDecisionGovernance()
    decision = _decision()
    governance.register(decision)
    _ready_for_investor(governance, decision)
    snapshot = governance.snapshot(decision.identity.internal_id)
    assert isinstance(snapshot.events, tuple)
    assert isinstance(snapshot.committee_reviews, tuple)
    assert len(snapshot.events) == 3


def test_json_and_markdown_outputs_include_governance_boundary() -> None:
    governance = EnterpriseDecisionGovernance()
    decision = _decision()
    governance.register(decision)
    snapshot = governance.snapshot(decision.identity.internal_id)
    payload = governance.render_json(snapshot)
    markdown = governance.render_markdown(snapshot)
    assert '"paper_trade_mode": true' in payload
    assert "Committees analyze and recommend" in markdown


def test_snapshot_rejects_live_flags() -> None:
    governance = EnterpriseDecisionGovernance()
    decision = _decision()
    governance.register(decision)
    snapshot = governance.snapshot(decision.identity.internal_id)
    invalid = replace(snapshot, live_trading_enabled=True)
    with pytest.raises(PlatformValidationError):
        invalid.validate()


def test_no_capital_broker_or_order_interface() -> None:
    governance = EnterpriseDecisionGovernance()
    assert not hasattr(governance, "allocate_capital")
    assert not hasattr(governance, "place_order")
    assert not hasattr(governance, "broker_request")
