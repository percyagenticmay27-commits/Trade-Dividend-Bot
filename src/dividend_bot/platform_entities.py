"""Canonical strategy-neutral business entities for the paper-only platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping
from uuid import UUID

from .platform_foundation import (
    IdentifierFactory,
    IdentifierKind,
    PlatformValidationError,
    utc_now,
)

MODULE_NAME = "platform_entities"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Canonical company, intelligence, strategy, portfolio, report, audit, and learning entities."


class CompanyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DELISTED = "DELISTED"
    MERGED = "MERGED"
    ARCHIVED = "ARCHIVED"


class DecisionState(str, Enum):
    DRAFT = "DRAFT"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    UNDER_COMMITTEE_COLLABORATION = "UNDER_COMMITTEE_COLLABORATION"
    UNDER_CONSTITUTIONAL_REVIEW = "UNDER_CONSTITUTIONAL_REVIEW"
    READY_FOR_CIO = "READY_FOR_CIO"
    INVESTOR_OVERRIDE_PENDING = "INVESTOR_OVERRIDE_PENDING"
    OVERRIDDEN_BY_INVESTOR = "OVERRIDDEN_BY_INVESTOR"
    SUPERSEDED = "SUPERSEDED"
    IMPLEMENTED = "IMPLEMENTED"
    ARCHIVED = "ARCHIVED"
    EXPIRED = "EXPIRED"


class PositionStatus(str, Enum):
    PROPOSED = "PROPOSED"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class FindingStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


@dataclass(frozen=True)
class EntityIdentity:
    internal_id: UUID
    public_id: str
    created_at: datetime

    def validate(self) -> None:
        if not self.public_id or self.public_id.count("-") != 2:
            raise PlatformValidationError("public_id must use PREFIX-YYYY-NNNNNN format")
        if self.created_at.tzinfo is None:
            raise PlatformValidationError("created_at must be timezone-aware")


def new_identity(kind: IdentifierKind | str) -> EntityIdentity:
    identity = EntityIdentity(
        internal_id=IdentifierFactory.new_internal_id(),
        public_id=IdentifierFactory.new_public_id(kind),
        created_at=utc_now(),
    )
    identity.validate()
    return identity


@dataclass(frozen=True)
class Company:
    identity: EntityIdentity
    symbol: str
    legal_name: str
    display_name: str
    exchange: str
    sector: str = ""
    industry: str = ""
    status: CompanyStatus = CompanyStatus.ACTIVE

    def validate(self) -> None:
        self.identity.validate()
        if not self.symbol or self.symbol != self.symbol.upper():
            raise PlatformValidationError("company symbol must be non-empty uppercase text")
        if not self.legal_name.strip() or not self.display_name.strip():
            raise PlatformValidationError("company names must not be empty")
        if not self.exchange.strip():
            raise PlatformValidationError("exchange must not be empty")


@dataclass(frozen=True)
class Asset:
    identity: EntityIdentity
    symbol: str
    instrument_type: str
    exchange: str
    currency: str = "USD"
    company_id: UUID | None = None
    underlying_symbol: str | None = None
    leverage_factor: float = 1.0
    active: bool = True

    def validate(self) -> None:
        self.identity.validate()
        if not self.symbol or self.symbol != self.symbol.upper():
            raise PlatformValidationError("asset symbol must be non-empty uppercase text")
        if self.leverage_factor <= 0:
            raise PlatformValidationError("leverage_factor must be greater than zero")


@dataclass(frozen=True)
class IntelligenceSnapshot:
    captured_at: datetime
    source_versions: Mapping[str, str] = field(default_factory=dict)
    values: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.captured_at.tzinfo is None:
            raise PlatformValidationError("captured_at must be timezone-aware")


@dataclass(frozen=True)
class MasterCompanyIntelligenceProfile:
    identity: EntityIdentity
    company_id: UUID
    discovery: Mapping[str, Any] = field(default_factory=dict)
    fundamentals: Mapping[str, Any] = field(default_factory=dict)
    growth: Mapping[str, Any] = field(default_factory=dict)
    income: Mapping[str, Any] = field(default_factory=dict)
    financial_health: Mapping[str, Any] = field(default_factory=dict)
    risk: Mapping[str, Any] = field(default_factory=dict)
    technical: Mapping[str, Any] = field(default_factory=dict)
    market_intelligence: Mapping[str, Any] = field(default_factory=dict)
    themes: tuple[str, ...] = ()
    earnings: Mapping[str, Any] = field(default_factory=dict)
    watchlist_intelligence: Mapping[str, Any] = field(default_factory=dict)
    evidence_ids: tuple[UUID, ...] = ()
    learning_ids: tuple[UUID, ...] = ()
    refreshed_at: datetime = field(default_factory=utc_now)
    quality_score: float = 0.0

    _FORBIDDEN_STRATEGY_KEYS = frozenset(
        {"strategy", "decision", "entry", "exit", "allocation", "recommendation"}
    )

    def validate(self) -> None:
        self.identity.validate()
        if self.refreshed_at.tzinfo is None:
            raise PlatformValidationError("refreshed_at must be timezone-aware")
        if not 0.0 <= self.quality_score <= 100.0:
            raise PlatformValidationError("quality_score must be between 0 and 100")
        for section_name in (
            "discovery",
            "fundamentals",
            "growth",
            "income",
            "financial_health",
            "risk",
            "technical",
            "market_intelligence",
            "earnings",
            "watchlist_intelligence",
        ):
            section = getattr(self, section_name)
            forbidden = self._FORBIDDEN_STRATEGY_KEYS.intersection(
                str(key).lower() for key in section.keys()
            )
            if forbidden:
                raise PlatformValidationError(
                    f"MCIP section {section_name} contains strategy-owned keys: {sorted(forbidden)}"
                )


@dataclass(frozen=True)
class EvidenceRecord:
    identity: EntityIdentity
    subject_type: str
    subject_id: UUID
    evidence_type: str
    source: str
    summary: str
    quality_score: float
    observed_at: datetime

    def validate(self) -> None:
        self.identity.validate()
        if not self.source.strip() or not self.summary.strip():
            raise PlatformValidationError("evidence source and summary must not be empty")
        if not 0.0 <= self.quality_score <= 100.0:
            raise PlatformValidationError("evidence quality_score must be between 0 and 100")
        if self.observed_at.tzinfo is None:
            raise PlatformValidationError("observed_at must be timezone-aware")


@dataclass(frozen=True)
class StrategyEvaluation:
    identity: EntityIdentity
    strategy_id: str
    company_id: UUID
    profile_id: UUID
    score: float
    rationale: str
    evaluated_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        self.identity.validate()
        if not self.strategy_id.strip():
            raise PlatformValidationError("strategy_id must not be empty")
        if not 0.0 <= self.score <= 100.0:
            raise PlatformValidationError("evaluation score must be between 0 and 100")
        if not self.rationale.strip():
            raise PlatformValidationError("evaluation rationale must not be empty")


@dataclass(frozen=True)
class StrategyRecommendation:
    identity: EntityIdentity
    strategy_id: str
    evaluation_id: UUID
    paper_action: str
    rationale: str
    confidence: float

    def validate(self) -> None:
        self.identity.validate()
        if not self.strategy_id.strip() or not self.paper_action.strip():
            raise PlatformValidationError("strategy_id and paper_action must not be empty")
        if not 0.0 <= self.confidence <= 100.0:
            raise PlatformValidationError("confidence must be between 0 and 100")


@dataclass(frozen=True)
class AICIODecision:
    identity: EntityIdentity
    strategy_id: str
    recommendation_id: UUID
    paper_action: str
    rationale: str
    confidence: float
    constitution_version: str
    state: DecisionState = DecisionState.DRAFT
    evidence_ids: tuple[UUID, ...] = ()
    supersedes_decision_id: UUID | None = None

    def validate(self) -> None:
        self.identity.validate()
        if not self.strategy_id.strip():
            raise PlatformValidationError("decision strategy_id must not be empty")
        if not self.paper_action.strip() or not self.rationale.strip():
            raise PlatformValidationError("decision action and rationale must not be empty")
        if not 0.0 <= self.confidence <= 100.0:
            raise PlatformValidationError("decision confidence must be between 0 and 100")
        if not self.constitution_version.strip():
            raise PlatformValidationError("constitution_version must not be empty")


@dataclass(frozen=True)
class Position:
    identity: EntityIdentity
    portfolio_id: UUID
    asset_id: UUID
    strategy_id: str
    quantity: float
    cost_basis: float
    current_value: float
    status: PositionStatus = PositionStatus.PROPOSED
    opened_at: datetime | None = None
    closed_at: datetime | None = None

    def validate(self) -> None:
        self.identity.validate()
        if not self.strategy_id.strip():
            raise PlatformValidationError("position strategy_id must not be empty")
        if self.quantity < 0 or self.cost_basis < 0 or self.current_value < 0:
            raise PlatformValidationError("position numeric values must not be negative")
        if self.status is PositionStatus.OPEN and self.opened_at is None:
            raise PlatformValidationError("open positions require opened_at")
        if self.status is PositionStatus.CLOSED and self.closed_at is None:
            raise PlatformValidationError("closed positions require closed_at")


@dataclass(frozen=True)
class ReportInstance:
    identity: EntityIdentity
    strategy_id: str
    report_type: str
    period_start: datetime
    period_end: datetime
    metrics: Mapping[str, Any] = field(default_factory=dict)
    decision_ids: tuple[UUID, ...] = ()
    output_paths: tuple[str, ...] = ()

    def validate(self) -> None:
        self.identity.validate()
        if not self.strategy_id.strip():
            raise PlatformValidationError("report strategy_id must not be empty")
        if self.period_start.tzinfo is None or self.period_end.tzinfo is None:
            raise PlatformValidationError("report periods must be timezone-aware")
        if self.period_end < self.period_start:
            raise PlatformValidationError("period_end must not precede period_start")


@dataclass(frozen=True)
class AuditFinding:
    check_name: str
    status: FindingStatus
    message: str

    def validate(self) -> None:
        if not self.check_name.strip() or not self.message.strip():
            raise PlatformValidationError("audit finding fields must not be empty")


@dataclass(frozen=True)
class AuditRun:
    identity: EntityIdentity
    scope_type: str
    scope_id: str
    strategy_id: str | None
    findings: tuple[AuditFinding, ...]
    completed_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        self.identity.validate()
        if not self.scope_type.strip() or not self.scope_id.strip():
            raise PlatformValidationError("audit scope must not be empty")
        if self.completed_at.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        for finding in self.findings:
            finding.validate()


@dataclass(frozen=True)
class LearningRecord:
    identity: EntityIdentity
    strategy_id: str | None
    subject_type: str
    subject_id: str
    lesson: str
    source_reference: str
    recorded_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        self.identity.validate()
        if not self.subject_type.strip() or not self.subject_id.strip():
            raise PlatformValidationError("learning subject must not be empty")
        if not self.lesson.strip() or not self.source_reference.strip():
            raise PlatformValidationError("learning content must not be empty")
