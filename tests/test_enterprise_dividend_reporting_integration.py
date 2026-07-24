from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from types import MappingProxyType
from uuid import uuid4

import pytest

from src.dividend_bot.enterprise_dividend_analytics_integration import EnterpriseDividendAnalyticsRecord
from src.dividend_bot.enterprise_dividend_reporting_integration import (
    DividendReportScope,
    EnterpriseDividendReportingIntegration,
)
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now


def _analytics(*, sequence=1, portfolio_id=None, company_id=None, profile_id=None, flags=()) -> EnterpriseDividendAnalyticsRecord:
    return EnterpriseDividendAnalyticsRecord(
        analytics_id=uuid4(), sequence=sequence,
        portfolio_integration_id=portfolio_id or uuid4(), workflow_id="WF-DEC-2026-000001",
        correlation_id="WF-DEC-2026-000001", decision_internal_id=uuid4(),
        decision_public_id="DEC-2026-000001", company_id=company_id or uuid4(),
        profile_id=profile_id or uuid4(), strategy_id="DIVIDEND", evidence_ids=(uuid4(),),
        source_income_record_ids=(uuid4(),), source_forecast_ids=(uuid4(),),
        trailing_received_income=270.0, forward_annual_income=1080.0,
        income_growth_percent=300.0, projected_yield_percent=3.6,
        forecast_variance=810.0, payment_consistency_percent=75.0,
        latest_forecast_confidence=96.0, review_flags=tuple(flags), calculated_at=utc_now(),
        metadata=MappingProxyType({"append_only": True}),
    )


def _report(records=None, **overrides):
    service = EnterpriseDividendReportingIntegration()
    values = {
        "scope": DividendReportScope.WEEKLY,
        "period_start": date(2026, 7, 20),
        "period_end": date(2026, 7, 26),
    }
    values.update(overrides)
    return service, service.build_report(records or (_analytics(),), **values)


def test_weekly_report_preserves_metrics() -> None:
    _, result = _report()
    assert result.record.trailing_received_income == 270.0
    assert result.record.forward_annual_income == 1080.0
    assert result.record.projected_yield_percent == 3.6


def test_report_preserves_governed_identity_links() -> None:
    analytics = _analytics()
    _, result = _report((analytics,))
    record = result.record
    assert record.portfolio_integration_id == analytics.portfolio_integration_id
    assert record.decision_internal_id == analytics.decision_internal_id
    assert record.company_id == analytics.company_id
    assert record.source_analytics_ids == (analytics.analytics_id,)


def test_monthly_scope_is_supported() -> None:
    _, result = _report(scope=DividendReportScope.MONTHLY, period_start=date(2026, 7, 1), period_end=date(2026, 7, 31))
    assert result.record.scope is DividendReportScope.MONTHLY


def test_investor_scope_is_marked_in_metadata() -> None:
    _, result = _report(scope=DividendReportScope.INVESTOR)
    assert result.record.metadata["investor_facing"] is True


def test_review_flags_set_review_required_status() -> None:
    _, result = _report((_analytics(flags=("PENDING_INCOME",)),))
    assert result.record.report_status == "REVIEW_REQUIRED"


def test_clear_report_has_clear_status() -> None:
    _, result = _report()
    assert result.record.report_status == "CLEAR"


def test_empty_analytics_is_rejected() -> None:
    service = EnterpriseDividendReportingIntegration()
    with pytest.raises(PlatformValidationError):
        service.build_report((), scope=DividendReportScope.WEEKLY, period_start=date(2026, 7, 20), period_end=date(2026, 7, 26))


def test_invalid_period_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        _report(period_start=date(2026, 7, 27), period_end=date(2026, 7, 26))


def test_mixed_identity_records_are_rejected() -> None:
    first = _analytics(sequence=1)
    second = replace(_analytics(sequence=2), workflow_id=first.workflow_id, correlation_id=first.correlation_id,
                     decision_internal_id=first.decision_internal_id, decision_public_id=first.decision_public_id,
                     portfolio_integration_id=first.portfolio_integration_id, profile_id=first.profile_id,
                     company_id=uuid4())
    with pytest.raises(PlatformValidationError):
        _report((first, second))


def test_unordered_records_are_rejected() -> None:
    first = _analytics(sequence=1)
    second = replace(first, analytics_id=uuid4(), sequence=2, source_income_record_ids=(uuid4(),), source_forecast_ids=(uuid4(),))
    with pytest.raises(PlatformValidationError):
        _report((second, first))


def test_duplicate_source_state_is_rejected() -> None:
    service = EnterpriseDividendReportingIntegration()
    analytics = _analytics()
    kwargs = dict(scope=DividendReportScope.WEEKLY, period_start=date(2026, 7, 20), period_end=date(2026, 7, 26))
    service.build_report((analytics,), **kwargs)
    with pytest.raises(PlatformValidationError):
        service.build_report((analytics,), **kwargs)


def test_same_sources_can_be_reported_for_different_scope() -> None:
    service = EnterpriseDividendReportingIntegration()
    analytics = _analytics()
    service.build_report((analytics,), scope=DividendReportScope.WEEKLY, period_start=date(2026, 7, 20), period_end=date(2026, 7, 26))
    result = service.build_report((analytics,), scope=DividendReportScope.INVESTOR, period_start=date(2026, 7, 20), period_end=date(2026, 7, 26))
    assert result.record.sequence == 2


def test_naive_completed_at_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        _report(completed_at=datetime(2026, 7, 24))


def test_history_and_ledger_are_immutable_tuple_snapshots() -> None:
    service, _ = _report()
    assert isinstance(service.history(), tuple)
    assert isinstance(service.ledger.all(), tuple)


def test_json_and_markdown_preserve_safety_boundary() -> None:
    service, result = _report()
    json_output = service.render_json(result)
    markdown = service.render_markdown(result)
    assert '"reporting_only": true' in json_output
    assert "Forward Annual Income: $1,080.00" in markdown
    assert "does not approve investments, move cash" in markdown


def test_service_has_no_cash_portfolio_or_execution_interfaces() -> None:
    service = EnterpriseDividendReportingIntegration()
    assert not hasattr(service, "move_cash")
    assert not hasattr(service, "open_position")
    assert not hasattr(service, "place_order")
