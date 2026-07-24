from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from types import MappingProxyType
from uuid import uuid4

import pytest

from src.dividend_bot.enterprise_ai_cio_runtime import EnterpriseRecommendation
from src.dividend_bot.enterprise_decision_engine import EnterpriseDecisionAction, StrategyAdvisory
from src.dividend_bot.enterprise_intelligence_integration import EnterpriseIntelligenceIntegration
from src.dividend_bot.enterprise_intelligence_service import IntelligenceContribution
from src.dividend_bot.enterprise_workflow_orchestrator import EnterpriseWorkflowOrchestrator, EnterpriseWorkflowRequest
from src.dividend_bot.platform_entities import MasterCompanyIntelligenceProfile, new_identity
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now
from src.dividend_bot.platform_integration import ServiceDomain


def _workflow():
    profile = MasterCompanyIntelligenceProfile(
        identity=new_identity("MCI"),
        company_id=uuid4(),
        evidence_ids=(uuid4(),),
        quality_score=82.0,
    )
    domains = (
        ServiceDomain.FUNDAMENTALS,
        ServiceDomain.INCOME,
        ServiceDomain.FINANCIAL_HEALTH,
        ServiceDomain.RISK,
        ServiceDomain.MARKET_INTELLIGENCE,
        ServiceDomain.TECHNICAL,
        ServiceDomain.EARNINGS,
    )
    contributions = tuple(
        IntelligenceContribution(f"{domain.value.upper()}_SERVICE", domain, {"score": 82.0})
        for domain in domains
    )
    advisory = StrategyAdvisory(
        strategy_id="DIVIDEND",
        action=EnterpriseDecisionAction.BUY,
        confidence=82,
        opportunity_quality=80,
        rationale="Dividend strategy supports governed paper review.",
        service_id="DIVIDEND_ADAPTER",
    )
    request = EnterpriseWorkflowRequest(
        profile=profile,
        contributions=contributions,
        strategy_advisories=(advisory,),
        proposed_recommendation=EnterpriseRecommendation.BUY,
        confidence=82,
        stability_checked=True,
        rationale="Enterprise intelligence supports investor review.",
        evidence_count=1,
    )
    return EnterpriseWorkflowOrchestrator().prepare_for_investor_review(request)


def test_integrate_preserves_workflow_profile_company_and_decision_links() -> None:
    workflow = _workflow()
    result = EnterpriseIntelligenceIntegration().integrate(workflow)
    assert result.workflow_id == workflow.workflow_id
    assert result.profile_id == workflow.intelligence.profile.identity.internal_id
    assert result.company_id == workflow.intelligence.profile.company_id
    assert result.decision_id == workflow.decision.identity.public_id


def test_integrate_publishes_expected_event_sequence() -> None:
    result = EnterpriseIntelligenceIntegration().integrate(_workflow())
    assert tuple(item.event.event_type.value for item in result.event_record.publications) == (
        "INTELLIGENCE_UPDATED",
        "CIO_ADVISORY_CREATED",
        "DECISION_CREATED",
        "DECISION_GOVERNANCE_UPDATED",
    )


def test_integrate_preserves_each_event_as_evidence() -> None:
    result = EnterpriseIntelligenceIntegration().integrate(_workflow())
    event_ids = tuple(item.event.event_id for item in result.event_record.publications)
    evidence_ids = tuple(item.source_event_id for item in result.evidence_result.entries)
    assert evidence_ids == event_ids


def test_integrate_preserves_dividend_strategy_scope() -> None:
    result = EnterpriseIntelligenceIntegration().integrate(_workflow())
    assert {item.event.strategy_id for item in result.event_record.publications} == {"DIVIDEND"}
    assert {item.strategy_id for item in result.evidence_result.entries} == {"DIVIDEND"}


def test_integrate_preserves_shared_correlation_id() -> None:
    result = EnterpriseIntelligenceIntegration().integrate(_workflow())
    assert result.event_record.correlation_id == result.evidence_result.correlation_id
    assert result.event_record.correlation_id == result.workflow_id


def test_duplicate_workflow_integration_is_rejected() -> None:
    service = EnterpriseIntelligenceIntegration()
    workflow = _workflow()
    service.integrate(workflow)
    with pytest.raises(PlatformValidationError):
        service.integrate(workflow)


def test_history_is_append_only_tuple_snapshot() -> None:
    service = EnterpriseIntelligenceIntegration()
    service.integrate(_workflow())
    assert isinstance(service.history(), tuple)
    assert len(service.history()) == 1


def test_event_and_evidence_histories_are_populated() -> None:
    service = EnterpriseIntelligenceIntegration()
    service.integrate(_workflow())
    assert len(service.event_integration.history()) == 1
    assert len(service.evidence_integration.history()) == 1
    assert len(service.evidence_integration.repository.all()) == 4


def test_metadata_is_immutable_and_preserves_quality_metrics() -> None:
    workflow = _workflow()
    result = EnterpriseIntelligenceIntegration().integrate(workflow)
    assert isinstance(result.metadata, MappingProxyType)
    assert result.metadata["intelligence_quality"] == workflow.intelligence.quality_score
    assert result.metadata["intelligence_completeness"] == workflow.intelligence.completeness_score
    with pytest.raises(TypeError):
        result.metadata["changed"] = True


def test_naive_completed_timestamp_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        EnterpriseIntelligenceIntegration().integrate(_workflow(), completed_at=datetime(2026, 7, 24))


def test_result_rejects_mismatched_event_workflow() -> None:
    result = EnterpriseIntelligenceIntegration().integrate(_workflow())
    invalid_event_record = replace(result.event_record, workflow_id="WF-OTHER")
    with pytest.raises(PlatformValidationError):
        replace(result, event_record=invalid_event_record).validate()


def test_result_rejects_broken_event_evidence_order() -> None:
    result = EnterpriseIntelligenceIntegration().integrate(_workflow())
    reversed_entries = tuple(reversed(result.evidence_result.entries))
    invalid_evidence = replace(result.evidence_result, entries=reversed_entries)
    with pytest.raises(PlatformValidationError):
        replace(result, evidence_result=invalid_evidence).validate()


def test_json_and_markdown_preserve_safety_boundary() -> None:
    service = EnterpriseIntelligenceIntegration()
    result = service.integrate(_workflow(), completed_at=utc_now())
    json_output = service.render_json(result)
    markdown = service.render_markdown(result)
    assert '"broker_execution_enabled": false' in json_output
    assert "does not approve decisions, assign capital, mutate portfolios, call brokers, or place orders" in markdown


def test_result_rejects_unsafe_flags() -> None:
    result = EnterpriseIntelligenceIntegration().integrate(_workflow())
    with pytest.raises(PlatformValidationError):
        replace(result, paper_trade_mode=False).validate()


def test_integration_has_no_execution_interfaces() -> None:
    service = EnterpriseIntelligenceIntegration()
    assert not hasattr(service, "approve_investor_decision")
    assert not hasattr(service, "assign_capital")
    assert not hasattr(service, "open_position")
    assert not hasattr(service, "place_order")
