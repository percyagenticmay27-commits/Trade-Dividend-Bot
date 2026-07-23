"""Append-only evidence and AI CIO decision governance for the paper-only platform."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Iterable
from uuid import UUID

from .platform_entities import AICIODecision, DecisionState, EvidenceRecord
from .platform_foundation import PlatformValidationError, utc_now

MODULE_NAME = "platform_governance"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Append-only evidence storage, immutable decision history, and investor overrides."


class EvidenceAppendType(str, Enum):
    NEW_INFORMATION = "NEW_INFORMATION"
    CORRECTION = "CORRECTION"
    FOLLOW_UP = "FOLLOW_UP"
    OFFICIAL_RESPONSE = "OFFICIAL_RESPONSE"
    REGULATORY_UPDATE = "REGULATORY_UPDATE"
    MARKET_REACTION = "MARKET_REACTION"
    COMMITTEE_REQUEST = "COMMITTEE_REQUEST"
    INVESTOR_NOTE = "INVESTOR_NOTE"
    FINAL_RESOLUTION = "FINAL_RESOLUTION"


@dataclass(frozen=True)
class EvidenceAppendEntry:
    evidence_id: UUID
    append_type: EvidenceAppendType
    content: str
    source: str
    appended_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        if not self.content.strip() or not self.source.strip():
            raise PlatformValidationError("evidence append content and source must not be empty")
        if self.appended_at.tzinfo is None:
            raise PlatformValidationError("appended_at must be timezone-aware")


class EvidenceRepository:
    """In-memory append-only evidence repository.

    Persistent adapters may wrap this contract later, but they must preserve the same
    no-update and no-delete semantics.
    """

    def __init__(self) -> None:
        self._records: dict[UUID, EvidenceRecord] = {}
        self._appends: dict[UUID, list[EvidenceAppendEntry]] = {}

    def add(self, record: EvidenceRecord) -> None:
        record.validate()
        key = record.identity.internal_id
        if key in self._records:
            raise PlatformValidationError("evidence records are immutable and cannot be replaced")
        self._records[key] = record
        self._appends[key] = []

    def append(self, entry: EvidenceAppendEntry) -> None:
        entry.validate()
        if entry.evidence_id not in self._records:
            raise PlatformValidationError("cannot append to unknown evidence record")
        self._appends[entry.evidence_id].append(entry)

    def get(self, evidence_id: UUID) -> EvidenceRecord:
        try:
            return self._records[evidence_id]
        except KeyError as exc:
            raise PlatformValidationError("evidence record not found") from exc

    def timeline(self, evidence_id: UUID) -> tuple[EvidenceRecord | EvidenceAppendEntry, ...]:
        record = self.get(evidence_id)
        return (record, *tuple(self._appends[evidence_id]))

    def list_for_subject(self, subject_id: UUID) -> tuple[EvidenceRecord, ...]:
        return tuple(
            sorted(
                (record for record in self._records.values() if record.subject_id == subject_id),
                key=lambda item: (item.observed_at, item.identity.public_id),
            )
        )

    def __len__(self) -> int:
        return len(self._records)


@dataclass(frozen=True)
class DecisionLedgerEntry:
    decision: AICIODecision
    recorded_at: datetime = field(default_factory=utc_now)
    event_type: str = "DECISION_RECORDED"
    note: str = ""

    def validate(self) -> None:
        self.decision.validate()
        if self.recorded_at.tzinfo is None:
            raise PlatformValidationError("recorded_at must be timezone-aware")
        if not self.event_type.strip():
            raise PlatformValidationError("event_type must not be empty")


@dataclass(frozen=True)
class InvestorOverrideRecord:
    original_decision_id: UUID
    replacement_decision_id: UUID
    investor_id: str
    reason: str
    created_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        if self.original_decision_id == self.replacement_decision_id:
            raise PlatformValidationError("override must create a distinct replacement decision")
        if not self.investor_id.strip() or not self.reason.strip():
            raise PlatformValidationError("investor override requires investor_id and reason")
        if self.created_at.tzinfo is None:
            raise PlatformValidationError("created_at must be timezone-aware")


_ALLOWED_TRANSITIONS: dict[DecisionState, frozenset[DecisionState]] = {
    DecisionState.DRAFT: frozenset({DecisionState.READY_FOR_REVIEW, DecisionState.ARCHIVED}),
    DecisionState.READY_FOR_REVIEW: frozenset({
        DecisionState.UNDER_COMMITTEE_COLLABORATION,
        DecisionState.UNDER_CONSTITUTIONAL_REVIEW,
        DecisionState.ARCHIVED,
    }),
    DecisionState.UNDER_COMMITTEE_COLLABORATION: frozenset({
        DecisionState.UNDER_CONSTITUTIONAL_REVIEW,
        DecisionState.READY_FOR_REVIEW,
        DecisionState.ARCHIVED,
    }),
    DecisionState.UNDER_CONSTITUTIONAL_REVIEW: frozenset({
        DecisionState.READY_FOR_CIO,
        DecisionState.READY_FOR_REVIEW,
        DecisionState.ARCHIVED,
    }),
    DecisionState.READY_FOR_CIO: frozenset({
        DecisionState.IMPLEMENTED,
        DecisionState.INVESTOR_OVERRIDE_PENDING,
        DecisionState.EXPIRED,
        DecisionState.ARCHIVED,
    }),
    DecisionState.INVESTOR_OVERRIDE_PENDING: frozenset({
        DecisionState.OVERRIDDEN_BY_INVESTOR,
        DecisionState.READY_FOR_CIO,
    }),
    DecisionState.IMPLEMENTED: frozenset({
        DecisionState.SUPERSEDED,
        DecisionState.ARCHIVED,
        DecisionState.INVESTOR_OVERRIDE_PENDING,
    }),
    DecisionState.OVERRIDDEN_BY_INVESTOR: frozenset({DecisionState.ARCHIVED}),
    DecisionState.SUPERSEDED: frozenset({DecisionState.ARCHIVED}),
    DecisionState.EXPIRED: frozenset({DecisionState.ARCHIVED}),
    DecisionState.ARCHIVED: frozenset(),
}


class DecisionLedger:
    """Append-only ledger preserving every AI CIO decision and lifecycle event."""

    def __init__(self) -> None:
        self._decisions: dict[UUID, AICIODecision] = {}
        self._entries: list[DecisionLedgerEntry] = []
        self._overrides: list[InvestorOverrideRecord] = []

    def record(self, decision: AICIODecision, *, note: str = "") -> None:
        decision.validate()
        key = decision.identity.internal_id
        if key in self._decisions:
            raise PlatformValidationError("decision history is immutable; duplicate decision id")
        self._decisions[key] = decision
        self._entries.append(DecisionLedgerEntry(decision=decision, note=note))

    def transition(self, decision_id: UUID, new_state: DecisionState, *, note: str = "") -> AICIODecision:
        current = self.get(decision_id)
        if new_state not in _ALLOWED_TRANSITIONS[current.state]:
            raise PlatformValidationError(
                f"invalid decision transition: {current.state.value} -> {new_state.value}"
            )
        updated = replace(current, state=new_state)
        updated.validate()
        self._decisions[decision_id] = updated
        self._entries.append(
            DecisionLedgerEntry(
                decision=updated,
                event_type="STATE_TRANSITION",
                note=note,
            )
        )
        return updated

    def override(
        self,
        original_decision_id: UUID,
        replacement_decision: AICIODecision,
        *,
        investor_id: str,
        reason: str,
    ) -> InvestorOverrideRecord:
        original = self.get(original_decision_id)
        if original.state not in {
            DecisionState.READY_FOR_CIO,
            DecisionState.IMPLEMENTED,
            DecisionState.INVESTOR_OVERRIDE_PENDING,
        }:
            raise PlatformValidationError("decision is not eligible for investor override")
        replacement_decision.validate()
        if replacement_decision.strategy_id != original.strategy_id:
            raise PlatformValidationError("override replacement must preserve strategy attribution")
        if replacement_decision.identity.internal_id in self._decisions:
            raise PlatformValidationError("replacement decision already exists")

        if original.state is not DecisionState.INVESTOR_OVERRIDE_PENDING:
            self.transition(original_decision_id, DecisionState.INVESTOR_OVERRIDE_PENDING)
        self.transition(original_decision_id, DecisionState.OVERRIDDEN_BY_INVESTOR, note=reason)
        self.record(replacement_decision, note=f"Investor override of {original.identity.public_id}")

        override = InvestorOverrideRecord(
            original_decision_id=original_decision_id,
            replacement_decision_id=replacement_decision.identity.internal_id,
            investor_id=investor_id,
            reason=reason,
        )
        override.validate()
        self._overrides.append(override)
        return override

    def get(self, decision_id: UUID) -> AICIODecision:
        try:
            return self._decisions[decision_id]
        except KeyError as exc:
            raise PlatformValidationError("decision not found") from exc

    def history(self, decision_id: UUID) -> tuple[DecisionLedgerEntry, ...]:
        self.get(decision_id)
        return tuple(
            entry
            for entry in self._entries
            if entry.decision.identity.internal_id == decision_id
        )

    def list_by_strategy(self, strategy_id: str) -> tuple[AICIODecision, ...]:
        if not strategy_id.strip():
            raise PlatformValidationError("strategy_id must not be empty")
        return tuple(
            decision
            for decision in self._decisions.values()
            if decision.strategy_id == strategy_id
        )

    @property
    def overrides(self) -> tuple[InvestorOverrideRecord, ...]:
        return tuple(self._overrides)

    @property
    def entries(self) -> tuple[DecisionLedgerEntry, ...]:
        return tuple(self._entries)
