from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from types import MappingProxyType
from uuid import uuid4

import pytest

from src.dividend_bot.enterprise_dividend_analytics_integration import EnterpriseDividendAnalyticsIntegration
from src.dividend_bot.enterprise_dividend_income_integration import EnterpriseDividendIncomeRecord
from src.dividend_bot.enterprise_income_forecast_integration import EnterpriseIncomeForecastRecord, IncomeForecastStatus
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now


def _records(*, received=800.0, pending=200.0, payments=3, forward=1000.0, confidence=90.0, status=IncomeForecastStatus.ACTIVE):
    portfolio_id = uuid4()
    decision_id = uuid4()
    company_id = uuid4()
    profile_id = uuid4()
    evidence = (uuid4(),)
    income = EnterpriseDividendIncomeRecord(
        income_record_id=uuid4(), sequence=1, portfolio_integration_id=portfolio_id,
        workflow_id="WF-DEC-2026-000001", correlation_id="WF-DEC-2026-000001",
        decision_internal_id=decision_id, decision_public_id="DEC-2026-000001",
        company_id=company_id, profile_id=profile_id, strategy_id="DIVIDEND",
        evidence_ids=evidence, source_dividend_record_ids=(uuid4(),),
        announced_income=received + pending, received_income=received, pending_income=pending,
        payment_count=payments, latest_amount_per_share=1.25, calculated_at=utc_now(),
        metadata=MappingProxyType({"append_only": True}),
    )
    projected_next = round(forward / 4, 8)
    forecast = EnterpriseIncomeForecastRecord(
        forecast_id=uuid4(), sequence=1, source_income_record_id=income.income_record_id,
        portfolio_integration_id=portfolio_id, workflow_id=income.workflow_id,
        correlation_id=income.correlation_id, decision_internal_id=decision_id,
        decision_public_id=income.decision_public_id, company_id=company_id, profile_id=profile_id,
        strategy_id="DIVIDEND", evidence_ids=evidence, status=status, share_count=200,
        payments_per_year=4, market_value=25000, projected_next_payment=0.0 if status is IncomeForecastStatus.SUSPENDED else projected_next,
        projected_annual_income=0.0 if status is IncomeForecastStatus.SUSPENDED else forward,
        projected_yield_percent=0.0 if status is IncomeForecastStatus.SUSPENDED else round((forward / 25000) * 100, 8),
        confidence=confidence, next_payment_date=None if status is IncomeForecastStatus.SUSPENDED else date(2026, 10, 15),
        forecasted_at=utc_now(), metadata=MappingProxyType({"predictive_only": True}),
    )
    return income, forecast


def _analyze(**kwargs):
    income, forecast = _records(**kwargs)
    service = EnterpriseDividendAnalyticsIntegration()
    return service, service.analyze((income,), (forecast,), expected_payments=4)


def test_analytics_calculates_core_metrics() -> None:
    _, result = _analyze()
    assert result.record.trailing_received_income == 800.0
    assert result.record.forward_annual_income == 1000.0
    assert result.record.income_growth_percent == 25.0
    assert result.record.forecast_variance == 200.0
    assert result.record.payment_consistency_percent == 75.0


def test_analytics_preserves_governed_identity_links() -> None:
    income, forecast = _records()
    result = EnterpriseDividendAnalyticsIntegration().analyze((income,), (forecast,), expected_payments=4)
    assert result.record.portfolio_integration_id == income.portfolio_integration_id
    assert result.record.decision_internal_id == income.decision_internal_id
    assert result.record.company_id == income.company_id
    assert result.record.profile_id == income.profile_id
    assert result.record.evidence_ids == income.evidence_ids


def test_zero_trailing_income_has_no_growth_rate() -> None:
    _, result = _analyze(received=0, pending=1000, payments=0)
    assert result.record.income_growth_percent is None
    assert "NO_RECEIVED_PAYMENTS" in result.record.review_flags


def test_negative_growth_creates_review_flag() -> None:
    _, result = _analyze(received=1200, pending=0, payments=4, forward=1000)
    assert result.record.income_growth_percent < 0
    assert "NEGATIVE_INCOME_GROWTH" in result.record.review_flags


def test_low_confidence_creates_review_flag() -> None:
    _, result = _analyze(confidence=60)
    assert "LOW_FORECAST_CONFIDENCE" in result.record.review_flags


def test_suspended_forecast_creates_review_flag() -> None:
    _, result = _analyze(status=IncomeForecastStatus.SUSPENDED, forward=0)
    assert "SUSPENDED" in result.record.review_flags


def test_pending_income_creates_review_flag() -> None:
    _, result = _analyze(pending=200)
    assert "PENDING_INCOME" in result.record.review_flags


def test_empty_inputs_are_rejected() -> None:
    service = EnterpriseDividendAnalyticsIntegration()
    income, forecast = _records()
    with pytest.raises(PlatformValidationError):
        service.analyze((), (forecast,), expected_payments=4)
    with pytest.raises(PlatformValidationError):
        service.analyze((income,), (), expected_payments=4)


def test_expected_payments_must_be_positive() -> None:
    income, forecast = _records()
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendAnalyticsIntegration().analyze((income,), (forecast,), expected_payments=0)


def test_mismatched_identity_is_rejected() -> None:
    income, forecast = _records()
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendAnalyticsIntegration().analyze((income,), (replace(forecast, company_id=uuid4()),), expected_payments=4)


def test_duplicate_source_state_is_rejected() -> None:
    income, forecast = _records()
    service = EnterpriseDividendAnalyticsIntegration()
    service.analyze((income,), (forecast,), expected_payments=4)
    with pytest.raises(PlatformValidationError):
        service.analyze((income,), (forecast,), expected_payments=4)


def test_records_must_be_unique_and_ordered() -> None:
    income, forecast = _records()
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendAnalyticsIntegration().analyze((income, income), (forecast,), expected_payments=4)
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendAnalyticsIntegration().analyze((income,), (forecast, forecast), expected_payments=4)


def test_record_math_is_validated() -> None:
    _, result = _analyze()
    with pytest.raises(PlatformValidationError):
        replace(result.record, forecast_variance=999).validate()
    with pytest.raises(PlatformValidationError):
        replace(result.record, payment_consistency_percent=101).validate()


def test_naive_completed_at_is_rejected() -> None:
    income, forecast = _records()
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendAnalyticsIntegration().analyze((income,), (forecast,), expected_payments=4, completed_at=datetime(2026, 7, 24))


def test_history_and_ledger_are_immutable_tuple_snapshots() -> None:
    service, _ = _analyze()
    assert isinstance(service.history(), tuple)
    assert isinstance(service.ledger.all(), tuple)
    assert len(service.history()) == 1


def test_json_markdown_and_safety_boundary() -> None:
    service, result = _analyze()
    json_output = service.render_json(result)
    markdown = service.render_markdown(result)
    assert '"analytical_only": true' in json_output
    assert "Forward Annual Income: $1,000.00" in markdown
    assert "does not move cash, alter balances, mutate holdings, call brokers, or place orders" in markdown
    assert not hasattr(service, "move_cash")
    assert not hasattr(service, "open_position")
    assert not hasattr(service, "place_order")
