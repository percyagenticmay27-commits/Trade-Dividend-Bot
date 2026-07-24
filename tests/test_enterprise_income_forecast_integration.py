from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from types import MappingProxyType
from uuid import uuid4

import pytest

from src.dividend_bot.enterprise_dividend_income_integration import EnterpriseDividendIncomeRecord
from src.dividend_bot.enterprise_income_forecast_integration import (
    EnterpriseIncomeForecastIntegration,
    EnterpriseIncomeForecastLedger,
    EnterpriseIncomeForecastRecord,
    IncomeForecastStatus,
)
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now


def _income(*, source_id=None, portfolio_id=None, latest_amount=1.35) -> EnterpriseDividendIncomeRecord:
    return EnterpriseDividendIncomeRecord(
        income_record_id=source_id or uuid4(),
        sequence=1,
        portfolio_integration_id=portfolio_id or uuid4(),
        workflow_id="WF-DEC-2026-000001",
        correlation_id="WF-DEC-2026-000001",
        decision_internal_id=uuid4(),
        decision_public_id="DEC-2026-000001",
        company_id=uuid4(),
        profile_id=uuid4(),
        strategy_id="DIVIDEND",
        evidence_ids=(uuid4(),),
        source_dividend_record_ids=(uuid4(),),
        announced_income=270.0,
        received_income=0.0,
        pending_income=270.0,
        payment_count=0,
        latest_amount_per_share=latest_amount,
        calculated_at=utc_now(),
        metadata=MappingProxyType({"append_only": True}),
    )


def _forecast(integration=None, income=None, **overrides):
    service = integration or EnterpriseIncomeForecastIntegration()
    values = {
        "share_count": 200,
        "payments_per_year": 4,
        "market_value": 30000,
        "next_payment_date": date(2026, 10, 15),
        "confidence": 96,
    }
    values.update(overrides)
    return service, service.forecast(income or _income(), **values)


def test_forecast_calculates_payment_annual_income_and_yield() -> None:
    _, result = _forecast()
    assert result.record.projected_next_payment == 270.0
    assert result.record.projected_annual_income == 1080.0
    assert result.record.projected_yield_percent == 3.6


def test_forecast_preserves_governed_identity_links() -> None:
    income = _income()
    _, result = _forecast(income=income)
    record = result.record
    assert record.source_income_record_id == income.income_record_id
    assert record.portfolio_integration_id == income.portfolio_integration_id
    assert record.workflow_id == income.workflow_id
    assert record.decision_internal_id == income.decision_internal_id
    assert record.company_id == income.company_id
    assert record.evidence_ids == income.evidence_ids


def test_first_forecast_is_active() -> None:
    _, result = _forecast()
    assert result.record.status is IncomeForecastStatus.ACTIVE
    assert result.record.supersedes_forecast_id is None


def test_successive_active_forecast_becomes_updated_and_links_prior() -> None:
    service = EnterpriseIncomeForecastIntegration()
    portfolio_id = uuid4()
    _, first = _forecast(service, _income(portfolio_id=portfolio_id))
    _, second = _forecast(service, _income(portfolio_id=portfolio_id, latest_amount=1.40))
    assert second.record.status is IncomeForecastStatus.UPDATED
    assert second.record.supersedes_forecast_id == first.record.forecast_id


def test_suspended_forecast_has_zero_income_and_no_payment_date() -> None:
    _, result = _forecast(status=IncomeForecastStatus.SUSPENDED, next_payment_date=None)
    assert result.record.projected_next_payment == 0
    assert result.record.projected_annual_income == 0
    assert result.record.projected_yield_percent == 0
    assert result.record.next_payment_date is None


def test_non_suspended_forecast_requires_payment_date() -> None:
    with pytest.raises(PlatformValidationError):
        _forecast(next_payment_date=None)


def test_confidence_must_be_in_range() -> None:
    with pytest.raises(PlatformValidationError):
        _forecast(confidence=101)


def test_positive_position_inputs_are_required() -> None:
    with pytest.raises(PlatformValidationError):
        _forecast(share_count=0)
    with pytest.raises(PlatformValidationError):
        _forecast(payments_per_year=0)
    with pytest.raises(PlatformValidationError):
        _forecast(market_value=0)


def test_duplicate_income_summary_is_rejected() -> None:
    service = EnterpriseIncomeForecastIntegration()
    income = _income()
    _forecast(service, income)
    with pytest.raises(PlatformValidationError):
        _forecast(service, income)


def test_ledger_requires_append_only_sequence() -> None:
    service, result = _forecast()
    record = replace(result.record, forecast_id=uuid4(), source_income_record_id=uuid4(), sequence=3)
    with pytest.raises(PlatformValidationError):
        service.ledger.append(record)


def test_updated_status_requires_prior_link() -> None:
    _, result = _forecast()
    with pytest.raises(PlatformValidationError):
        replace(result.record, status=IncomeForecastStatus.UPDATED, supersedes_forecast_id=None).validate()


def test_forecast_math_is_validated() -> None:
    _, result = _forecast()
    with pytest.raises(PlatformValidationError):
        replace(result.record, projected_annual_income=999).validate()
    with pytest.raises(PlatformValidationError):
        replace(result.record, projected_yield_percent=99).validate()


def test_naive_completed_at_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        _forecast(completed_at=datetime(2026, 7, 24))


def test_history_and_ledger_are_immutable_tuple_snapshots() -> None:
    service, _ = _forecast()
    assert isinstance(service.history(), tuple)
    assert isinstance(service.ledger.all(), tuple)
    assert len(service.history()) == 1


def test_json_and_markdown_preserve_predictive_safety_boundary() -> None:
    service, result = _forecast()
    json_output = service.render_json(result)
    markdown = service.render_markdown(result)
    assert '"predictive_only": true' in json_output
    assert "Projected Annual Income: $1,080.00" in markdown
    assert "does not move cash, alter balances, mutate holdings, call brokers, or place orders" in markdown


def test_service_has_no_cash_portfolio_or_execution_interfaces() -> None:
    service = EnterpriseIncomeForecastIntegration()
    assert not hasattr(service, "move_cash")
    assert not hasattr(service, "open_position")
    assert not hasattr(service, "place_order")
