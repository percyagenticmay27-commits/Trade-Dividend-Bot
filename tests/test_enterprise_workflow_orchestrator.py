from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from uuid import uuid4

import pytest

from src.dividend_bot.enterprise_ai_cio_runtime import EnterpriseRecommendation
from src.dividend_bot.enterprise_decision_engine import EnterpriseDecisionAction, StrategyAdvisory
from src.dividend_bot.enterprise_intelligence_service import IntelligenceContribution
from src.dividend_bot.enterprise_workflow_orchestrator import (
    EnterpriseWorkflowOrchestrator,
    EnterpriseWorkflowRequest,
)
from src.dividend_bot.platform_entities import MasterCompanyIntelligenceProfile, new_identity
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now
from src.dividend_bot.platform_integration import ServiceDomain


def _profile(*, quality: float = 80.0) -> MasterCompanyIntelligenceProfile:
    profile = MasterCompanyIntelligenceProfile(
        identity=new_identity("MCI"),
        company_id=uuid4(),
        evidence_ids=(uuid4(),),
        quality_score=quality,
    )
    profile.validate()
    return profile


def _contributions() -> tuple[IntelligenceContribution, ...]:
    domains = (
        ServiceDomain.FUNDAMENTALS,
        ServiceDomain.INCOME,
        ServiceDomain.FINANCIAL_HEALTH,
        ServiceDomain.RISK,
        ServiceDomain.MARKET_INTELLIGENCE,
        ServiceDomain.TECHNICAL,
        ServiceDomain.EARNINGS,
    )
    return tuple(
        IntelligenceContribution(f"{domain.value.upper()}_SERVICE", domain, {"score": 80.0})
        for domain in domains
    )


def _advisory() -> StrategyAdvisory:
    return StrategyAdvisory(
        strategy_id="DIVIDEND",
        action=EnterpriseDecisionAction.BUY,
        confidence=80,
        opportunity_quality=75,
        rationale="Dividend strategy supports a governed paper review.",
        service_id="DIVIDEND_ADAPTER",
    )


def _request(**changes) -> EnterpriseWorkflowRequest:
    request = EnterpriseWorkflowRequest(
        profile=_profile(),
        contributions=_contributions(),
        strategy_advisories=(_advisory(),),
        proposed_recommendation=EnterpriseRecommendation.BUY,
        confidence=80,
        stability_checked=True,
        rationale="Enterprise intelligence supports review.",
        evidence_count=1,
    )
    return replace(request, **changes)


def test_orchestrator_runs_stages_in_dependency_order() -> None:
    result = EnterpriseWorkflowOrchestrator().prepare_for_investor_review(_request())
    assert result.completed_stages == ("INTELLIGENCE", "AI_CIO_ADVISORY", "ENTERPRISE_DECISION")


def test_complete_intelligence_can_prepare_buy_decision() -> None:
    result = EnterpriseWorkflowOrchestrator().prepare_for_investor_review(_request())
    assert result.decision.action is EnterpriseDecisionAction.BUY


def test_missing_intelligence_degrades_to_review() -> None:
    request = _request(contributions=_contributions()[:2])
    result = EnterpriseWorkflowOrchestrator().prepare_for_investor_review(request)
    assert result.decision.action is EnterpriseDecisionAction.REVIEW
    assert result.pipeline.gates_passed is False


def test_missing_stability_degrades_to_review() -> None:
    result = EnterpriseWorkflowOrchestrator().prepare_for_investor_review(
        _request(stability_checked=False)
    )
    assert result.decision.action is EnterpriseDecisionAction.REVIEW


def test_decision_preserves_profile_reference() -> None:
    result = EnterpriseWorkflowOrchestrator().prepare_for_investor_review(_request())
    assert result.decision.profile_id == result.intelligence.profile.identity.internal_id


def test_decision_is_appended_to_shared_ledger() -> None:
    orchestrator = EnterpriseWorkflowOrchestrator()
    result = orchestrator.prepare_for_investor_review(_request())
    assert orchestrator.decision_engine.ledger.all() == (result.decision,)


def test_successive_company_decision_links_previous_decision() -> None:
    orchestrator = EnterpriseWorkflowOrchestrator()
    request = _request()
    first = orchestrator.prepare_for_investor_review(request)
    second = orchestrator.prepare_for_investor_review(request)
    assert second.decision.supersedes_decision_id == first.decision.identity.internal_id


def test_history_is_append_only_tuple_snapshot() -> None:
    orchestrator = EnterpriseWorkflowOrchestrator()
    orchestrator.prepare_for_investor_review(_request())
    assert isinstance(orchestrator.history(), tuple)
    assert len(orchestrator.history()) == 1


def test_request_requires_strategy_advisory() -> None:
    with pytest.raises(PlatformValidationError):
        EnterpriseWorkflowOrchestrator().prepare_for_investor_review(
            _request(strategy_advisories=())
        )


def test_request_rejects_invalid_confidence() -> None:
    with pytest.raises(PlatformValidationError):
        EnterpriseWorkflowOrchestrator().prepare_for_investor_review(_request(confidence=101))


def test_request_rejects_naive_timestamp() -> None:
    with pytest.raises(PlatformValidationError):
        EnterpriseWorkflowOrchestrator().prepare_for_investor_review(
            _request(requested_at=datetime(2026, 7, 24))
        )


def test_completed_timestamp_is_timezone_aware() -> None:
    result = EnterpriseWorkflowOrchestrator().prepare_for_investor_review(
        _request(), completed_at=utc_now()
    )
    assert result.completed_at.tzinfo is not None


def test_json_and_markdown_preserve_investor_boundary() -> None:
    orchestrator = EnterpriseWorkflowOrchestrator()
    result = orchestrator.prepare_for_investor_review(_request())
    json_output = orchestrator.render_json(result)
    markdown = orchestrator.render_markdown(result)
    assert '"broker_execution_enabled": false' in json_output
    assert "Investor approval, capital assignment, portfolio mutation, and broker execution are not performed" in markdown


def test_result_rejects_unsafe_flags() -> None:
    result = EnterpriseWorkflowOrchestrator().prepare_for_investor_review(_request())
    with pytest.raises(PlatformValidationError):
        replace(result, paper_trade_mode=False).validate()


def test_orchestrator_has_no_execution_interfaces() -> None:
    orchestrator = EnterpriseWorkflowOrchestrator()
    assert not hasattr(orchestrator, "approve_investor_decision")
    assert not hasattr(orchestrator, "assign_capital")
    assert not hasattr(orchestrator, "place_order")
