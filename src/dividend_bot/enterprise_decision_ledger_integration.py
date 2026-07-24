"""Append-only integration of governed enterprise decisions with evidence traceability.

This module records immutable decision-ledger snapshots only. It does not approve decisions,
assign capital, mutate portfolios, call brokers, or place orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from .enterprise_intelligence_integration import EnterpriseIntelligenceIntegrationResult
from .enterprise_workflow_orchestrator import EnterpriseWorkflowResult
from .platform_foundation import IdentifierFactory, JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_decision_ledger_integration"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Preserve governed enterprise decisions in an immutable append-only integration ledger."


@dataclass(frozen=True)
class EnterpriseDecisionLedgerEntry:
    ledger_entry_id: UUID
    sequence: int
    workflow_id: str
    correlation_id: str
    decision_internal_id: UUID
    decision_public_id: str
    company_id: UUID
    profile_id: UUID
    action: str
    decision_state: str
    strategy_ids: tuple[str, ...]
    evidence_ids: tuple[UUID, ...]
    supersedes_decision_id: UUID | None
    recorded_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if self.sequence < 1:
            raise PlatformValidationError("ledger sequence must be positive")
        if not self.workflow_id.strip() or not self.correlation_id.strip():
            raise PlatformValidationError("workflow_id and correlation_id are required")
        if not self.decision_public_id.strip() or not self.action.strip() or not self.decision_state.strip():
            raise PlatformValidationError("decision identity, action, and state are required")
        if not self.strategy_ids or any(not item or item != item.upper() for item in self.strategy_ids):
            raise PlatformValidationError("strategy_ids must contain uppercase values")
        if not self.evidence_ids:
            raise PlatformValidationError("at least one evidence ID is required")
        if self.recorded_at.tzinfo is None:
            raise PlatformValidationError("recorded_at must be timezone-aware")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterpriseDecisionIntegrationLedger:
    """Append-only decision integration ledger with chain validation."""

    def __init__(self) -> None:
        self._entries: list[EnterpriseDecisionLedgerEntry] = []
        self._internal_ids: set[UUID] = set()
        self._public_ids: set[str] = set()
        self._workflow_ids: set[str] = set()

    def append(self, entry: EnterpriseDecisionLedgerEntry) -> None:
        entry.validate()
        if entry.sequence != len(self._entries) + 1:
            raise PlatformValidationError("decision ledger sequence must be append-only")
        if entry.decision_internal_id in self._internal_ids:
            raise PlatformValidationError("decision internal ID already exists")
        if entry.decision_public_id in self._public_ids:
            raise PlatformValidationError("decision public ID already exists")
        if entry.workflow_id in self._workflow_ids:
            raise PlatformValidationError("workflow decision already exists")
        if entry.supersedes_decision_id is not None:
            previous = next(
                (item for item in self._entries if item.decision_internal_id == entry.supersedes_decision_id),
                None,
            )
            if previous is None:
                raise PlatformValidationError("superseded decision must already exist in ledger")
            if previous.company_id != entry.company_id:
                raise PlatformValidationError("superseded decision must belong to the same company")
        self._entries.append(entry)
        self._internal_ids.add(entry.decision_internal_id)
        self._public_ids.add(entry.decision_public_id)
        self._workflow_ids.add(entry.workflow_id)

    def all(self) -> tuple[EnterpriseDecisionLedgerEntry, ...]:
        return tuple(self._entries)

    def for_company(self, company_id: UUID) -> tuple[EnterpriseDecisionLedgerEntry, ...]:
        return tuple(item for item in self._entries if item.company_id == company_id)

    def latest_for_company(self, company_id: UUID) -> EnterpriseDecisionLedgerEntry | None:
        matches = self.for_company(company_id)
        return matches[-1] if matches else None


@dataclass(frozen=True)
class EnterpriseDecisionLedgerIntegrationResult:
    integration_id: UUID
    entry: EnterpriseDecisionLedgerEntry
    completed_at: datetime
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        self.entry.validate()
        if self.completed_at.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterpriseDecisionLedgerIntegration:
    def __init__(self, ledger: EnterpriseDecisionIntegrationLedger | None = None) -> None:
        self._ledger = ledger or EnterpriseDecisionIntegrationLedger()
        self._history: list[EnterpriseDecisionLedgerIntegrationResult] = []

    @property
    def ledger(self) -> EnterpriseDecisionIntegrationLedger:
        return self._ledger

    def history(self) -> tuple[EnterpriseDecisionLedgerIntegrationResult, ...]:
        return tuple(self._history)

    def integrate(
        self,
        workflow: EnterpriseWorkflowResult,
        intelligence: EnterpriseIntelligenceIntegrationResult,
        *,
        completed_at: datetime | None = None,
    ) -> EnterpriseDecisionLedgerIntegrationResult:
        workflow.validate()
        intelligence.validate()
        if intelligence.workflow_id != workflow.workflow_id:
            raise PlatformValidationError("intelligence integration must match workflow")
        if intelligence.profile_id != workflow.decision.profile_id:
            raise PlatformValidationError("intelligence profile must match decision profile")
        if intelligence.company_id != workflow.decision.company_id:
            raise PlatformValidationError("intelligence company must match decision company")
        if intelligence.decision_id != workflow.decision.identity.public_id:
            raise PlatformValidationError("intelligence decision must match workflow decision")
        timestamp = completed_at or utc_now()
        if timestamp.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")

        evidence_ids = tuple(item.evidence_id for item in intelligence.evidence_result.entries)
        strategy_ids = tuple(dict.fromkeys(item.strategy_id for item in workflow.decision.strategy_advisories))
        entry = EnterpriseDecisionLedgerEntry(
            ledger_entry_id=IdentifierFactory.new_internal_id(),
            sequence=len(self._ledger.all()) + 1,
            workflow_id=workflow.workflow_id,
            correlation_id=intelligence.event_record.correlation_id,
            decision_internal_id=workflow.decision.identity.internal_id,
            decision_public_id=workflow.decision.identity.public_id,
            company_id=workflow.decision.company_id,
            profile_id=workflow.decision.profile_id,
            action=workflow.decision.action.value,
            decision_state=workflow.decision.state.value,
            strategy_ids=strategy_ids,
            evidence_ids=evidence_ids,
            supersedes_decision_id=workflow.decision.supersedes_decision_id,
            recorded_at=timestamp,
            metadata=MappingProxyType(
                {
                    "module_version": MODULE_VERSION,
                    "constitution_version": workflow.decision.constitution_version,
                    "confidence": workflow.decision.confidence,
                    "opportunity_quality": workflow.decision.opportunity_quality,
                    "investor_status": "PENDING",
                    "append_only": True,
                }
            ),
        )
        self._ledger.append(entry)
        result = EnterpriseDecisionLedgerIntegrationResult(
            integration_id=IdentifierFactory.new_internal_id(),
            entry=entry,
            completed_at=timestamp,
        )
        result.validate()
        self._history.append(result)
        return result

    @staticmethod
    def render_json(result: EnterpriseDecisionLedgerIntegrationResult) -> str:
        result.validate()
        return JsonSerializer.dumps(result)

    @staticmethod
    def render_markdown(result: EnterpriseDecisionLedgerIntegrationResult) -> str:
        result.validate()
        entry = result.entry
        return "\n".join(
            [
                "# Enterprise Decision Ledger",
                "",
                f"- Sequence: {entry.sequence}",
                f"- Decision ID: {entry.decision_public_id}",
                f"- Workflow ID: {entry.workflow_id}",
                f"- Correlation ID: {entry.correlation_id}",
                f"- Company ID: {entry.company_id}",
                f"- Profile ID: {entry.profile_id}",
                f"- Action: {entry.action}",
                f"- Governance State: {entry.decision_state}",
                f"- Strategies: {', '.join(entry.strategy_ids)}",
                f"- Evidence Count: {len(entry.evidence_ids)}",
                f"- Investor Status: {entry.metadata['investor_status']}",
                f"- Paper Trade Mode: {'YES' if entry.paper_trade_mode else 'NO'}",
                "",
                "## Safety Boundary",
                "",
                "This append-only ledger records governed decisions only. It does not approve investors, assign capital, mutate portfolios, call brokers, or place orders.",
                "",
            ]
        )
