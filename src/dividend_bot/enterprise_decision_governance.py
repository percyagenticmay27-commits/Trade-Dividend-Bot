"""Append-only governance workflow for canonical enterprise investment decisions.

Committees analyze and recommend but never vote or decide. Constitutional review and
investor actions are preserved as immutable records linked to the original Enterprise
Decision. This module is paper-only and exposes no broker or order interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping
from uuid import UUID, uuid4

from .enterprise_decision_engine import EnterpriseDecision, EnterpriseDecisionAction
from .platform_entities import DecisionState
from .platform_foundation import JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_decision_governance"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Append-only committee, constitutional, and investor governance for enterprise decisions."


class CommitteeReviewOutcome(str, Enum):
    SUPPORT = "SUPPORT"
    CONCERN = "CONCERN"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"


class ConstitutionalOutcome(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class InvestorDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    OVERRIDE = "OVERRIDE"


class GovernanceEventType(str, Enum):
    LIFECYCLE_TRANSITION = "LIFECYCLE_TRANSITION"
    COMMITTEE_REVIEW = "COMMITTEE_REVIEW"
    CONSTITUTIONAL_REVIEW = "CONSTITUTIONAL_REVIEW"
    INVESTOR_DECISION = "INVESTOR_DECISION"


@dataclass(frozen=True)
class CommitteeReviewRecord:
    review_id: UUID
    decision_id: UUID
    committee_id: str
    outcome: CommitteeReviewOutcome
    analysis: str
    evidence_requests: tuple[str, ...] = ()
    reviewed_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        if not self.committee_id or self.committee_id != self.committee_id.upper():
            raise PlatformValidationError("committee_id must be non-empty uppercase text")
        if not self.analysis.strip():
            raise PlatformValidationError("committee analysis must not be empty")
        if self.reviewed_at.tzinfo is None:
            raise PlatformValidationError("committee review timestamp must be timezone-aware")
        if self.outcome is CommitteeReviewOutcome.REQUEST_MORE_EVIDENCE and not self.evidence_requests:
            raise PlatformValidationError("REQUEST_MORE_EVIDENCE requires evidence_requests")


@dataclass(frozen=True)
class ConstitutionalReviewRecord:
    review_id: UUID
    decision_id: UUID
    constitution_version: str
    outcome: ConstitutionalOutcome
    checks: Mapping[str, bool]
    rationale: str
    reviewed_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        if not self.constitution_version.strip() or not self.rationale.strip():
            raise PlatformValidationError("constitution_version and rationale are required")
        if self.reviewed_at.tzinfo is None:
            raise PlatformValidationError("constitutional review timestamp must be timezone-aware")
        if not self.checks:
            raise PlatformValidationError("constitutional review requires checks")
        if self.outcome is ConstitutionalOutcome.PASSED and not all(bool(value) for value in self.checks.values()):
            raise PlatformValidationError("PASSED constitutional review requires every check to pass")


@dataclass(frozen=True)
class InvestorDecisionRecord:
    record_id: UUID
    decision_id: UUID
    investor_id: str
    decision: InvestorDecision
    reason: str
    override_action: EnterpriseDecisionAction | None = None
    decided_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        if not self.investor_id.strip() or not self.reason.strip():
            raise PlatformValidationError("investor_id and reason are required")
        if self.decided_at.tzinfo is None:
            raise PlatformValidationError("investor decision timestamp must be timezone-aware")
        if self.decision is InvestorDecision.OVERRIDE and self.override_action is None:
            raise PlatformValidationError("investor override requires override_action")
        if self.decision is not InvestorDecision.OVERRIDE and self.override_action is not None:
            raise PlatformValidationError("override_action is only valid for OVERRIDE")


@dataclass(frozen=True)
class GovernanceEvent:
    event_id: UUID
    decision_id: UUID
    event_type: GovernanceEventType
    from_state: DecisionState
    to_state: DecisionState
    actor_id: str
    reason: str
    occurred_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        if not self.actor_id.strip() or not self.reason.strip():
            raise PlatformValidationError("governance event actor_id and reason are required")
        if self.occurred_at.tzinfo is None:
            raise PlatformValidationError("governance event timestamp must be timezone-aware")
        if self.from_state is self.to_state:
            raise PlatformValidationError("governance transition must change state")


@dataclass(frozen=True)
class DecisionGovernanceSnapshot:
    decision: EnterpriseDecision
    current_state: DecisionState
    committee_reviews: tuple[CommitteeReviewRecord, ...]
    constitutional_reviews: tuple[ConstitutionalReviewRecord, ...]
    investor_decisions: tuple[InvestorDecisionRecord, ...]
    events: tuple[GovernanceEvent, ...]
    effective_action: EnterpriseDecisionAction
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        self.decision.validate()
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")
        for record in self.committee_reviews:
            record.validate()
        for record in self.constitutional_reviews:
            record.validate()
        for record in self.investor_decisions:
            record.validate()
        for event in self.events:
            event.validate()


_ALLOWED_TRANSITIONS: Mapping[DecisionState, frozenset[DecisionState]] = {
    DecisionState.READY_FOR_REVIEW: frozenset({DecisionState.UNDER_COMMITTEE_COLLABORATION, DecisionState.ARCHIVED}),
    DecisionState.READY_FOR_CIO: frozenset({DecisionState.UNDER_COMMITTEE_COLLABORATION, DecisionState.UNDER_CONSTITUTIONAL_REVIEW}),
    DecisionState.UNDER_COMMITTEE_COLLABORATION: frozenset({DecisionState.UNDER_CONSTITUTIONAL_REVIEW, DecisionState.READY_FOR_REVIEW}),
    DecisionState.UNDER_CONSTITUTIONAL_REVIEW: frozenset({DecisionState.INVESTOR_OVERRIDE_PENDING, DecisionState.READY_FOR_REVIEW}),
    DecisionState.INVESTOR_OVERRIDE_PENDING: frozenset({DecisionState.IMPLEMENTED, DecisionState.OVERRIDDEN_BY_INVESTOR, DecisionState.ARCHIVED}),
    DecisionState.OVERRIDDEN_BY_INVESTOR: frozenset({DecisionState.IMPLEMENTED, DecisionState.ARCHIVED}),
    DecisionState.IMPLEMENTED: frozenset({DecisionState.ARCHIVED, DecisionState.SUPERSEDED}),
    DecisionState.SUPERSEDED: frozenset({DecisionState.ARCHIVED}),
}


class EnterpriseDecisionGovernance:
    """Maintain append-only governance records without mutating the original decision."""

    def __init__(self) -> None:
        self._decisions: dict[UUID, EnterpriseDecision] = {}
        self._states: dict[UUID, DecisionState] = {}
        self._committee_reviews: list[CommitteeReviewRecord] = []
        self._constitutional_reviews: list[ConstitutionalReviewRecord] = []
        self._investor_decisions: list[InvestorDecisionRecord] = []
        self._events: list[GovernanceEvent] = []

    def register(self, decision: EnterpriseDecision) -> None:
        decision.validate()
        decision_id = decision.identity.internal_id
        if decision_id in self._decisions:
            raise PlatformValidationError("decision is already registered for governance")
        self._decisions[decision_id] = decision
        self._states[decision_id] = decision.state

    def state(self, decision_id: UUID) -> DecisionState:
        self._require_decision(decision_id)
        return self._states[decision_id]

    def transition(self, decision_id: UUID, to_state: DecisionState, *, actor_id: str, reason: str) -> GovernanceEvent:
        self._require_decision(decision_id)
        from_state = self._states[decision_id]
        if to_state not in _ALLOWED_TRANSITIONS.get(from_state, frozenset()):
            raise PlatformValidationError(f"invalid decision transition: {from_state.value} -> {to_state.value}")
        event = GovernanceEvent(uuid4(), decision_id, GovernanceEventType.LIFECYCLE_TRANSITION, from_state, to_state, actor_id, reason)
        event.validate()
        self._states[decision_id] = to_state
        self._events.append(event)
        return event

    def add_committee_review(self, decision_id: UUID, *, committee_id: str, outcome: CommitteeReviewOutcome, analysis: str, evidence_requests: tuple[str, ...] = ()) -> CommitteeReviewRecord:
        self._require_state(decision_id, DecisionState.UNDER_COMMITTEE_COLLABORATION)
        record = CommitteeReviewRecord(uuid4(), decision_id, committee_id, outcome, analysis, evidence_requests)
        record.validate()
        self._committee_reviews.append(record)
        return record

    def add_constitutional_review(self, decision_id: UUID, *, outcome: ConstitutionalOutcome, checks: Mapping[str, bool], rationale: str) -> ConstitutionalReviewRecord:
        self._require_state(decision_id, DecisionState.UNDER_CONSTITUTIONAL_REVIEW)
        decision = self._decisions[decision_id]
        record = ConstitutionalReviewRecord(uuid4(), decision_id, decision.constitution_version, outcome, dict(checks), rationale)
        record.validate()
        self._constitutional_reviews.append(record)
        target = DecisionState.INVESTOR_OVERRIDE_PENDING if outcome is ConstitutionalOutcome.PASSED else DecisionState.READY_FOR_REVIEW
        self.transition(decision_id, target, actor_id="CONSTITUTIONAL_REVIEW", reason=rationale)
        return record

    def record_investor_decision(self, decision_id: UUID, *, investor_id: str, decision: InvestorDecision, reason: str, override_action: EnterpriseDecisionAction | None = None) -> InvestorDecisionRecord:
        self._require_state(decision_id, DecisionState.INVESTOR_OVERRIDE_PENDING)
        record = InvestorDecisionRecord(uuid4(), decision_id, investor_id, decision, reason, override_action)
        record.validate()
        self._investor_decisions.append(record)
        if decision is InvestorDecision.APPROVE:
            target = DecisionState.IMPLEMENTED
        elif decision is InvestorDecision.OVERRIDE:
            target = DecisionState.OVERRIDDEN_BY_INVESTOR
        else:
            target = DecisionState.ARCHIVED
        self.transition(decision_id, target, actor_id=investor_id, reason=reason)
        return record

    def snapshot(self, decision_id: UUID) -> DecisionGovernanceSnapshot:
        self._require_decision(decision_id)
        decision = self._decisions[decision_id]
        investor_records = tuple(item for item in self._investor_decisions if item.decision_id == decision_id)
        effective_action = decision.action
        for item in investor_records:
            if item.decision is InvestorDecision.OVERRIDE and item.override_action is not None:
                effective_action = item.override_action
        snapshot = DecisionGovernanceSnapshot(
            decision=decision,
            current_state=self._states[decision_id],
            committee_reviews=tuple(item for item in self._committee_reviews if item.decision_id == decision_id),
            constitutional_reviews=tuple(item for item in self._constitutional_reviews if item.decision_id == decision_id),
            investor_decisions=investor_records,
            events=tuple(item for item in self._events if item.decision_id == decision_id),
            effective_action=effective_action,
        )
        snapshot.validate()
        return snapshot

    @staticmethod
    def render_json(snapshot: DecisionGovernanceSnapshot) -> str:
        snapshot.validate()
        return JsonSerializer.dumps(snapshot)

    @staticmethod
    def render_markdown(snapshot: DecisionGovernanceSnapshot) -> str:
        snapshot.validate()
        lines = [
            "# Enterprise Decision Governance",
            "",
            f"- Decision ID: {snapshot.decision.identity.public_id}",
            f"- Original Action: {snapshot.decision.action.value}",
            f"- Effective Action: {snapshot.effective_action.value}",
            f"- Current State: {snapshot.current_state.value}",
            f"- Committee Reviews: {len(snapshot.committee_reviews)}",
            f"- Constitutional Reviews: {len(snapshot.constitutional_reviews)}",
            f"- Investor Decisions: {len(snapshot.investor_decisions)}",
            f"- Paper Trade Mode: {'YES' if snapshot.paper_trade_mode else 'NO'}",
            "",
            "## Governance Boundary",
            "",
            "Committees analyze and recommend; they do not vote or make the investment decision. The investor may approve, reject, or override with a preserved reason and audit trail.",
            "",
        ]
        return "\n".join(lines)

    def _require_decision(self, decision_id: UUID) -> None:
        if decision_id not in self._decisions:
            raise PlatformValidationError("decision is not registered for governance")

    def _require_state(self, decision_id: UUID, expected: DecisionState) -> None:
        self._require_decision(decision_id)
        actual = self._states[decision_id]
        if actual is not expected:
            raise PlatformValidationError(f"decision must be {expected.value}; current state is {actual.value}")
