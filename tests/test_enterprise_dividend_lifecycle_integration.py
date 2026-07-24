from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from types import MappingProxyType
from uuid import uuid4

import pytest

from src.dividend_bot.enterprise_dividend_lifecycle_integration import (
    DividendLifecycleEvent,
    EnterpriseDividendLifecycleIntegration,
)
from src.dividend_bot.enterprise_portfolio_lifecycle_integration import (
    EnterprisePortfolioLifecycleRecord,
    PortfolioLifecycleAction,
)
from src.dividend_bot.platform_foundation import PlatformValidationError


def _source() -> EnterprisePortfolioLifecycleRecord:
    return EnterprisePortfolioLifecycleRecord(
        lifecycle_record_id=uuid4(), sequence=1, portfolio_integration_id=uuid4(),
        ledger_entry_id=uuid4(), workflow_id="WF-DIV-2026-000001",
        correlation_id="WF-DIV-2026-000001", decision_internal_id=uuid4(),
        decision_public_id="DEC-2026-000001", company_id=uuid4(), profile_id=uuid4(),
        strategy_id="DIVIDEND", evidence_ids=(uuid4(),), action=PortfolioLifecycleAction.REVIEW,
        reason="Dividend lifecycle review", metadata=MappingProxyType({"append_only": True}),
    )


def _announce(service: EnterpriseDividendLifecycleIntegration, source=None):
    return service.record(source or _source(), event=DividendLifecycleEvent.ANNOUNCED,
                          reason="Quarterly dividend announced", effective_date=date(2026, 8, 1),
                          amount_per_share=0.25)


def test_announcement_creates_record():
    result = _announce(EnterpriseDividendLifecycleIntegration())
    assert result.record.sequence == 1


def test_links_are_preserved():
    source = _source()
    record = _announce(EnterpriseDividendLifecycleIntegration(), source).record
    assert record.portfolio_integration_id == source.portfolio_integration_id
    assert record.decision_internal_id == source.decision_internal_id
    assert record.evidence_ids == source.evidence_ids


def test_date_sequence_is_valid():
    service, source = EnterpriseDividendLifecycleIntegration(), _source()
    first = _announce(service, source).record
    second = service.record(source, event=DividendLifecycleEvent.EX_DATE, reason="Ex date", effective_date=date(2026, 8, 10)).record
    third = service.record(source, event=DividendLifecycleEvent.RECORD_DATE, reason="Record date", effective_date=date(2026, 8, 11)).record
    assert (first.sequence, second.sequence, third.sequence) == (1, 2, 3)
    assert third.supersedes_dividend_record_id == second.dividend_record_id


def test_received_requires_total_amount():
    service, source = EnterpriseDividendLifecycleIntegration(), _source()
    _announce(service, source)
    service.record(source, event=DividendLifecycleEvent.EX_DATE, reason="Ex", effective_date=date(2026, 8, 10))
    service.record(source, event=DividendLifecycleEvent.RECORD_DATE, reason="Record", effective_date=date(2026, 8, 11))
    service.record(source, event=DividendLifecycleEvent.PAYMENT_DATE, reason="Pay", effective_date=date(2026, 8, 20))
    with pytest.raises(PlatformValidationError):
        service.record(source, event=DividendLifecycleEvent.RECEIVED, reason="Receipt", amount_per_share=0.25)


def test_received_is_recorded_without_cash_movement():
    service, source = EnterpriseDividendLifecycleIntegration(), _source()
    _announce(service, source)
    service.record(source, event=DividendLifecycleEvent.EX_DATE, reason="Ex", effective_date=date(2026, 8, 10))
    service.record(source, event=DividendLifecycleEvent.RECORD_DATE, reason="Record", effective_date=date(2026, 8, 11))
    service.record(source, event=DividendLifecycleEvent.PAYMENT_DATE, reason="Pay", effective_date=date(2026, 8, 20))
    result = service.record(source, event=DividendLifecycleEvent.RECEIVED, reason="Receipt", amount_per_share=0.25, total_amount=25.0)
    assert result.record.total_amount == 25.0
    assert result.record.metadata["cash_moved"] is False


def test_suspend_then_reinstate():
    service, source = EnterpriseDividendLifecycleIntegration(), _source()
    _announce(service, source)
    suspended = service.record(source, event=DividendLifecycleEvent.SUSPENDED, reason="Suspended").record
    reinstated = service.record(source, event=DividendLifecycleEvent.REINSTATED, reason="Reinstated", amount_per_share=0.10).record
    assert reinstated.supersedes_dividend_record_id == suspended.dividend_record_id


def test_invalid_initial_transition_is_rejected():
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendLifecycleIntegration().record(_source(), event=DividendLifecycleEvent.RECEIVED,
                                                         reason="Invalid", amount_per_share=0.25, total_amount=25.0)


def test_announcement_requires_date():
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendLifecycleIntegration().record(_source(), event=DividendLifecycleEvent.ANNOUNCED,
                                                         reason="Missing date", amount_per_share=0.25)


def test_announcement_requires_amount():
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendLifecycleIntegration().record(_source(), event=DividendLifecycleEvent.ANNOUNCED,
                                                         reason="Missing amount", effective_date=date(2026, 8, 1))


def test_negative_amount_is_rejected():
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendLifecycleIntegration().record(_source(), event=DividendLifecycleEvent.ANNOUNCED,
                                                         reason="Negative", effective_date=date(2026, 8, 1), amount_per_share=-0.01)


def test_naive_timestamp_is_rejected():
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendLifecycleIntegration().record(_source(), event=DividendLifecycleEvent.ANNOUNCED,
                                                         reason="Naive", effective_date=date(2026, 8, 1),
                                                         amount_per_share=0.25, completed_at=datetime(2026, 7, 24))


def test_duplicate_record_id_is_rejected():
    service = EnterpriseDividendLifecycleIntegration()
    record = _announce(service).record
    duplicate = replace(record, sequence=2, supersedes_dividend_record_id=record.dividend_record_id)
    with pytest.raises(PlatformValidationError):
        service.ledger.append(duplicate)


def test_history_and_ledger_are_immutable_snapshots():
    service = EnterpriseDividendLifecycleIntegration()
    _announce(service)
    assert isinstance(service.history(), tuple)
    assert isinstance(service.ledger.all(), tuple)


def test_json_and_markdown_preserve_boundaries():
    service = EnterpriseDividendLifecycleIntegration()
    result = _announce(service)
    assert '"cash_moved": false' in service.render_json(result)
    assert "does not mutate holdings" in service.render_markdown(result)


def test_unsafe_flags_are_rejected():
    result = _announce(EnterpriseDividendLifecycleIntegration())
    with pytest.raises(PlatformValidationError):
        replace(result.record, paper_trade_mode=False).validate()


def test_service_exposes_no_mutation_method():
    service = EnterpriseDividendLifecycleIntegration()
    assert not hasattr(service, "mutate_holdings")
