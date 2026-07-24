from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from uuid import uuid4

import pytest

from src.dividend_bot.enterprise_ai_cio_runtime import EnterpriseRecommendation
from src.dividend_bot.enterprise_decision_engine import EnterpriseDecisionAction, StrategyAdvisory
from src.dividend_bot.enterprise_decision_ledger_integration import (
    EnterpriseDecisionIntegrationLedger,
    EnterpriseDecisionLedgerEntry,
    EnterpriseDecisionLedgerIntegration,
)
from src.dividend_bot.enterprise_intelligence_integration import EnterpriseIntelligenceIntegration
from src.dividend_bot.enterprise_intelligence_service import IntelligenceContribution
from src.dividend_bot.enterprise_workflow_orchestrator import EnterpriseWorkflowOrchestrator, EnterpriseWorkflowRequest
from src.dividend_bot.platform_entities import MasterCompanyIntelligenceProfile, new_identity
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now
from src.dividend_bot.platform_integration import ServiceDomain


def _profile(company_id=None) -> MasterCompanyIntelligenceProfile:
    profile = MasterCompanyIntelligenceProfile(
        identity=new_identity("MCI"),
        company_id=company_id or uuid4(),
        evidence_ids=(uuid4(),),
        quality_score=80.0,
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
    return tuple(IntelligenceContribution(f"{item.value.upper()}_SERVICE", item, {"score": 80.0}) for item in domains)


def _request(profile=None) -> EnterpriseWorkflowRequest:
    return EnterpriseWorkflowRequest(
        profile=profile or _profile(),
        contributions=_contributions(),
        strategy_advisories=(
            StrategyAdvisory(
                strategy_id="DIVIDEND",
                action=EnterpriseDecisionAction.BUY,
                confidence=80,
                opportunity_quality=75,
                rationale="Dividend strategy supports governed paper review.",
                service_id="DIVIDEND_ADAPTER",
            ),
        ),
        proposed_recommendation=EnterpriseRecommendation.BUY,
        confidence=80,
        stability_checked=True,
        rationale="Enterprise intelligence supports review.",
        evidence_count=1,
    )


def _integrated_pair(orchestrator=None, intelligence=None, request=None):
    orchestrator = orchestrator or EnterpriseWorkflowOrchestrator()
    intelligence = intelligence or EnterpriseIntelligenceIntegration()
    workflow = orchestrator.prepare_for_investor_review(request or _request())
    intelligence_result = intelligence.integrate(workflow)
    return workflow, intelligence_result


def test_integrate_preserves_decision_workflow_and_evidence_links() -> None:
    workflow, intelligence = _integrated_pair()
    result = EnterpriseDecisionLedgerIntegration().integrate(workflow, intelligence)
    assert result.entry.workflow_id == workflow.workflow_id
    assert result.entry.decision_public_id == workflow.decision.identity.public_id
    assert result.entry.evidence_ids == tuple(item.evidence_id for item in intelligence.evidence_result.entries)


def test_entry_preserves_company_and_profile_links() -> None:
    workflow, intelligence = _integrated_pair()
    entry = EnterpriseDecisionLedgerIntegration().integrate(workflow, intelligence).entry
    assert entry.company_id == workflow.decision.company_id
    assert entry.profile_id == workflow.decision.profile_id


def test_entry_preserves_dividend_strategy_scope() -> None:
    workflow, intelligence = _integrated_pair()
    entry = EnterpriseDecisionLedgerIntegration().integrate(workflow, intelligence).entry
    assert entry.strategy_ids == ("DIVIDEND",)


def test_ledger_is_append_only_tuple_snapshot() -> None:
    workflow, intelligence = _integrated_pair()
    service = EnterpriseDecisionLedgerIntegration()
    service.integrate(workflow, intelligence)
    assert isinstance(service.ledger.all(), tuple)
    assert isinstance(service.history(), tuple)


def test_duplicate_decision_is_rejected() -> None:
    workflow, intelligence = _integrated_pair()
    service = EnterpriseDecisionLedgerIntegration()
    service.integrate(workflow, intelligence)
    with pytest.raises(PlatformValidationError):
        service.integrate(workflow, intelligence)


def test_duplicate_public_id_is_rejected() -> None:
    workflow, intelligence = _integrated_pair()
    result = EnterpriseDecisionLedgerIntegration().integrate(workflow, intelligence)
    duplicate = replace(result.entry, ledger_entry_id=uuid4(), decision_internal_id=uuid4(), workflow_id="WF-OTHER", sequence=2)
    with pytest.raises(PlatformValidationError):
        EnterpriseDecisionIntegrationLedgerWith(result.entry).append(duplicate)


class EnterpriseDecisionIntegrationLedgerWith(EnterpriseDecisionIntegrationLedger):
    def __init__(self, first):
        super().__init__()
        self.append(first)


def test_missing_superseded_decision_is_rejected() -> None:
    workflow, intelligence = _integrated_pair()
    entry = EnterpriseDecisionLedgerIntegration().integrate(workflow, intelligence).entry
    broken = replace(entry, ledger_entry_id=uuid4(), decision_internal_id=uuid4(), decision_public_id="DEC-OTHER", workflow_id="WF-OTHER", sequence=1, supersedes_decision_id=uuid4())
    with pytest.raises(PlatformValidationError):
        EnterpriseDecisionIntegrationLedger().append(broken)


def test_successive_company_decision_preserves_chain() -> None:
    profile = _profile()
    orchestrator = EnterpriseWorkflowOrchestrator()
    intelligence_service = EnterpriseIntelligenceIntegration()
    ledger_service = EnterpriseDecisionLedgerIntegration()
    first_workflow, first_intelligence = _integrated_pair(orchestrator, intelligence_service, _request(profile))
    first = ledger_service.integrate(first_workflow, first_intelligence)
    second_workflow, second_intelligence = _integrated_pair(orchestrator, intelligence_service, _request(profile))
    second = ledger_service.integrate(second_workflow, second_intelligence)
    assert second.entry.supersedes_decision_id == first.entry.decision_internal_id
    assert len(ledger_service.ledger.for_company(profile.company_id)) == 2


def test_mismatched_workflow_is_rejected() -> None:
    first_workflow, _ = _integrated_pair()
    second_workflow, second_intelligence = _integrated_pair()
    with pytest.raises(PlatformValidationError):
        EnterpriseDecisionLedgerIntegration().integrate(first_workflow, second_intelligence)


def test_mismatched_profile_is_rejected() -> None:
    workflow, intelligence = _integrated_pair()
    broken = replace(intelligence, profile_id=uuid4())
    with pytest.raises(PlatformValidationError):
        EnterpriseDecisionLedgerIntegration().integrate(workflow, broken)


def test_naive_completed_timestamp_is_rejected() -> None:
    workflow, intelligence = _integrated_pair()
    with pytest.raises(PlatformValidationError):
        EnterpriseDecisionLedgerIntegration().integrate(workflow, intelligence, completed_at=datetime(2026, 7, 24))


def test_json_and_markdown_preserve_safety_boundary() -> None:
    workflow, intelligence = _integrated_pair()
    service = EnterpriseDecisionLedgerIntegration()
    result = service.integrate(workflow, intelligence)
    assert '"broker_execution_enabled": false' in service.render_json(result)
    assert "does not approve investors, assign capital, mutate portfolios, call brokers, or place orders" in service.render_markdown(result)


def test_entry_rejects_missing_evidence() -> None:
    workflow, intelligence = _integrated_pair()
    entry = EnterpriseDecisionLedgerIntegration().integrate(workflow, intelligence).entry
    with pytest.raises(PlatformValidationError):
        replace(entry, evidence_ids=()).validate()


def test_result_rejects_unsafe_flags() -> None:
    workflow, intelligence = _integrated_pair()
    result = EnterpriseDecisionLedgerIntegration().integrate(workflow, intelligence)
    with pytest.raises(PlatformValidationError):
        replace(result, paper_trade_mode=False).validate()


def test_integration_has_no_execution_interfaces() -> None:
    service = EnterpriseDecisionLedgerIntegration()
    assert not hasattr(service, "approve_investor_decision")
    assert not hasattr(service, "assign_capital")
    assert not hasattr(service, "mutate_portfolio")
    assert not hasattr(service, "place_order")
