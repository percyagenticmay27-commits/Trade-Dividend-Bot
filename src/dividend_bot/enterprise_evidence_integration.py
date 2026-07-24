"""Append-only evidence integration for governed enterprise workflow events.

This module converts completed event-integration records into immutable evidence entries. It does
not overwrite evidence, approve decisions, assign capital, mutate portfolios, or call brokers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from .enterprise_event_integration import EventIntegrationRecord
from .platform_foundation import IdentifierFactory, JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_evidence_integration"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Preserve governed workflow milestones as append-only enterprise evidence."


class EvidenceEntryType(str, Enum):
    INTELLIGENCE = "INTELLIGENCE"
    CIO_ADVISORY = "CIO_ADVISORY"
    DECISION = "DECISION"
    GOVERNANCE = "GOVERNANCE"
    INVESTOR_ACTION = "INVESTOR_ACTION"
    STRATEGY_RESULT = "STRATEGY_RESULT"
    FOLLOW_UP = "FOLLOW_UP"
    CORRECTION = "CORRECTION"


@dataclass(frozen=True)
class EnterpriseEvidenceEntry:
    evidence_id: UUID
    sequence: int
    entry_type: EvidenceEntryType
    workflow_id: str
    correlation_id: str
    source_event_id: UUID
    source_service_id: str
    aggregate_id: str
    payload: Mapping[str, object]
    recorded_at: datetime = field(default_factory=utc_now)
    strategy_id: str | None = None
    supersedes_evidence_id: UUID | None = None
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if self.sequence < 1:
            raise PlatformValidationError("evidence sequence must be positive")
        if not self.workflow_id.strip() or not self.correlation_id.strip():
            raise PlatformValidationError("workflow_id and correlation_id are required")
        if not self.source_service_id or self.source_service_id != self.source_service_id.upper():
            raise PlatformValidationError("source_service_id must be uppercase")
        if not self.aggregate_id.strip() or not isinstance(self.payload, Mapping):
            raise PlatformValidationError("aggregate_id and evidence payload are required")
        if self.recorded_at.tzinfo is None:
            raise PlatformValidationError("recorded_at must be timezone-aware")
        if self.strategy_id is not None and self.strategy_id != self.strategy_id.upper():
            raise PlatformValidationError("strategy_id must be uppercase when provided")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


@dataclass(frozen=True)
class EvidenceIntegrationResult:
    integration_id: UUID
    workflow_id: str
    correlation_id: str
    entries: tuple[EnterpriseEvidenceEntry, ...]
    completed_at: datetime
    metadata: Mapping[str, object]
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if not self.entries:
            raise PlatformValidationError("evidence integration requires entries")
        if self.completed_at.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        for index, entry in enumerate(self.entries, start=1):
            entry.validate()
            if entry.sequence != index:
                raise PlatformValidationError("evidence entries must preserve deterministic sequence")
            if entry.workflow_id != self.workflow_id or entry.correlation_id != self.correlation_id:
                raise PlatformValidationError("evidence entries must preserve workflow linkage")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterpriseEvidenceRepository:
    """Append-only in-memory evidence repository with workflow deduplication."""

    def __init__(self) -> None:
        self._entries: list[EnterpriseEvidenceEntry] = []
        self._source_event_ids: set[UUID] = set()

    def append(self, entry: EnterpriseEvidenceEntry) -> None:
        entry.validate()
        if entry.source_event_id in self._source_event_ids:
            raise PlatformValidationError("source event has already been preserved as evidence")
        if entry.sequence != len(self._entries) + 1:
            raise PlatformValidationError("repository evidence sequence must be append-only")
        self._entries.append(entry)
        self._source_event_ids.add(entry.source_event_id)

    def all(self) -> tuple[EnterpriseEvidenceEntry, ...]:
        return tuple(self._entries)

    def for_workflow(self, workflow_id: str) -> tuple[EnterpriseEvidenceEntry, ...]:
        return tuple(item for item in self._entries if item.workflow_id == workflow_id)


class EnterpriseEvidenceIntegration:
    def __init__(self, repository: EnterpriseEvidenceRepository | None = None) -> None:
        self._repository = repository or EnterpriseEvidenceRepository()
        self._history: list[EvidenceIntegrationResult] = []
        self._integrated_workflows: set[str] = set()

    @property
    def repository(self) -> EnterpriseEvidenceRepository:
        return self._repository

    def history(self) -> tuple[EvidenceIntegrationResult, ...]:
        return tuple(self._history)

    def preserve(self, record: EventIntegrationRecord, *, completed_at: datetime | None = None) -> EvidenceIntegrationResult:
        record.validate()
        if record.workflow_id in self._integrated_workflows:
            raise PlatformValidationError("workflow evidence has already been integrated")
        timestamp = completed_at or utc_now()
        if timestamp.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        type_map = {
            "INTELLIGENCE_UPDATED": EvidenceEntryType.INTELLIGENCE,
            "CIO_ADVISORY_CREATED": EvidenceEntryType.CIO_ADVISORY,
            "DECISION_CREATED": EvidenceEntryType.DECISION,
            "DECISION_GOVERNANCE_UPDATED": EvidenceEntryType.GOVERNANCE,
        }
        entries: list[EnterpriseEvidenceEntry] = []
        for publication in record.publications:
            event = publication.event
            entry = EnterpriseEvidenceEntry(
                evidence_id=IdentifierFactory.new_internal_id(),
                sequence=len(self._repository.all()) + 1,
                entry_type=type_map[event.event_type.value],
                workflow_id=record.workflow_id,
                correlation_id=record.correlation_id,
                source_event_id=event.event_id,
                source_service_id=event.source_service_id,
                aggregate_id=event.aggregate_id,
                payload=MappingProxyType(dict(event.payload)),
                recorded_at=timestamp,
                strategy_id=event.strategy_id,
            )
            self._repository.append(entry)
            entries.append(entry)
        result = EvidenceIntegrationResult(
            integration_id=IdentifierFactory.new_internal_id(),
            workflow_id=record.workflow_id,
            correlation_id=record.correlation_id,
            entries=tuple(entries),
            completed_at=timestamp,
            metadata=MappingProxyType({"module_version": MODULE_VERSION, "append_only": True}),
        )
        result.validate()
        self._history.append(result)
        self._integrated_workflows.add(record.workflow_id)
        return result

    @staticmethod
    def render_json(result: EvidenceIntegrationResult) -> str:
        result.validate()
        return JsonSerializer.dumps(result)

    @staticmethod
    def render_markdown(result: EvidenceIntegrationResult) -> str:
        result.validate()
        lines = [
            "# Enterprise Evidence Integration", "",
            f"- Workflow ID: {result.workflow_id}",
            f"- Correlation ID: {result.correlation_id}",
            f"- Evidence Entries: {len(result.entries)}",
            f"- Append Only: YES",
            f"- Paper Trade Mode: {'YES' if result.paper_trade_mode else 'NO'}", "",
            "## Evidence Sequence", "",
        ]
        lines.extend(f"- {item.sequence}. {item.entry_type.value} — {item.source_service_id}" for item in result.entries)
        lines.extend(["", "## Safety Boundary", "", "Evidence preservation is additive only. No approval, capital movement, portfolio mutation, broker call, or order placement is performed.", ""])
        return "\n".join(lines)
