from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from types import MappingProxyType
from uuid import uuid4

import pytest

from src.dividend_bot.enterprise_portfolio_integration import EnterprisePortfolioIntegrationRecord
from src.dividend_bot.enterprise_portfolio_lifecycle_integration import (
    EnterprisePortfolioLifecycleIntegration,
    EnterprisePortfolioLifecycleLedger,
    EnterprisePortfolioLifecycleRecord,
    PortfolioLifecycleAction,
)
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now


def _portfolio() -> EnterprisePortfolioIntegrationRecord:
    record = EnterprisePortfolioIntegrationRecord(
        integration_id=uuid4(), sequence=1, ledger_entry_id=uuid4(), workflow_id="WF-1",
        correlation_id="COR-1", decision_internal_id=uuid4(), decision_public_id="DEC-2026-000001",
        company_id=uuid4(), profile_id=uuid4(), strategy_id="DIVIDEND", execution_request_id=uuid4(),
        effective_action="BUY", requested_capital=1000.0, evidence_ids=(uuid4(),),
        constitution_version="1.0.0", metadata=MappingProxyType({"portfolio_mutated": False}),
    )
    record.validate()
    return record


def test_review_creates_lifecycle_record() -> None:
    result = EnterprisePortfolioLifecycleIntegration().record(_portfolio(), action=PortfolioLifecycleAction.REVIEW, reason="Scheduled review")
    assert result.record.action is PortfolioLifecycleAction.REVIEW


def test_links_are_preserved() -> None:
    portfolio = _portfolio()
    result = EnterprisePortfolioLifecycleIntegration().record(portfolio, action=PortfolioLifecycleAction.REVIEW, reason="Review")
    assert result.record.workflow_id == portfolio.workflow_id
    assert result.record.evidence_ids == portfolio.evidence_ids
    assert result.record.decision_internal_id == portfolio.decision_internal_id


def test_mark_requires_price() -> None:
    with pytest.raises(PlatformValidationError):
        EnterprisePortfolioLifecycleIntegration().record(_portfolio(), action=PortfolioLifecycleAction.MARK, reason="Mark")


def test_mark_accepts_price() -> None:
    result = EnterprisePortfolioLifecycleIntegration().record(_portfolio(), action=PortfolioLifecycleAction.MARK, reason="Market close", price=25.0)
    assert result.record.price == 25.0


def test_dividend_accrual_requires_amount() -> None:
    with pytest.raises(PlatformValidationError):
        EnterprisePortfolioLifecycleIntegration().record(_portfolio(), action=PortfolioLifecycleAction.DIVIDEND_ACCRUAL, reason="Dividend")


def test_dividend_accrual_accepts_amount() -> None:
    result = EnterprisePortfolioLifecycleIntegration().record(_portfolio(), action=PortfolioLifecycleAction.DIVIDEND_ACCRUAL, reason="Dividend", amount=12.5)
    assert result.record.amount == 12.5


def test_close_requires_price() -> None:
    integration = EnterprisePortfolioLifecycleIntegration()
    portfolio = _portfolio()
    integration.record(portfolio, action=PortfolioLifecycleAction.REVIEW, reason="Review")
    with pytest.raises(PlatformValidationError):
        integration.record(portfolio, action=PortfolioLifecycleAction.CLOSE, reason="Close")


def test_close_then_archive_is_valid() -> None:
    integration = EnterprisePortfolioLifecycleIntegration()
    portfolio = _portfolio()
    integration.record(portfolio, action=PortfolioLifecycleAction.REVIEW, reason="Review")
    close = integration.record(portfolio, action=PortfolioLifecycleAction.CLOSE, reason="Paper close", price=30.0)
    archive = integration.record(portfolio, action=PortfolioLifecycleAction.ARCHIVE, reason="Archive")
    assert archive.record.supersedes_lifecycle_record_id == close.record.lifecycle_record_id


def test_archive_before_close_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        EnterprisePortfolioLifecycleIntegration().record(_portfolio(), action=PortfolioLifecycleAction.ARCHIVE, reason="Archive")


def test_transition_after_archive_is_rejected() -> None:
    integration = EnterprisePortfolioLifecycleIntegration()
    portfolio = _portfolio()
    integration.record(portfolio, action=PortfolioLifecycleAction.REVIEW, reason="Review")
    integration.record(portfolio, action=PortfolioLifecycleAction.CLOSE, reason="Close", price=30.0)
    integration.record(portfolio, action=PortfolioLifecycleAction.ARCHIVE, reason="Archive")
    with pytest.raises(PlatformValidationError):
        integration.record(portfolio, action=PortfolioLifecycleAction.REVIEW, reason="Again")


def test_sequence_is_global_and_append_only() -> None:
    integration = EnterprisePortfolioLifecycleIntegration()
    first = integration.record(_portfolio(), action=PortfolioLifecycleAction.REVIEW, reason="One")
    second = integration.record(_portfolio(), action=PortfolioLifecycleAction.REVIEW, reason="Two")
    assert (first.record.sequence, second.record.sequence) == (1, 2)


def test_ledger_rejects_duplicate_record_id() -> None:
    ledger = EnterprisePortfolioLifecycleLedger()
    portfolio = _portfolio()
    record = EnterprisePortfolioLifecycleRecord(
        lifecycle_record_id=uuid4(), sequence=1, portfolio_integration_id=portfolio.integration_id,
        ledger_entry_id=portfolio.ledger_entry_id, workflow_id=portfolio.workflow_id, correlation_id=portfolio.correlation_id,
        decision_internal_id=portfolio.decision_internal_id, decision_public_id=portfolio.decision_public_id,
        company_id=portfolio.company_id, profile_id=portfolio.profile_id, strategy_id="DIVIDEND",
        evidence_ids=portfolio.evidence_ids, action=PortfolioLifecycleAction.REVIEW, reason="Review",
    )
    ledger.append(record)
    with pytest.raises(PlatformValidationError):
        ledger.append(replace(record, sequence=2))


def test_naive_completed_at_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        EnterprisePortfolioLifecycleIntegration().record(
            _portfolio(), action=PortfolioLifecycleAction.REVIEW, reason="Review", completed_at=datetime(2026, 7, 24)
        )


def test_history_is_immutable_tuple_snapshot() -> None:
    integration = EnterprisePortfolioLifecycleIntegration()
    integration.record(_portfolio(), action=PortfolioLifecycleAction.REVIEW, reason="Review")
    assert isinstance(integration.history(), tuple)
    assert isinstance(integration.ledger.all(), tuple)


def test_json_and_markdown_preserve_safety_boundary() -> None:
    integration = EnterprisePortfolioLifecycleIntegration()
    result = integration.record(_portfolio(), action=PortfolioLifecycleAction.REVIEW, reason="Review")
    assert '"append_only": true' in integration.render_json(result)
    assert "does not mutate holdings, move capital, call brokers, or place orders" in integration.render_markdown(result)


def test_no_execution_interfaces_exist() -> None:
    integration = EnterprisePortfolioLifecycleIntegration()
    assert not hasattr(integration, "place_order")
    assert not hasattr(integration, "open_position")
    assert not hasattr(integration, "move_capital")
