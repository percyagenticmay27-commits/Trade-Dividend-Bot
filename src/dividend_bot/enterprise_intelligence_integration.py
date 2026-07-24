"""Governed integration of enterprise intelligence into event and evidence backbones.

This module coordinates existing workflow, event, and evidence services. It does not rebuild
intelligence, change decisions, approve investors, assign capital, mutate portfolios, or call brokers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from .enterprise_event_integration import EnterpriseEventIntegration, EventIntegrationRecord
from .enterprise_evidence_integration import EnterpriseEvidenceIntegration, EvidenceIntegrationResult
from .enterprise_workflow_orchestrator import EnterpriseWorkflowResult
from .platform_foundation import IdentifierFactory, JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_intelligence_integration"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Link completed enterprise intelligence workflows to immutable events and evidence."


@dataclass(frozen=True)
class EnterpriseIntelligenceIntegrationResult:
    integration_id: UUID
    workflow_id: str
    profile_id: UUID
    company_id: UUID
    decision_id: str
    event_record: EventIntegrationRecord
    evidence_result: EvidenceIntegrationResult
    completed_at: datetime
    metadata: Mapping[str, object]
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if not self.workflow_id.strip() or not self.decision_id.strip():
            raise PlatformValidationError("workflow_id and decision_id are required")
        if self.completed_at.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        self.event_record.validate()
        self.evidence_result.validate()
        if self.event_record.workflow_id != self.workflow_id:
            raise PlatformValidationError("event record must preserve workflow_id")
        if self.evidence_result.workflow_id != self.workflow_id:
            raise PlatformValidationError("evidence result must preserve workflow_id")
        if self.event_record.correlation_id != self.evidence_result.correlation_id:
            raise PlatformValidationError("event and evidence correlation IDs must match")
        event_ids = tuple(item.event.event_id for item in self.event_record.publications)
        evidence_event_ids = tuple(item.source_event_id for item in self.evidence_result.entries)
        if event_ids != evidence_event_ids:
            raise PlatformValidationError("evidence must preserve every event in deterministic order")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterpriseIntelligenceIntegration:
    """Connect completed workflow intelligence to append-only event and evidence services."""

    def __init__(
        self,
        event_integration: EnterpriseEventIntegration | None = None,
        evidence_integration: EnterpriseEvidenceIntegration | None = None,
    ) -> None:
        self._event_integration = event_integration or EnterpriseEventIntegration()
        self._evidence_integration = evidence_integration or EnterpriseEvidenceIntegration()
        self._history: list[EnterpriseIntelligenceIntegrationResult] = []
        self._integrated_workflows: set[str] = set()

    @property
    def event_integration(self) -> EnterpriseEventIntegration:
        return self._event_integration

    @property
    def evidence_integration(self) -> EnterpriseEvidenceIntegration:
        return self._evidence_integration

    def history(self) -> tuple[EnterpriseIntelligenceIntegrationResult, ...]:
        return tuple(self._history)

    def integrate(
        self,
        workflow: EnterpriseWorkflowResult,
        *,
        completed_at: datetime | None = None,
    ) -> EnterpriseIntelligenceIntegrationResult:
        workflow.validate()
        if workflow.workflow_id in self._integrated_workflows:
            raise PlatformValidationError("workflow intelligence has already been integrated")
        timestamp = completed_at or utc_now()
        if timestamp.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")

        event_record = self._event_integration.publish_workflow(workflow, published_at=timestamp)
        evidence_result = self._evidence_integration.preserve(event_record, completed_at=timestamp)
        profile = workflow.intelligence.profile
        result = EnterpriseIntelligenceIntegrationResult(
            integration_id=IdentifierFactory.new_internal_id(),
            workflow_id=workflow.workflow_id,
            profile_id=profile.identity.internal_id,
            company_id=profile.company_id,
            decision_id=workflow.decision.identity.public_id,
            event_record=event_record,
            evidence_result=evidence_result,
            completed_at=timestamp,
            metadata=MappingProxyType(
                {
                    "module_version": MODULE_VERSION,
                    "intelligence_quality": workflow.intelligence.quality_score,
                    "intelligence_completeness": workflow.intelligence.completeness_score,
                    "evidence_count": len(evidence_result.entries),
                    "investor_review_required": True,
                }
            ),
        )
        result.validate()
        self._history.append(result)
        self._integrated_workflows.add(workflow.workflow_id)
        return result

    @staticmethod
    def render_json(result: EnterpriseIntelligenceIntegrationResult) -> str:
        result.validate()
        return JsonSerializer.dumps(result)

    @staticmethod
    def render_markdown(result: EnterpriseIntelligenceIntegrationResult) -> str:
        result.validate()
        return "\n".join(
            [
                "# Enterprise Intelligence Integration",
                "",
                f"- Workflow ID: {result.workflow_id}",
                f"- Company ID: {result.company_id}",
                f"- Profile ID: {result.profile_id}",
                f"- Decision ID: {result.decision_id}",
                f"- Published Events: {len(result.event_record.publications)}",
                f"- Preserved Evidence Entries: {len(result.evidence_result.entries)}",
                f"- Investor Review Required: {'YES' if result.metadata['investor_review_required'] else 'NO'}",
                f"- Paper Trade Mode: {'YES' if result.paper_trade_mode else 'NO'}",
                "",
                "## Safety Boundary",
                "",
                "This integration preserves existing intelligence as events and evidence only. It does not approve decisions, assign capital, mutate portfolios, call brokers, or place orders.",
                "",
            ]
        )
