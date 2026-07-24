from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.dividend_bot.enterprise_ai_cio_runtime import EnterpriseRecommendation
from src.dividend_bot.enterprise_decision_engine import EnterpriseDecisionAction, StrategyAdvisory
from src.dividend_bot.enterprise_event_bus import EnterpriseEventBus, EnterpriseEventType
from src.dividend_bot.enterprise_event_integration import EnterpriseEventIntegration
from src.dividend_bot.enterprise_intelligence_service import IntelligenceContribution
from src.dividend_bot.enterprise_workflow_orchestrator import EnterpriseWorkflowOrchestrator, EnterpriseWorkflowRequest
from src.dividend_bot.platform_entities import MasterCompanyIntelligenceProfile, new_identity
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now
from src.dividend_bot.platform_integration import ServiceDomain


def _request() -> EnterpriseWorkflowRequest:
    profile = MasterCompanyIntelligenceProfile(
        identity=new_identity("MCI"), company_id=uuid4(), evidence_ids=(uuid4(),), quality_score=80.0
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
        IntelligenceContribution(f"{domain.value.upper()}_SERVICE", domain, {"score": 80.0})
        for domain in domains
    )
    advisory = StrategyAdvisory(
        strategy_id="DIVIDEND",
        action=EnterpriseDecisionAction.BUY,
        confidence=80,
        opportunity_quality=75,
        rationale="Dividend strategy supports governed review.",
        service_id="DIVIDEND_ADAPTER",
    )
    return EnterpriseWorkflowRequest(
        profile=profile,
        contributions=contributions,
        strategy_advisories=(advisory,),
        proposed_recommendation=EnterpriseRecommendation.BUY,
        confidence=80,
        stability_checked=True,
        rationale="Enterprise intelligence supports review.",
        evidence_count=1,
    )


def _result():
    return EnterpriseWorkflowOrchestrator().prepare_for_investor_review(_request())


def test_publishes_expected_workflow_sequence() -> None:
    record = EnterpriseEventIntegration().publish_workflow(_result())
    assert tuple(p.event.event_type for p in record.publications) == (
        EnterpriseEventType.INTELLIGENCE_UPDATED,
        EnterpriseEventType.CIO_ADVISORY_CREATED,
        EnterpriseEventType.DECISION_CREATED,
        EnterpriseEventType.DECISION_GOVERNANCE_UPDATED,
    )


def test_all_events_preserve_correlation_id() -> None:
    record = EnterpriseEventIntegration().publish_workflow(_result())
    assert all(p.event.correlation_id == record.workflow_id for p in record.publications)


def test_events_preserve_causation_chain() -> None:
    record = EnterpriseEventIntegration().publish_workflow(_result())
    assert record.publications[0].event.causation_id is None
    for previous, current in zip(record.publications, record.publications[1:]):
        assert current.event.causation_id == previous.event.event_id


def test_dividend_strategy_scope_is_preserved() -> None:
    record = EnterpriseEventIntegration().publish_workflow(_result())
    assert all(p.event.strategy_id == "DIVIDEND" for p in record.publications)


def test_enterprise_subscriber_receives_event() -> None:
    received = []
    bus = EnterpriseEventBus()
    bus.subscribe("AUDITOR", EnterpriseEventType.DECISION_CREATED, lambda event: received.append(event))
    EnterpriseEventIntegration(bus).publish_workflow(_result())
    assert len(received) == 1


def test_strategy_subscriber_receives_matching_event() -> None:
    received = []
    bus = EnterpriseEventBus()
    bus.subscribe("DIVIDEND_VIEW", EnterpriseEventType.DECISION_CREATED, lambda event: received.append(event), strategy_id="DIVIDEND")
    EnterpriseEventIntegration(bus).publish_workflow(_result())
    assert len(received) == 1


def test_other_strategy_subscriber_does_not_receive_event() -> None:
    received = []
    bus = EnterpriseEventBus()
    bus.subscribe("SWING_VIEW", EnterpriseEventType.DECISION_CREATED, lambda event: received.append(event), strategy_id="SWING")
    EnterpriseEventIntegration(bus).publish_workflow(_result())
    assert received == []


def test_duplicate_workflow_publication_is_rejected() -> None:
    integration = EnterpriseEventIntegration()
    result = _result()
    integration.publish_workflow(result)
    with pytest.raises(PlatformValidationError):
        integration.publish_workflow(result)


def test_history_is_append_only_tuple_snapshot() -> None:
    integration = EnterpriseEventIntegration()
    integration.publish_workflow(_result())
    assert isinstance(integration.history(), tuple)
    assert len(integration.history()) == 1


def test_naive_publication_timestamp_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        EnterpriseEventIntegration().publish_workflow(_result(), published_at=datetime(2026, 7, 24))


def test_handler_failure_does_not_block_later_subscriber() -> None:
    received = []
    bus = EnterpriseEventBus()
    def fail(_event):
        raise RuntimeError("failure")
    bus.subscribe("FAILURE", EnterpriseEventType.DECISION_CREATED, fail)
    bus.subscribe("LATER", EnterpriseEventType.DECISION_CREATED, lambda event: received.append(event))
    record = EnterpriseEventIntegration(bus).publish_workflow(_result())
    decision_publication = record.publications[2]
    assert decision_publication.deliveries[0].accepted is False
    assert decision_publication.deliveries[1].accepted is True
    assert len(received) == 1


def test_json_and_markdown_preserve_boundaries() -> None:
    integration = EnterpriseEventIntegration()
    record = integration.publish_workflow(_result())
    json_output = integration.render_json(record)
    markdown = integration.render_markdown(record)
    assert '"broker_execution_enabled": false' in json_output
    assert "Investor approval, capital assignment, portfolio mutation, broker calls, and order placement are not performed" in markdown


def test_record_rejects_unsafe_flags() -> None:
    record = EnterpriseEventIntegration().publish_workflow(_result())
    with pytest.raises(PlatformValidationError):
        replace(record, paper_trade_mode=False).validate()


def test_publications_are_append_only_bus_history() -> None:
    integration = EnterpriseEventIntegration()
    record = integration.publish_workflow(_result())
    assert integration.event_bus.history() == record.publications


def test_event_payload_marks_investor_review_required() -> None:
    record = EnterpriseEventIntegration().publish_workflow(_result())
    assert record.publications[-1].event.payload["investor_review_required"] is True


def test_integration_has_no_execution_interfaces() -> None:
    integration = EnterpriseEventIntegration()
    assert not hasattr(integration, "approve_investor_decision")
    assert not hasattr(integration, "assign_capital")
    assert not hasattr(integration, "place_order")
