from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest

from src.dividend_bot.enterprise_capital_manager import EnterpriseCapitalManager, InvestorCapitalInstruction
from src.dividend_bot.enterprise_decision_engine import (
    EnterpriseDecision,
    EnterpriseDecisionAction,
    StrategyAdvisory,
)
from src.dividend_bot.enterprise_decision_governance import (
    DecisionGovernanceSnapshot,
    InvestorDecision,
    InvestorDecisionRecord,
)
from src.dividend_bot.enterprise_strategy_execution import (
    EnterpriseStrategyExecutionCoordinator,
    StrategyExecutionRequest,
    StrategyExecutionResponse,
    StrategyResponseStatus,
)
from src.dividend_bot.platform_entities import DecisionState, new_identity
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now
from src.dividend_bot.strategy_framework import (
    StrategyConfiguration,
    StrategyDefinition,
    StrategyRegistry,
    StrategyStatus,
)


def _definition(strategy_id: str = "DIVIDEND") -> StrategyDefinition:
    return StrategyDefinition(
        strategy_id=strategy_id,
        name=f"{strategy_id.title()} Strategy",
        version="1.0.0",
        supported_asset_types=("EQUITY",),
        required_intelligence=("FUNDAMENTALS",),
        supported_report_types=("WEEKLY",),
        supported_audit_types=("STRATEGY",),
        module_entry_point=f"src.dividend_bot.{strategy_id.lower()}_strategy_adapter",
    )


def _setup(*, funded: bool = True, status: StrategyStatus = StrategyStatus.PAPER_VALIDATION):
    registry = StrategyRegistry()
    registry.register(_definition())
    registry.configure(StrategyConfiguration("DIVIDEND", "1.0.0", {}))
    registry.transition("DIVIDEND", StrategyStatus.CONFIGURED, "Configured for paper validation")
    registry.transition("DIVIDEND", StrategyStatus.PAPER_VALIDATION, "Begin paper validation")

    capital = EnterpriseCapitalManager(registry)
    if funded:
        capital.record_deposit(10_000)
        capital.apply_investor_instruction(
            InvestorCapitalInstruction("INVESTOR-1", {"DIVIDEND": 5_000}, "Fund Dividend strategy")
        )

    if status is StrategyStatus.OPERATIONAL:
        registry.transition("DIVIDEND", StrategyStatus.OPERATIONAL, "Paper validation passed")
    elif status is StrategyStatus.SUSPENDED:
        registry.transition("DIVIDEND", StrategyStatus.SUSPENDED, "Temporarily suspended")

    return registry, capital, EnterpriseStrategyExecutionCoordinator(registry, capital)


def _governance(
    *,
    state: DecisionState = DecisionState.IMPLEMENTED,
    investor_decision: InvestorDecision = InvestorDecision.APPROVE,
    effective_action: EnterpriseDecisionAction = EnterpriseDecisionAction.BUY,
    strategy_id: str = "DIVIDEND",
) -> DecisionGovernanceSnapshot:
    advisory = StrategyAdvisory(
        strategy_id=strategy_id,
        action="BUY",
        confidence=80,
        opportunity_quality=75,
        rationale="Strategy supports a paper buy.",
        service_id="DIVIDEND_ADAPTER",
    )
    decision = EnterpriseDecision(
        identity=new_identity("DEC"),
        company_id=uuid4(),
        profile_id=uuid4(),
        action=EnterpriseDecisionAction.BUY,
        confidence=80,
        opportunity_quality=75,
        rationale="Enterprise CIO approved advisory.",
        strategy_advisories=(advisory,),
        evidence_count=3,
        intelligence_completeness=100,
        intelligence_quality=80,
        stability_checked=True,
        constitution_version="1.0.0",
        state=DecisionState.READY_FOR_CIO,
    )
    record = InvestorDecisionRecord(
        record_id=uuid4(),
        decision_id=decision.identity.internal_id,
        investor_id="INVESTOR-1",
        decision=investor_decision,
        reason="Investor reviewed the governed decision.",
        override_action=effective_action if investor_decision is InvestorDecision.OVERRIDE else None,
    )
    snapshot = DecisionGovernanceSnapshot(
        decision=decision,
        current_state=state,
        committee_reviews=(),
        constitutional_reviews=(),
        investor_decisions=(record,),
        events=(),
        effective_action=effective_action,
    )
    snapshot.validate()
    return snapshot


def test_capability_discovery_reports_readiness_and_allocation() -> None:
    _, _, coordinator = _setup()
    row = coordinator.discover_capabilities()[0]
    assert row.strategy_id == "DIVIDEND"
    assert row.ready_for_execution is True
    assert row.allocated_capital == 5_000


def test_approved_decision_routes_to_funded_strategy() -> None:
    _, _, coordinator = _setup()
    request = coordinator.route(
        _governance(), strategy_id="DIVIDEND", requested_capital=1_000, rationale="Paper allocation review"
    )
    assert request.strategy_id == "DIVIDEND"
    assert request.effective_action == "BUY"
    assert request.available_strategy_capital == 5_000


