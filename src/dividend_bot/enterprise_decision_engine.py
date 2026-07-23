"""Governed, strategy-neutral Enterprise Decision Engine.

Strategies submit advisory records.  Only this engine creates canonical enterprise
investment decisions.  Decisions are immutable, append-only, paper-only, and never
create broker or order requests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping
from uuid import UUID

from .enterprise_ai_cio_runtime import EnterpriseRecommendation
from .enterprise_intelligence_cio_pipeline import IntelligenceCIOPipelineResult
from .platform_entities import DecisionState, EntityIdentity, new_identity
from .platform_foundation import JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_decision_engine"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Canonical governed enterprise investment decisions from strategy advisories."


class EnterpriseDecisionAction(str, Enum):
    BUY = "BUY"
    ACCUMULATE = "ACCUMULATE"
    ADD = "ADD"
    HOLD = "HOLD"
    WATCH = "WATCH"
    REVIEW = "REVIEW"
    SELL = "SELL"
    EXIT = "EXIT"
    DO_NOT_BUY = "DO_NOT_BUY"


_ADVISORY_TO_DECISION = {
    EnterpriseRecommendation.BUY: EnterpriseDecisionAction.BUY,
    EnterpriseRecommendation.HOLD: EnterpriseDecisionAction.HOLD,
    EnterpriseRecommendation.WATCH: EnterpriseDecisionAction.WATCH,
    EnterpriseRecommendation.REVIEW: EnterpriseDecisionAction.REVIEW,
    EnterpriseRecommendation.DO_NOT_BUY: EnterpriseDecisionAction.DO_NOT_BUY,
}


@dataclass(frozen=True)
class StrategyAdvisory:
    strategy_id: str
    action: EnterpriseDecisionAction | str
    confidence: float
    opportunity_quality: float
    rationale: str
    service_id: str
    advisory_id: UUID | None = None
    generated_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        if not self.strategy_id or self.strategy_id != self.strategy_id.upper():
            raise PlatformValidationError("strategy_id must be non-empty uppercase text")
        if not self.service_id or self.service_id != self.service_id.upper():
            raise PlatformValidationError("service_id must be non-empty uppercase text")
        if isinstance(self.action, str):
            try:
                EnterpriseDecisionAction(self.action.upper())
            except ValueError as exc:
                raise PlatformValidationError("unsupported strategy advisory action") from exc
        if not 0.0 <= float(self.confidence) <= 100.0:
            raise PlatformValidationError("advisory confidence must be between 0 and 100")
        if not 0.0 <= float(self.opportunity_quality) <= 100.0:
            raise PlatformValidationError("opportunity_quality must be between 0 and 100")
        if not self.rationale.strip():
            raise PlatformValidationError("advisory rationale must not be empty")
        if self.generated_at.tzinfo is None:
            raise PlatformValidationError("advisory timestamp must be timezone-aware")

    def resolved_action(self) -> EnterpriseDecisionAction:
        self.validate()
        return self.action if isinstance(self.action, EnterpriseDecisionAction) else EnterpriseDecisionAction(self.action.upper())


@dataclass(frozen=True)
class EnterpriseDecision:
    identity: EntityIdentity
    company_id: UUID
    profile_id: UUID
    action: EnterpriseDecisionAction
    confidence: float
    opportunity_quality: float
    rationale: str
    strategy_advisories: tuple[StrategyAdvisory, ...]
    evidence_count: int
    intelligence_completeness: float
    intelligence_quality: float
    stability_checked: bool
    constitution_version: str
    state: DecisionState = DecisionState.READY_FOR_REVIEW
    created_at: datetime = field(default_factory=utc_now)
    supersedes_decision_id: UUID | None = None
    learning_record_id: UUID | None = None
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        self.identity.validate()
        if self.created_at.tzinfo is None:
            raise PlatformValidationError("decision timestamp must be timezone-aware")
        if not self.strategy_advisories:
            raise PlatformValidationError("enterprise decision requires at least one strategy advisory")
        for advisory in self.strategy_advisories:
            advisory.validate()
        if not 0.0 <= self.confidence <= 100.0:
            raise PlatformValidationError("decision confidence must be between 0 and 100")
        if not 0.0 <= self.opportunity_quality <= 100.0:
            raise PlatformValidationError("decision opportunity_quality must be between 0 and 100")
        if not 0.0 <= self.intelligence_completeness <= 100.0:
            raise PlatformValidationError("intelligence_completeness must be between 0 and 100")
        if not 0.0 <= self.intelligence_quality <= 100.0:
            raise PlatformValidationError("intelligence_quality must be between 0 and 100")
        if self.evidence_count < 0:
            raise PlatformValidationError("evidence_count must not be negative")
        if not self.rationale.strip() or not self.constitution_version.strip():
            raise PlatformValidationError("decision rationale and constitution_version are required")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")
        if self.action is not EnterpriseDecisionAction.REVIEW and not self.stability_checked:
            raise PlatformValidationError("non-REVIEW decisions require stability evaluation")


class EnterpriseDecisionLedger:
    """Append-only immutable enterprise decision history."""

    def __init__(self) -> None:
        self._decisions: list[EnterpriseDecision] = []
        self._ids: set[UUID] = set()

    def append(self, decision: EnterpriseDecision) -> None:
        decision.validate()
        if decision.identity.internal_id in self._ids:
            raise PlatformValidationError("enterprise decision already exists in ledger")
        self._decisions.append(decision)
        self._ids.add(decision.identity.internal_id)

    def all(self) -> tuple[EnterpriseDecision, ...]:
        return tuple(self._decisions)

    def for_company(self, company_id: UUID) -> tuple[EnterpriseDecision, ...]:
        return tuple(item for item in self._decisions if item.company_id == company_id)

    def latest_for_company(self, company_id: UUID) -> EnterpriseDecision | None:
        matches = self.for_company(company_id)
        return matches[-1] if matches else None


class EnterpriseDecisionEngine:
    """Create the platform's only canonical investment decision records."""

    def __init__(self, ledger: EnterpriseDecisionLedger | None = None) -> None:
        self._ledger = ledger or EnterpriseDecisionLedger()

    @property
    def ledger(self) -> EnterpriseDecisionLedger:
        return self._ledger

    def create_decision(
        self,
        pipeline_result: IntelligenceCIOPipelineResult,
        advisories: tuple[StrategyAdvisory, ...],
        *,
        constitution_version: str = "1.0.0",
        created_at: datetime | None = None,
    ) -> EnterpriseDecision:
        pipeline_result.validate()
        if not advisories:
            raise PlatformValidationError("at least one strategy advisory is required")
        for advisory in advisories:
            advisory.validate()

        advisory = pipeline_result.advisory
        action = _ADVISORY_TO_DECISION[advisory.recommendation]
        confidence = float(advisory.confidence)
        opportunity_quality = round(sum(float(item.opportunity_quality) for item in advisories) / len(advisories), 2)
        rationale = advisory.rationale
        state = DecisionState.READY_FOR_CIO

        if not pipeline_result.gates_passed or not advisory.stability_checked:
            action = EnterpriseDecisionAction.REVIEW
            confidence = min(confidence, 50.0)
            state = DecisionState.READY_FOR_REVIEW
            rationale = "Governance review required. " + advisory.rationale

        previous = self._ledger.latest_for_company(pipeline_result.intelligence.profile.company_id)
        decision = EnterpriseDecision(
            identity=new_identity("DEC"),
            company_id=pipeline_result.intelligence.profile.company_id,
            profile_id=pipeline_result.intelligence.profile.identity.internal_id,
            action=action,
            confidence=confidence,
            opportunity_quality=opportunity_quality,
            rationale=rationale,
            strategy_advisories=tuple(advisories),
            evidence_count=pipeline_result.intelligence.evidence_count,
            intelligence_completeness=pipeline_result.intelligence.completeness_score,
            intelligence_quality=pipeline_result.intelligence.quality_score,
            stability_checked=advisory.stability_checked,
            constitution_version=constitution_version,
            state=state,
            created_at=created_at or utc_now(),
            supersedes_decision_id=previous.identity.internal_id if previous else None,
        )
        decision.validate()
        self._ledger.append(decision)
        return decision

    @staticmethod
    def render_json(decision: EnterpriseDecision) -> str:
        decision.validate()
        return JsonSerializer.dumps(decision)

    @staticmethod
    def render_markdown(decision: EnterpriseDecision) -> str:
        decision.validate()
        lines = [
            "# Enterprise AI CIO Decision",
            "",
            f"- Decision ID: {decision.identity.public_id}",
            f"- Company ID: {decision.company_id}",
            f"- Profile ID: {decision.profile_id}",
            f"- Action: {decision.action.value}",
            f"- Confidence: {decision.confidence:.1f}",
            f"- Opportunity Quality: {decision.opportunity_quality:.1f}",
            f"- Lifecycle State: {decision.state.value}",
            f"- Evidence Count: {decision.evidence_count}",
            f"- Intelligence Completeness: {decision.intelligence_completeness:.1f}",
            f"- Intelligence Quality: {decision.intelligence_quality:.1f}",
            f"- Stability Checked: {'YES' if decision.stability_checked else 'NO'}",
            f"- Constitution Version: {decision.constitution_version}",
            f"- Investor Status: PENDING",
            f"- Paper Trade Mode: {'YES' if decision.paper_trade_mode else 'NO'}",
            "",
            "## Decision Rationale",
            "",
            decision.rationale,
            "",
            "## Strategy Advisories",
            "",
        ]
        for advisory in decision.strategy_advisories:
            lines.append(
                f"- {advisory.strategy_id}: {advisory.resolved_action().value} | "
                f"Confidence {advisory.confidence:.1f} | Quality {advisory.opportunity_quality:.1f} | "
                f"Service {advisory.service_id}"
            )
        lines.extend(
            [
                "",
                "## Execution Boundary",
                "",
                "This governed decision does not allocate capital, place orders, or call broker APIs.",
                "",
            ]
        )
        return "\n".join(lines)
