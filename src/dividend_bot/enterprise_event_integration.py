"""Additive event publication for governed enterprise workflow results.

This module observes completed workflow and daily-cycle records and publishes immutable events.
It does not change business state, approve investors, assign capital, mutate portfolios, or call brokers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from .enterprise_daily_cycle import DailyCycleRun, DailyCycleStatus
from .enterprise_event_bus import EnterpriseEvent, EnterpriseEventBus, EnterpriseEventType, EventPublication
from .enterprise_workflow_orchestrator import EnterpriseWorkflowResult
from .platform_foundation import JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_event_integration"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Publish governed workflow milestones to the synchronous enterprise event bus."


@dataclass(frozen=True)
class EventIntegrationRecord:
    integration_id: UUID
    workflow_id: str
    correlation_id: str
    publications: tuple[EventPublication, ...]
    completed_at: datetime
    metadata: Mapping[str, object]
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if not self.workflow_id.strip() or not self.correlation_id.strip():
            raise PlatformValidationError("workflow_id and correlation_id are required")
        if self.completed_at.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        if not self.publications:
            raise PlatformValidationError("event integration requires publications")
        previous: UUID | None = None
        for publication in self.publications:
            publication.validate()
            event = publication.event
            if event.correlation_id != self.correlation_id:
                raise PlatformValidationError("all events must preserve the integration correlation_id")
            if previous is not None and event.causation_id != previous:
                raise PlatformValidationError("events must preserve the causation chain")
            previous = event.event_id
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterpriseEventIntegration:
    """Publish additive workflow milestones without mutating the source workflow."""

    def __init__(self, event_bus: EnterpriseEventBus | None = None) -> None:
        self._event_bus = event_bus or EnterpriseEventBus()
        self._history: list[EventIntegrationRecord] = []
        self._published_workflows: set[str] = set()

    @property
    def event_bus(self) -> EnterpriseEventBus:
        return self._event_bus

    def history(self) -> tuple[EventIntegrationRecord, ...]:
        return tuple(self._history)

    def publish_workflow(
        self,
        result: EnterpriseWorkflowResult,
        *,
        published_at: datetime | None = None,
    ) -> EventIntegrationRecord:
        result.validate()
        if result.workflow_id in self._published_workflows:
            raise PlatformValidationError("workflow events have already been published")
        timestamp = published_at or utc_now()
        if timestamp.tzinfo is None:
            raise PlatformValidationError("published_at must be timezone-aware")

        decision_id = result.decision.identity.public_id
        strategy_ids = tuple(advisory.strategy_id for advisory in result.decision.strategy_advisories)
        strategy_id = strategy_ids[0] if len(set(strategy_ids)) == 1 else None
        correlation_id = result.workflow_id
        definitions = (
            (
                EnterpriseEventType.INTELLIGENCE_UPDATED,
                "ENTERPRISE_INTELLIGENCE_SERVICE",
                str(result.intelligence.profile.identity.internal_id),
                {
                    "workflow_id": result.workflow_id,
                    "quality_score": result.intelligence.quality_score,
                    "completeness_score": result.intelligence.completeness_score,
                    "evidence_count": result.intelligence.evidence_count,
                },
            ),
            (
                EnterpriseEventType.CIO_ADVISORY_CREATED,
                "ENTERPRISE_INTELLIGENCE_CIO_PIPELINE",
                result.workflow_id,
                {
                    "workflow_id": result.workflow_id,
                    "recommendation": result.pipeline.advisory.recommendation.value,
                    "confidence": result.pipeline.advisory.confidence,
                    "gates_passed": result.pipeline.gates_passed,
                },
            ),
            (
                EnterpriseEventType.DECISION_CREATED,
                "ENTERPRISE_DECISION_ENGINE",
                decision_id,
                {
                    "workflow_id": result.workflow_id,
                    "decision_id": decision_id,
                    "action": result.decision.action.value,
                    "state": result.decision.state.value,
                },
            ),
            (
                EnterpriseEventType.DECISION_GOVERNANCE_UPDATED,
                "ENTERPRISE_WORKFLOW_ORCHESTRATOR",
                decision_id,
                {
                    "workflow_id": result.workflow_id,
                    "decision_id": decision_id,
                    "investor_review_required": True,
                    "completed_stages": result.completed_stages,
                },
            ),
        )

        publications: list[EventPublication] = []
        cause: UUID | None = None
        for event_type, source, aggregate_id, payload in definitions:
            event = self._event_bus.create_event(
                event_type,
                source,
                aggregate_id,
                payload,
                strategy_id=strategy_id,
                correlation_id=correlation_id,
                causation_id=cause,
                occurred_at=result.completed_at,
            )
            publication = self._event_bus.publish(event, published_at=timestamp)
            publications.append(publication)
            cause = event.event_id

        record = EventIntegrationRecord(
            integration_id=publications[0].event.event_id,
            workflow_id=result.workflow_id,
            correlation_id=correlation_id,
            publications=tuple(publications),
            completed_at=timestamp,
            metadata=MappingProxyType(
                {
                    "module_version": MODULE_VERSION,
                    "investor_review_required": True,
                    "strategy_ids": strategy_ids,
                }
            ),
        )
        record.validate()
        self._history.append(record)
        self._published_workflows.add(result.workflow_id)
        return record

    def publish_daily_cycle(
        self,
        run: DailyCycleRun,
        *,
        published_at: datetime | None = None,
    ) -> EventIntegrationRecord | None:
        run.validate()
        if run.status is not DailyCycleStatus.COMPLETED:
            return None
        if run.workflow_result is None:
            raise PlatformValidationError("completed daily cycle requires workflow_result")
        return self.publish_workflow(run.workflow_result, published_at=published_at or run.completed_at)

    @staticmethod
    def render_json(record: EventIntegrationRecord) -> str:
        record.validate()
        return JsonSerializer.dumps(record)

    @staticmethod
    def render_markdown(record: EventIntegrationRecord) -> str:
        record.validate()
        lines = [
            "# Enterprise Event Integration",
            "",
            f"- Workflow ID: {record.workflow_id}",
            f"- Correlation ID: {record.correlation_id}",
            f"- Publications: {len(record.publications)}",
            f"- Paper Trade Mode: {'YES' if record.paper_trade_mode else 'NO'}",
            "",
            "## Event Sequence",
            "",
        ]
        lines.extend(
            f"- {index}. {publication.event.event_type.value} — {publication.event.source_service_id}"
            for index, publication in enumerate(record.publications, start=1)
        )
        lines.extend(
            [
                "",
                "## Investor Boundary",
                "",
                "Events are additive notifications only. Investor approval, capital assignment, portfolio mutation, broker calls, and order placement are not performed.",
                "",
            ]
        )
        return "\n".join(lines)
