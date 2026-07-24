from __future__ import annotations

from datetime import datetime, time, timezone
from uuid import uuid4

import pytest

from src.dividend_bot.enterprise_ai_cio_runtime import EnterpriseRecommendation
from src.dividend_bot.enterprise_daily_cycle import (
    DailyCyclePolicy,
    DailyCycleStatus,
    EnterpriseDailyCycle,
)
from src.dividend_bot.enterprise_decision_engine import EnterpriseDecisionAction, StrategyAdvisory
from src.dividend_bot.enterprise_intelligence_service import IntelligenceContribution
from src.dividend_bot.enterprise_workflow_orchestrator import EnterpriseWorkflowRequest
from src.dividend_bot.platform_entities import MasterCompanyIntelligenceProfile, new_identity
from src.dividend_bot.platform_foundation import PlatformValidationError
from src.dividend_bot.platform_integration import ServiceDomain


def _request() -> EnterpriseWorkflowRequest:
    profile = MasterCompanyIntelligenceProfile(
        identity=new_identity("MCI"),
        company_id=uuid4(),
        quality_score=80.0,
    )
    contributions = (
        IntelligenceContribution("FUNDAMENTAL-SERVICE", ServiceDomain.FUNDAMENTALS, {"score": 80}),
        IntelligenceContribution("INCOME-SERVICE", ServiceDomain.INCOME, {"score": 85}),
        IntelligenceContribution("HEALTH-SERVICE", ServiceDomain.FINANCIAL_HEALTH, {"score": 75}),
        IntelligenceContribution("RISK-SERVICE", ServiceDomain.RISK, {"score": 20}),
        IntelligenceContribution("MARKET-SERVICE", ServiceDomain.MARKET_INTELLIGENCE, {"score": 70}),
        IntelligenceContribution("TECHNICAL-SERVICE", ServiceDomain.TECHNICAL, {"score": 65}),
        IntelligenceContribution("EARNINGS-SERVICE", ServiceDomain.EARNINGS, {"score": 70}),
    )
    advisory = StrategyAdvisory(
        strategy_id="DIVIDEND",
        action=EnterpriseDecisionAction.BUY,
        confidence=80,
        opportunity_quality=80,
        rationale="Dividend advisory",
        service_id="DIVIDEND-ADAPTER",
    )
    return EnterpriseWorkflowRequest(
        profile=profile,
        contributions=contributions,
        strategy_advisories=(advisory,),
        proposed_recommendation=EnterpriseRecommendation.BUY,
        confidence=80,
        stability_checked=True,
        rationale="Enterprise rationale",
        evidence_count=3,
    )


def _at(hour: int, minute: int = 0, day: int = 24) -> datetime:
    return datetime(2026, 7, day, hour, minute, tzinfo=timezone.utc)


def test_default_policy_is_paper_daily_at_1530() -> None:
    cycle = EnterpriseDailyCycle()
    assert cycle.policy.scheduled_time == time(15, 30)
    assert cycle.policy.allowed_weekdays == (0, 1, 2, 3, 4, 5, 6)


def test_before_schedule_is_not_due() -> None:
    plan = EnterpriseDailyCycle().plan(evaluated_at=_at(15, 29))
    assert plan.status is DailyCycleStatus.NOT_DUE


def test_at_schedule_is_ready() -> None:
    plan = EnterpriseDailyCycle().plan(evaluated_at=_at(15, 30))
    assert plan.status is DailyCycleStatus.READY


def test_disabled_weekday_is_not_due() -> None:
    policy = DailyCyclePolicy(allowed_weekdays=(0,))
    plan = EnterpriseDailyCycle(policy=policy).plan(evaluated_at=_at(16))
    assert plan.status is DailyCycleStatus.NOT_DUE


def test_run_when_ready_completes_orchestrator() -> None:
    result = EnterpriseDailyCycle().run(_request(), evaluated_at=_at(16))
    assert result.status is DailyCycleStatus.COMPLETED
    assert result.workflow_result is not None


def test_run_before_schedule_does_not_invoke_workflow() -> None:
    result = EnterpriseDailyCycle().run(_request(), evaluated_at=_at(12))
    assert result.status is DailyCycleStatus.NOT_DUE
    assert result.workflow_result is None


def test_force_runs_before_schedule() -> None:
    result = EnterpriseDailyCycle().run(_request(), evaluated_at=_at(12), force=True)
    assert result.status is DailyCycleStatus.COMPLETED
    assert result.workflow_result is not None


def test_one_run_per_date_skips_duplicate() -> None:
    cycle = EnterpriseDailyCycle()
    cycle.run(_request(), evaluated_at=_at(16))
    second = cycle.run(_request(), evaluated_at=_at(17))
    assert second.status is DailyCycleStatus.SKIPPED
    assert second.workflow_result is None


def test_force_does_not_bypass_completed_date() -> None:
    cycle = EnterpriseDailyCycle()
    cycle.run(_request(), evaluated_at=_at(16))
    second = cycle.run(_request(), evaluated_at=_at(17), force=True)
    assert second.status is DailyCycleStatus.SKIPPED


def test_next_date_can_run() -> None:
    cycle = EnterpriseDailyCycle()
    first = cycle.run(_request(), evaluated_at=_at(16, day=24))
    second = cycle.run(_request(), evaluated_at=_at(16, day=25))
    assert first.status is DailyCycleStatus.COMPLETED
    assert second.status is DailyCycleStatus.COMPLETED


def test_history_is_append_only_tuple_snapshot() -> None:
    cycle = EnterpriseDailyCycle()
    cycle.run(_request(), evaluated_at=_at(12))
    assert isinstance(cycle.history(), tuple)
    assert len(cycle.history()) == 1


def test_naive_evaluation_timestamp_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        EnterpriseDailyCycle().plan(evaluated_at=datetime(2026, 7, 24, 16, 0))


def test_policy_rejects_invalid_weekdays() -> None:
    with pytest.raises(PlatformValidationError):
        DailyCyclePolicy(allowed_weekdays=(7,)).validate()


def test_json_and_markdown_preserve_boundaries() -> None:
    cycle = EnterpriseDailyCycle()
    result = cycle.run(_request(), evaluated_at=_at(16))
    json_output = cycle.render_json(result)
    markdown = cycle.render_markdown(result)
    assert '"broker_execution_enabled": false' in json_output
    assert "stops at investor review" in markdown
    assert "does not assign capital" in markdown


def test_cycle_has_no_scheduler_broker_or_order_interfaces() -> None:
    cycle = EnterpriseDailyCycle()
    assert not hasattr(cycle, "install_cron")
    assert not hasattr(cycle, "create_os_schedule")
    assert not hasattr(cycle, "place_order")
    assert not hasattr(cycle, "broker_request")
