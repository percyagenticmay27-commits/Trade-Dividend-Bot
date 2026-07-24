from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from types import MappingProxyType
from uuid import uuid4

import pytest

from src.dividend_bot.enterprise_dividend_income_integration import (
    EnterpriseDividendIncomeIntegration,
    EnterpriseDividendIncomeLedger,
)
from src.dividend_bot.enterprise_dividend_lifecycle_integration import (
    DividendLifecycleEvent,
    EnterpriseDividendLifecycleRecord,
)
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now


def _records() -> tuple[EnterpriseDividendLifecycleRecord, ...]:
    common = dict(
        portfolio_lifecycle_record_id=uuid4(),
        portfolio_integration_id=uuid4(),
        ledger_entry_id=uuid4(),
        workflow_id="WF-DEC-2026-000001",
        correlation_id="WF-DEC-2026-000001",
        decision_internal_id=uuid4(),
        decision_public_id="DEC-2026-000001",
        company_id=uuid4(),
        profile_id=uuid4(),
        strategy_id="DIVIDEND",
        evidence_ids=(uuid4(), uuid4()),
        reason="Paper dividend lifecycle",
        recorded_at=utc_now(),
        metadata=MappingProxyType({"cash_moved": False}),
    )
    announced = EnterpriseDividendLifecycleRecord(
        dividend_record_id=uuid4(), sequence=1, event=DividendLifecycleEvent.ANNOUNCED,
        effective_date=date(2026, 8, 1), amount_per_share=0.50, total_amount=50.0,
        **common,
    )
    received = EnterpriseDividendLifecycleRecord(
        dividend_record_id=uuid4(), sequence=2, event=DividendLifecycleEvent.RECEIVED,
        amount_per_share=0.50, total_amount=50.0,
        supersedes_dividend_record_id=announced.dividend_record_id,
        **common,
    )
    announced.validate()
    received.validate()
    return announced, received


def test_summary_aggregates_announced_and_received_income() -> None:
    result = EnterpriseDividendIncomeIntegration().summarize(_records())
    assert result.record.announced_income == 50.0
    assert result.record.received_income == 50.0
    assert result.record.pending_income == 0.0


def test_summary_counts_received_payments() -> None:
    result = EnterpriseDividendIncomeIntegration().summarize(_records())
    assert result.record.payment_count == 1


def test_summary_preserves_decision_and_workflow_links() -> None:
    records = _records()
    result = EnterpriseDividendIncomeIntegration().summarize(records)
    assert result.record.workflow_id == records[0].workflow_id
    assert result.record.decision_internal_id == records[0].decision_internal_id
    assert result.record.decision_public_id == records[0].decision_public_id


def test_summary_preserves_company_profile_and_portfolio_links() -> None:
    records = _records()
    result = EnterpriseDividendIncomeIntegration().summarize(records)
    assert result.record.company_id == records[0].company_id
    assert result.record.profile_id == records[0].profile_id
    assert result.record.portfolio_integration_id == records[0].portfolio_integration_id


def test_summary_deduplicates_evidence_links() -> None:
    records = _records()
    result = EnterpriseDividendIncomeIntegration().summarize(records)
    assert result.record.evidence_ids == records[0].evidence_ids


def test_summary_preserves_source_record_order() -> None:
    records = _records()
    result = EnterpriseDividendIncomeIntegration().summarize(records)
    assert result.record.source_dividend_record_ids == tuple(item.dividend_record_id for item in records)


def test_duplicate_lifecycle_state_is_rejected() -> None:
    integration = EnterpriseDividendIncomeIntegration()
    records = _records()
    integration.summarize(records)
    with pytest.raises(PlatformValidationError):
        integration.summarize(records)


def test_empty_records_are_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendIncomeIntegration().summarize(())


def test_mixed_portfolios_are_rejected() -> None:
    first, second = _records()
    second = replace(second, portfolio_integration_id=uuid4())
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendIncomeIntegration().summarize((first, second))


def test_mismatched_decisions_are_rejected() -> None:
    first, second = _records()
    second = replace(second, decision_internal_id=uuid4())
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendIncomeIntegration().summarize((first, second))


def test_unordered_records_are_rejected() -> None:
    records = _records()
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendIncomeIntegration().summarize(tuple(reversed(records)))


def test_naive_completed_at_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendIncomeIntegration().summarize(_records(), completed_at=datetime(2026, 7, 24))


def test_pending_income_is_calculated_for_unpaid_announcement() -> None:
    announced = _records()[0]
    result = EnterpriseDividendIncomeIntegration().summarize((announced,))
    assert result.record.pending_income == 50.0
    assert result.record.payment_count == 0


def test_history_and_ledger_are_immutable_tuple_snapshots() -> None:
    integration = EnterpriseDividendIncomeIntegration()
    integration.summarize(_records())
    assert isinstance(integration.history(), tuple)
    assert isinstance(integration.ledger.all(), tuple)
    assert len(integration.ledger.all()) == 1


def test_json_and_markdown_preserve_safety_boundaries() -> None:
    integration = EnterpriseDividendIncomeIntegration()
    result = integration.summarize(_records())
    json_output = integration.render_json(result)
    markdown = integration.render_markdown(result)
    assert '"cash_moved": false' in json_output
    assert "Received Income: $50.00" in markdown
    assert "does not move cash" in markdown


def test_service_has_no_cash_portfolio_or_broker_interfaces() -> None:
    integration = EnterpriseDividendIncomeIntegration(EnterpriseDividendIncomeLedger())
    assert not hasattr(integration, "move_cash")
    assert not hasattr(integration, "update_balance")
    assert not hasattr(integration, "open_position")
    assert not hasattr(integration, "place_order")
