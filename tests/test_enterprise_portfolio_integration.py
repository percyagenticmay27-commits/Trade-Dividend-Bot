from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from types import MappingProxyType
from uuid import uuid4

import pytest

from src.dividend_bot.enterprise_decision_ledger_integration import (
    EnterpriseDecisionLedgerEntry,
    EnterpriseDecisionLedgerIntegrationResult,
)
from src.dividend_bot.enterprise_portfolio_integration import (
    EnterprisePortfolioIntegration,
    EnterprisePortfolioIntegrationLedger,
    EnterprisePortfolioIntegrationRecord,
)
from src.dividend_bot.enterprise_strategy_execution import StrategyExecutionRequest
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now


def _decision_result(*, strategy_ids: tuple[str, ...] = ("DIVIDEND",), supersedes=None):
    entry = EnterpriseDecisionLedgerEntry(
        ledger_entry_id=uuid4(),
        sequence=1,
        workflow_id="WF-DEC-2026-000001",
        correlation_id="WF-DEC-2026-000001",
        decision_internal_id=uuid4(),
        decision_public_id="DEC-2026-000001",
        company_id=uuid4(),
        profile_id=uuid4(),
        action="BUY",
        decision_state="IMPLEMENTED",
        strategy_ids=strategy_ids,
        evidence_ids=(uuid4(), uuid4()),
        supersedes_decision_id=supersedes,
        metadata=MappingProxyType(
            {
                "constitution_version": "1.0.0",
                "investor_status": "APPROVED",
                "append_only": True,
            }
        ),
    )
    result = EnterpriseDecisionLedgerIntegrationResult(
        integration_id=uuid4(), entry=entry, completed_at=utc_now()
    )
    result.validate()
    return result


def _request(result, *, strategy_id="DIVIDEND", decision_id=None, public_id=None, capital=100.0):
    entry = result.entry
    request = StrategyExecutionRequest(
        request_id=uuid4(),
        decision_id=decision_id or entry.decision_internal_id,
        decision_public_id=public_id or entry.decision_public_id,
        strategy_id=strategy_id,
        effective_action="BUY",
        requested_capital=capital,
        available_strategy_capital=1000.0,
        rationale="Approved paper portfolio intent",
    )
    request.validate()
    return request


def test_valid_ledger_decision_creates_portfolio_integration() -> None:
    decision = _decision_result()
    result = EnterprisePortfolioIntegration().integrate(decision, _request(decision))
    assert result.record.decision_public_id == decision.entry.decision_public_id


def test_decision_chain_is_preserved() -> None:
    decision = _decision_result()
    result = EnterprisePortfolioIntegration().integrate(decision, _request(decision))
    assert result.record.decision_internal_id == decision.entry.decision_internal_id
    assert result.record.ledger_entry_id == decision.entry.ledger_entry_id


def test_evidence_chain_is_preserved() -> None:
    decision = _decision_result()
    result = EnterprisePortfolioIntegration().integrate(decision, _request(decision))
    assert result.record.evidence_ids == decision.entry.evidence_ids


def test_company_and_profile_links_are_preserved() -> None:
    decision = _decision_result()
    result = EnterprisePortfolioIntegration().integrate(decision, _request(decision))
    assert result.record.company_id == decision.entry.company_id
    assert result.record.profile_id == decision.entry.profile_id


def test_workflow_and_correlation_are_preserved() -> None:
    decision = _decision_result()
    result = EnterprisePortfolioIntegration().integrate(decision, _request(decision))
    assert result.record.workflow_id == decision.entry.workflow_id
    assert result.record.correlation_id == decision.entry.correlation_id


def test_duplicate_execution_request_is_rejected() -> None:
    decision = _decision_result()
    request = _request(decision)
    integration = EnterprisePortfolioIntegration()
    integration.integrate(decision, request)
    with pytest.raises(PlatformValidationError):
        integration.integrate(decision, request)


def test_duplicate_ledger_entry_is_rejected() -> None:
    decision = _decision_result()
    integration = EnterprisePortfolioIntegration()
    integration.integrate(decision, _request(decision))
    with pytest.raises(PlatformValidationError):
        integration.integrate(decision, _request(decision))


def test_non_dividend_strategy_is_rejected() -> None:
    decision = _decision_result(strategy_ids=("SWING",))
    with pytest.raises(PlatformValidationError):
        EnterprisePortfolioIntegration().integrate(decision, _request(decision, strategy_id="SWING"))


def test_strategy_missing_from_ledger_is_rejected() -> None:
    decision = _decision_result(strategy_ids=("SWING",))
    request = _request(decision, strategy_id="DIVIDEND")
    with pytest.raises(PlatformValidationError):
        EnterprisePortfolioIntegration().integrate(decision, request)


def test_internal_decision_mismatch_is_rejected() -> None:
    decision = _decision_result()
    with pytest.raises(PlatformValidationError):
        EnterprisePortfolioIntegration().integrate(decision, _request(decision, decision_id=uuid4()))


def test_public_decision_mismatch_is_rejected() -> None:
    decision = _decision_result()
    with pytest.raises(PlatformValidationError):
        EnterprisePortfolioIntegration().integrate(decision, _request(decision, public_id="DEC-OTHER"))


def test_naive_completed_at_is_rejected() -> None:
    decision = _decision_result()
    with pytest.raises(PlatformValidationError):
        EnterprisePortfolioIntegration().integrate(
            decision, _request(decision), completed_at=datetime(2026, 7, 24)
        )


def test_record_rejects_unsafe_flags() -> None:
    decision = _decision_result()
    record = EnterprisePortfolioIntegration().integrate(decision, _request(decision)).record
    with pytest.raises(PlatformValidationError):
        replace(record, paper_trade_mode=False).validate()
    with pytest.raises(PlatformValidationError):
        replace(record, broker_execution_enabled=True).validate()


def test_history_and_ledger_are_immutable_tuple_snapshots() -> None:
    decision = _decision_result()
    integration = EnterprisePortfolioIntegration()
    integration.integrate(decision, _request(decision))
    assert isinstance(integration.history(), tuple)
    assert isinstance(integration.ledger.all(), tuple)


def test_json_and_markdown_preserve_safety_boundary() -> None:
    decision = _decision_result()
    integration = EnterprisePortfolioIntegration()
    result = integration.integrate(decision, _request(decision))
    json_output = integration.render_json(result)
    markdown = integration.render_markdown(result)
    assert '"portfolio_mutated": false' in json_output
    assert "does not reserve capital, mutate holdings, call brokers, or place orders" in markdown


def test_integration_has_no_execution_interfaces() -> None:
    integration = EnterprisePortfolioIntegration()
    assert not hasattr(integration, "open_position")
    assert not hasattr(integration, "close_position")
    assert not hasattr(integration, "place_order")
    assert not hasattr(integration, "reserve_capital")