def test_investor_override_routes_effective_action() -> None:
    _, _, coordinator = _setup()
    request = coordinator.route(
        _governance(
            state=DecisionState.OVERRIDDEN_BY_INVESTOR,
            investor_decision=InvestorDecision.OVERRIDE,
            effective_action=EnterpriseDecisionAction.HOLD,
        ),
        strategy_id="DIVIDEND",
        requested_capital=500,
        rationale="Honor investor override",
    )
    assert request.effective_action == "HOLD"


def test_unapproved_decision_is_rejected() -> None:
    _, _, coordinator = _setup()
    with pytest.raises(PlatformValidationError):
        coordinator.route(
            _governance(state=DecisionState.INVESTOR_OVERRIDE_PENDING),
            strategy_id="DIVIDEND",
            requested_capital=500,
            rationale="Not approved",
        )


def test_rejected_investor_decision_is_rejected() -> None:
    _, _, coordinator = _setup()
    with pytest.raises(PlatformValidationError):
        coordinator.route(
            _governance(state=DecisionState.ARCHIVED, investor_decision=InvestorDecision.REJECT),
            strategy_id="DIVIDEND",
            requested_capital=500,
            rationale="Rejected",
        )


def test_unfunded_strategy_is_rejected() -> None:
    _, _, coordinator = _setup(funded=False)
    with pytest.raises(PlatformValidationError):
        coordinator.route(
            _governance(), strategy_id="DIVIDEND", requested_capital=500, rationale="No capital"
        )


def test_request_cannot_exceed_isolated_strategy_allocation() -> None:
    _, _, coordinator = _setup()
    with pytest.raises(PlatformValidationError):
        coordinator.route(
            _governance(), strategy_id="DIVIDEND", requested_capital=6_000, rationale="Too much"
        )


def test_unready_strategy_is_rejected() -> None:
    _, _, coordinator = _setup(status=StrategyStatus.SUSPENDED)
    with pytest.raises(PlatformValidationError):
        coordinator.route(
            _governance(), strategy_id="DIVIDEND", requested_capital=500, rationale="Suspended"
        )


def test_decision_must_include_target_strategy_advisory() -> None:
    _, _, coordinator = _setup()
    with pytest.raises(PlatformValidationError):
        coordinator.route(
            _governance(strategy_id="SWING"),
            strategy_id="DIVIDEND",
            requested_capital=500,
            rationale="Wrong strategy",
        )


def test_strategy_response_is_append_only_and_isolated() -> None:
    _, _, coordinator = _setup()
    request = coordinator.route(
        _governance(), strategy_id="DIVIDEND", requested_capital=500, rationale="Route"
    )
    response = coordinator.respond(
        request.request_id,
        strategy_id="DIVIDEND",
        status=StrategyResponseStatus.ACCEPTED,
        explanation="Accepted for paper processing.",
    )
    assert response.status is StrategyResponseStatus.ACCEPTED
    with pytest.raises(PlatformValidationError):
        coordinator.respond(
            request.request_id,
            strategy_id="DIVIDEND",
            status=StrategyResponseStatus.DEFERRED,
            explanation="Second response.",
        )


def test_other_strategy_cannot_respond() -> None:
    registry, capital, coordinator = _setup()
    registry.register(_definition("SWING"))
    request = coordinator.route(
        _governance(), strategy_id="DIVIDEND", requested_capital=500, rationale="Route"
    )
    with pytest.raises(PlatformValidationError):
        coordinator.respond(
            request.request_id,
            strategy_id="SWING",
            status=StrategyResponseStatus.REJECTED,
            explanation="Cross-strategy response.",
        )


def test_history_returns_immutable_tuples() -> None:
    _, _, coordinator = _setup()
    request = coordinator.route(
        _governance(), strategy_id="DIVIDEND", requested_capital=500, rationale="Route"
    )
    coordinator.respond(
        request.request_id,
        strategy_id="DIVIDEND",
        status=StrategyResponseStatus.DEFERRED,
        explanation="Await more evidence.",
    )
    assert isinstance(coordinator.requests(), tuple)
    assert isinstance(coordinator.responses(), tuple)


def test_json_and_markdown_outputs_preserve_execution_boundary() -> None:
    _, _, coordinator = _setup()
    request = coordinator.route(
        _governance(), strategy_id="DIVIDEND", requested_capital=500, rationale="Route"
    )
    snapshot = coordinator.snapshot(request.request_id)
    json_output = coordinator.render_json(snapshot)
    markdown = coordinator.render_markdown(snapshot)
    assert '"broker_execution_enabled": false' in json_output
    assert "does not reserve capital, place orders, or call broker APIs" in markdown


def test_request_validation_rejects_unsafe_or_invalid_values() -> None:
    _, _, coordinator = _setup()
    request = coordinator.route(
        _governance(), strategy_id="DIVIDEND", requested_capital=500, rationale="Route"
    )
    with pytest.raises(PlatformValidationError):
        replace(request, paper_trade_mode=False).validate()
    with pytest.raises(PlatformValidationError):
        replace(request, requested_capital=0).validate()


def test_coordinator_has_no_broker_or_order_interface() -> None:
    _, _, coordinator = _setup()
    assert not hasattr(coordinator, "place_order")
    assert not hasattr(coordinator, "broker_request")
    assert not hasattr(coordinator, "execute_live_trade")
