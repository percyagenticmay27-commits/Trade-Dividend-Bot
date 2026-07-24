from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest

from src.dividend_bot.dividend_enterprise_execution import (
    DividendPaperDisposition,
    DividendPaperExecutionRecord,
)
from src.dividend_bot.dividend_execution_reporting import DividendExecutionReportingService
from src.dividend_bot.dividend_strategy_adapter import DividendStrategyAdapter
from src.dividend_bot.enterprise_strategy_execution import (
    StrategyExecutionRequest,
    StrategyExecutionResponse,
    StrategyResponseStatus,
)
from src.dividend_bot.platform_entities import MasterCompanyIntelligenceProfile, new_identity
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now


def _record(*, disposition=DividendPaperDisposition.PAPER_BUY_REVIEW, status=StrategyResponseStatus.ACCEPTED, strategy_id="DIVIDEND", score_profile=80.0):
    now = utc_now()
    profile = MasterCompanyIntelligenceProfile(
        identity=new_identity("MCIP"),
        company_id=new_identity("COM").internal_id,
        income={"score": score_profile},
        risk={"score": 20.0},
        quality_score=80.0,
    )
    evaluation = DividendStrategyAdapter().evaluate(profile)
    request = StrategyExecutionRequest(
        request_id=uuid4(),
        decision_id=uuid4(),
        decision_public_id="DEC-2026-000001",
        strategy_id=strategy_id,
        effective_action="BUY",
        requested_capital=500.0,
        available_strategy_capital=5000.0,
        rationale="Governed paper request",
        routed_at=now,
    )
    response = StrategyExecutionResponse(
        response_id=uuid4(),
        request_id=request.request_id,
        strategy_id=strategy_id,
        status=status,
        explanation="Paper response",
        responded_at=now,
    )
    return DividendPaperExecutionRecord(
        record_id=uuid4(),
        request=request,
        evaluation_result=evaluation,
        response=response,
        disposition=disposition,
        processed_at=now,
    )


def _build(records=None, report_type="WEEKLY"):
    now = utc_now()
    return DividendExecutionReportingService().build(
        records or (_record(),),
        report_type=report_type,
        period_start=now - timedelta(days=7),
        period_end=now,
        completed_at=now,
    )


def test_weekly_report_is_dividend_isolated() -> None:
    bundle = _build()
    assert bundle.report.strategy_id == "DIVIDEND"
    assert bundle.report.report_type == "WEEKLY"
    assert bundle.audit.strategy_id == "DIVIDEND"


def test_monthly_report_uses_monthly_audit() -> None:
    bundle = _build(report_type="MONTHLY")
    assert bundle.audit.audit_type == "MONTHLY_AUDIT"


def test_performance_report_uses_release_audit() -> None:
    assert _build(report_type="PERFORMANCE").audit.audit_type == "RELEASE_AUDIT"


def test_learning_report_uses_release_audit() -> None:
    assert _build(report_type="LEARNING").audit.audit_type == "RELEASE_AUDIT"


def test_metrics_count_accepted_and_deferred() -> None:
    bundle = _build((_record(), _record(disposition=DividendPaperDisposition.DEFERRED, status=StrategyResponseStatus.DEFERRED)))
    assert bundle.record_count == 2
    assert bundle.accepted_count == 1
    assert bundle.deferred_count == 1


def test_disposition_counts_are_preserved() -> None:
    bundle = _build((_record(), _record(disposition=DividendPaperDisposition.EXIT_REVIEW)))
    assert bundle.paper_buy_review_count == 1
    assert bundle.exit_review_count == 1


def test_deferred_requests_create_warning() -> None:
    bundle = _build((_record(disposition=DividendPaperDisposition.DEFERRED, status=StrategyResponseStatus.DEFERRED),))
    assert bundle.report.warnings


def test_decision_ids_are_deduplicated() -> None:
    bundle = _build((_record(), _record()))
    assert bundle.report.decision_ids == ("DEC-2026-000001",)


def test_empty_records_are_rejected() -> None:
    now = utc_now()
    with pytest.raises(PlatformValidationError):
        DividendExecutionReportingService().build((), report_type="WEEKLY", period_start=now, period_end=now, completed_at=now)


def test_cross_strategy_record_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        _build((_record(strategy_id="SWING"),))


def test_unsupported_report_type_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        _build(report_type="DAILY")


def test_naive_timestamp_is_rejected() -> None:
    now = utc_now()
    with pytest.raises(PlatformValidationError):
        DividendExecutionReportingService().build((_record(),), report_type="WEEKLY", period_start=now.replace(tzinfo=None), period_end=now, completed_at=now)


def test_json_and_markdown_preserve_paper_boundary() -> None:
    service = DividendExecutionReportingService()
    bundle = _build()
    assert '"paper_trade_mode": true' in service.render_json(bundle)
    assert "Strategy: DIVIDEND" in service.render_report_markdown(bundle)
    assert "broker_execution" in service.render_audit_markdown(bundle)


def test_bundle_validation_rejects_inconsistent_counts() -> None:
    bundle = _build()
    with pytest.raises(PlatformValidationError):
        replace(bundle, accepted_count=0).validate()


def test_service_has_no_broker_or_order_interface() -> None:
    service = DividendExecutionReportingService()
    assert not hasattr(service, "place_order")
    assert not hasattr(service, "broker_request")
    assert not hasattr(service, "allocate_capital")
