from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from types import MappingProxyType
from uuid import uuid4

import pytest

from src.dividend_bot.enterprise_dividend_dashboard_integration import EnterpriseDividendDashboardIntegration
from src.dividend_bot.enterprise_dividend_reporting_integration import DividendReportScope, EnterpriseDividendReportRecord
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now


def _report(*, sequence=1, scope=DividendReportScope.WEEKLY, portfolio_id=None, company_id=None, profile_id=None, flags=(), forward=1200.0):
    return EnterpriseDividendReportRecord(
        report_id=uuid4(), sequence=sequence, scope=scope, period_start=date(2026, 7, 1), period_end=date(2026, 7, 7),
        portfolio_integration_id=portfolio_id or uuid4(), workflow_id="WF-DEC-2026-000001", correlation_id="WF-DEC-2026-000001",
        decision_internal_id=uuid4(), decision_public_id="DEC-2026-000001", company_id=company_id or uuid4(), profile_id=profile_id or uuid4(),
        strategy_id="DIVIDEND", evidence_ids=(uuid4(),), source_analytics_ids=(uuid4(),), trailing_received_income=300.0,
        forward_annual_income=forward, projected_yield_percent=4.0, payment_consistency_percent=75.0,
        latest_forecast_confidence=90.0, review_flags=tuple(flags), report_status="REVIEW_REQUIRED" if flags else "CLEAR",
        generated_at=utc_now(), metadata=MappingProxyType({"reporting_only": True}),
    )


def _same(report, **changes):
    values = dict(
        portfolio_integration_id=report.portfolio_integration_id, workflow_id=report.workflow_id, correlation_id=report.correlation_id,
        decision_internal_id=report.decision_internal_id, decision_public_id=report.decision_public_id, company_id=report.company_id,
        profile_id=report.profile_id, strategy_id=report.strategy_id,
    )
    values.update(changes)
    return replace(report, report_id=uuid4(), **values)


def test_dashboard_preserves_latest_metrics() -> None:
    result = EnterpriseDividendDashboardIntegration().build_dashboard((_report(),))
    assert result.record.forward_annual_income == 1200.0
    assert result.record.projected_monthly_income == 100.0


def test_dashboard_preserves_identity_links() -> None:
    report = _report()
    result = EnterpriseDividendDashboardIntegration().build_dashboard((report,))
    assert result.record.portfolio_integration_id == report.portfolio_integration_id
    assert result.record.decision_internal_id == report.decision_internal_id
    assert result.record.company_id == report.company_id


def test_dashboard_collects_report_scopes() -> None:
    first = _report()
    second = _same(first, sequence=2, scope=DividendReportScope.MONTHLY)
    result = EnterpriseDividendDashboardIntegration().build_dashboard((first, second))
    assert result.record.report_scopes == ("WEEKLY", "MONTHLY")


def test_review_flags_set_review_status() -> None:
    result = EnterpriseDividendDashboardIntegration().build_dashboard((_report(flags=("PENDING_INCOME",)),))
    assert result.record.dashboard_status == "REVIEW_REQUIRED"


def test_clear_dashboard_has_no_flags() -> None:
    result = EnterpriseDividendDashboardIntegration().build_dashboard((_report(),))
    assert result.record.dashboard_status == "CLEAR"


def test_empty_reports_are_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendDashboardIntegration().build_dashboard(())


def test_mixed_identity_is_rejected() -> None:
    first = _report()
    second = _same(first, sequence=2, company_id=uuid4())
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendDashboardIntegration().build_dashboard((first, second))


def test_unordered_reports_are_rejected() -> None:
    first = _report(sequence=1)
    second = _same(first, sequence=2)
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendDashboardIntegration().build_dashboard((second, first))


def test_duplicate_report_state_is_rejected() -> None:
    service = EnterpriseDividendDashboardIntegration()
    report = _report()
    service.build_dashboard((report,))
    with pytest.raises(PlatformValidationError):
        service.build_dashboard((report,))


def test_append_only_sequence_is_enforced() -> None:
    service = EnterpriseDividendDashboardIntegration()
    result = service.build_dashboard((_report(),))
    with pytest.raises(PlatformValidationError):
        service.ledger.append(replace(result.record, dashboard_id=uuid4(), source_report_ids=(uuid4(),), sequence=3))


def test_monthly_projection_is_validated() -> None:
    result = EnterpriseDividendDashboardIntegration().build_dashboard((_report(),))
    with pytest.raises(PlatformValidationError):
        replace(result.record, projected_monthly_income=999.0).validate()


def test_status_must_match_flags() -> None:
    result = EnterpriseDividendDashboardIntegration().build_dashboard((_report(),))
    with pytest.raises(PlatformValidationError):
        replace(result.record, dashboard_status="REVIEW_REQUIRED").validate()


def test_naive_completed_at_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        EnterpriseDividendDashboardIntegration().build_dashboard((_report(),), completed_at=datetime(2026, 7, 24))


def test_history_and_ledger_are_tuple_snapshots() -> None:
    service = EnterpriseDividendDashboardIntegration()
    service.build_dashboard((_report(),))
    assert isinstance(service.history(), tuple)
    assert isinstance(service.ledger.all(), tuple)


def test_json_and_markdown_preserve_safety_boundary() -> None:
    service = EnterpriseDividendDashboardIntegration()
    result = service.build_dashboard((_report(),))
    assert '"presentation_only": true' in service.render_json(result)
    assert "Projected Monthly Income: $100.00" in service.render_markdown(result)
    assert "does not approve investments, move cash" in service.render_markdown(result)


def test_service_has_no_execution_interfaces() -> None:
    service = EnterpriseDividendDashboardIntegration()
    assert not hasattr(service, "approve_investment")
    assert not hasattr(service, "move_cash")
    assert not hasattr(service, "open_position")
    assert not hasattr(service, "place_order")
