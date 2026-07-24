"""Controlled paper-only daily cycle for the enterprise investment platform.

This module determines whether a cycle is due and, when explicitly invoked, delegates to the
Enterprise Workflow Orchestrator. It does not create OS schedules, background jobs, capital
assignments, portfolio mutations, broker requests, or live orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from .enterprise_workflow_orchestrator import (
    EnterpriseWorkflowOrchestrator,
    EnterpriseWorkflowRequest,
    EnterpriseWorkflowResult,
)
from .platform_foundation import JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_daily_cycle"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Plan and explicitly run one paper-only enterprise daily workflow cycle."


class DailyCycleStatus(str, Enum):
    NOT_DUE = "NOT_DUE"
    READY = "READY"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class DailyCyclePolicy:
    scheduled_time: time = time(15, 30)
    allowed_weekdays: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6)
    timezone_name: str = "USER_LOCAL"
    one_run_per_date: bool = True

    def validate(self) -> None:
        if self.scheduled_time.tzinfo is not None:
            raise PlatformValidationError("scheduled_time must be a naive local wall-clock time")
        if not self.allowed_weekdays:
            raise PlatformValidationError("allowed_weekdays must not be empty")
        if len(set(self.allowed_weekdays)) != len(self.allowed_weekdays):
            raise PlatformValidationError("allowed_weekdays must not contain duplicates")
        if any(day < 0 or day > 6 for day in self.allowed_weekdays):
            raise PlatformValidationError("allowed_weekdays values must be between 0 and 6")
        if not self.timezone_name.strip():
            raise PlatformValidationError("timezone_name is required")


@dataclass(frozen=True)
class DailyCyclePlan:
    cycle_date: date
    evaluated_at: datetime
    scheduled_time: time
    status: DailyCycleStatus
    reason: str
    timezone_name: str
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if self.evaluated_at.tzinfo is None:
            raise PlatformValidationError("evaluated_at must be timezone-aware")
        if not self.reason.strip() or not self.timezone_name.strip():
            raise PlatformValidationError("cycle plan reason and timezone_name are required")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


@dataclass(frozen=True)
class DailyCycleRun:
    plan: DailyCyclePlan
    workflow_result: EnterpriseWorkflowResult | None
    completed_at: datetime
    status: DailyCycleStatus
    metadata: Mapping[str, object] = field(default_factory=dict)
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        self.plan.validate()
        if self.completed_at.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        if self.status is DailyCycleStatus.COMPLETED:
            if self.workflow_result is None:
                raise PlatformValidationError("completed cycles require a workflow result")
            self.workflow_result.validate()
        elif self.workflow_result is not None:
            raise PlatformValidationError("non-completed cycles must not contain a workflow result")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterpriseDailyCycle:
    """Plan and explicitly execute one daily workflow without creating an OS scheduler."""

    def __init__(
        self,
        orchestrator: EnterpriseWorkflowOrchestrator | None = None,
        policy: DailyCyclePolicy | None = None,
    ) -> None:
        self._orchestrator = orchestrator or EnterpriseWorkflowOrchestrator()
        self._policy = policy or DailyCyclePolicy()
        self._policy.validate()
        self._runs: list[DailyCycleRun] = []
        self._completed_dates: set[date] = set()

    @property
    def policy(self) -> DailyCyclePolicy:
        return self._policy

    def history(self) -> tuple[DailyCycleRun, ...]:
        return tuple(self._runs)

    def plan(self, *, evaluated_at: datetime | None = None) -> DailyCyclePlan:
        now = evaluated_at or utc_now()
        if now.tzinfo is None:
            raise PlatformValidationError("evaluated_at must be timezone-aware")
        cycle_date = now.date()
        if now.weekday() not in self._policy.allowed_weekdays:
            status = DailyCycleStatus.NOT_DUE
            reason = "The configured weekday is not enabled for the enterprise daily cycle."
        elif self._policy.one_run_per_date and cycle_date in self._completed_dates:
            status = DailyCycleStatus.SKIPPED
            reason = "The enterprise daily cycle has already completed for this date."
        elif now.timetz().replace(tzinfo=None) < self._policy.scheduled_time:
            status = DailyCycleStatus.NOT_DUE
            reason = "The configured enterprise daily cycle time has not been reached."
        else:
            status = DailyCycleStatus.READY
            reason = "The enterprise daily cycle is ready for explicit paper-only execution."
        plan = DailyCyclePlan(
            cycle_date=cycle_date,
            evaluated_at=now,
            scheduled_time=self._policy.scheduled_time,
            status=status,
            reason=reason,
            timezone_name=self._policy.timezone_name,
        )
        plan.validate()
        return plan

    def run(
        self,
        request: EnterpriseWorkflowRequest,
        *,
        evaluated_at: datetime | None = None,
        force: bool = False,
    ) -> DailyCycleRun:
        request.validate()
        plan = self.plan(evaluated_at=evaluated_at)
        timestamp = evaluated_at or utc_now()
        if force and plan.status is not DailyCycleStatus.SKIPPED:
            plan = DailyCyclePlan(
                cycle_date=plan.cycle_date,
                evaluated_at=plan.evaluated_at,
                scheduled_time=plan.scheduled_time,
                status=DailyCycleStatus.READY,
                reason="The enterprise daily cycle was explicitly forced for paper-only validation.",
                timezone_name=plan.timezone_name,
            )
        if plan.status is not DailyCycleStatus.READY:
            run = DailyCycleRun(
                plan=plan,
                workflow_result=None,
                completed_at=timestamp,
                status=plan.status,
                metadata=MappingProxyType({"module_version": MODULE_VERSION, "forced": force}),
            )
            run.validate()
            self._runs.append(run)
            return run

        workflow = self._orchestrator.prepare_for_investor_review(request, completed_at=timestamp)
        run = DailyCycleRun(
            plan=plan,
            workflow_result=workflow,
            completed_at=timestamp,
            status=DailyCycleStatus.COMPLETED,
            metadata=MappingProxyType(
                {
                    "module_version": MODULE_VERSION,
                    "forced": force,
                    "investor_review_required": True,
                }
            ),
        )
        run.validate()
        self._runs.append(run)
        self._completed_dates.add(plan.cycle_date)
        return run

    @staticmethod
    def render_json(run: DailyCycleRun) -> str:
        run.validate()
        payload = {
            "plan": run.plan,
            "workflow_result": run.workflow_result,
            "completed_at": run.completed_at,
            "status": run.status,
            "metadata": dict(run.metadata),
            "paper_trade_mode": run.paper_trade_mode,
            "live_trading_enabled": run.live_trading_enabled,
            "broker_execution_enabled": run.broker_execution_enabled,
        }
        return JsonSerializer.dumps(payload)

    @staticmethod
    def render_markdown(run: DailyCycleRun) -> str:
        run.validate()
        decision_id = (
            run.workflow_result.decision.identity.public_id if run.workflow_result is not None else "NONE"
        )
        return "\n".join(
            [
                "# Enterprise Daily Paper Cycle",
                "",
                f"- Cycle Date: {run.plan.cycle_date.isoformat()}",
                f"- Status: {run.status.value}",
                f"- Scheduled Time: {run.plan.scheduled_time.isoformat()}",
                f"- Timezone: {run.plan.timezone_name}",
                f"- Decision ID: {decision_id}",
                f"- Paper Trade Mode: {'YES' if run.paper_trade_mode else 'NO'}",
                "",
                "## Result",
                "",
                run.plan.reason,
                "",
                "## Investor Boundary",
                "",
                "The daily cycle stops at investor review. It does not assign capital, mutate portfolios, create OS schedules, or call broker APIs.",
                "",
            ]
        )
