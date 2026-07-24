"""Deterministic orchestration for the paper-only enterprise investment workflow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from typing import Any

from .enterprise_ai_cio_runtime import EnterpriseRecommendation
from .enterprise_decision_engine import EnterpriseDecision, EnterpriseDecisionEngine, StrategyAdvisory
from .enterprise_intelligence_cio_pipeline import EnterpriseIntelligenceCIOPipeline, IntelligenceCIOPipelineResult
from .enterprise_intelligence_service import EnterpriseIntelligenceProfile, EnterpriseIntelligenceService, IntelligenceContribution
from .platform_entities import MasterCompanyIntelligenceProfile
from .platform_foundation import JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_workflow_orchestrator"
MODULE_VERSION = "1.0.1"
MODULE_DESCRIPTION = "Coordinate intelligence, AI CIO advisory, and canonical decision preparation."


@dataclass(frozen=True)
class EnterpriseWorkflowRequest:
    profile: MasterCompanyIntelligenceProfile
    contributions: tuple[IntelligenceContribution, ...]
    strategy_advisories: tuple[StrategyAdvisory, ...]
    proposed_recommendation: EnterpriseRecommendation | str
    confidence: float
    stability_checked: bool
    rationale: str
    evidence_count: int | None = None
    constitution_version: str = "1.0.0"
    requested_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        self.profile.validate()
        if not self.strategy_advisories:
            raise PlatformValidationError("workflow requires at least one strategy advisory")
        for advisory in self.strategy_advisories:
            advisory.validate()
        if not 0.0 <= float(self.confidence) <= 100.0:
            raise PlatformValidationError("workflow confidence must be between 0 and 100")
        if self.evidence_count is not None and self.evidence_count < 0:
            raise PlatformValidationError("evidence_count must not be negative")
        if not self.rationale.strip() or not self.constitution_version.strip():
            raise PlatformValidationError("workflow rationale and constitution_version are required")
        if self.requested_at.tzinfo is None:
            raise PlatformValidationError("requested_at must be timezone-aware")


@dataclass(frozen=True)
class EnterpriseWorkflowResult:
    workflow_id: str
    intelligence: EnterpriseIntelligenceProfile
    pipeline: IntelligenceCIOPipelineResult
    decision: EnterpriseDecision
    completed_stages: tuple[str, ...]
    completed_at: datetime = field(default_factory=utc_now)
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if not self.workflow_id.strip():
            raise PlatformValidationError("workflow_id is required")
        self.intelligence.validate()
        self.pipeline.validate()
        self.decision.validate()
        if self.pipeline.intelligence.profile.identity.internal_id != self.intelligence.profile.identity.internal_id:
            raise PlatformValidationError("pipeline must preserve orchestrated intelligence profile")
        if self.decision.profile_id != self.intelligence.profile.identity.internal_id:
            raise PlatformValidationError("decision must reference orchestrated intelligence profile")
        if self.completed_stages != ("INTELLIGENCE", "AI_CIO_ADVISORY", "ENTERPRISE_DECISION"):
            raise PlatformValidationError("workflow stages are incomplete or out of order")
        if self.completed_at.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterpriseWorkflowOrchestrator:
    def __init__(self, intelligence_service=None, cio_pipeline=None, decision_engine=None) -> None:
        self._intelligence_service = intelligence_service or EnterpriseIntelligenceService()
        self._cio_pipeline = cio_pipeline or EnterpriseIntelligenceCIOPipeline()
        self._decision_engine = decision_engine or EnterpriseDecisionEngine()
        self._history: list[EnterpriseWorkflowResult] = []

    @property
    def decision_engine(self) -> EnterpriseDecisionEngine:
        return self._decision_engine

    def history(self) -> tuple[EnterpriseWorkflowResult, ...]:
        return tuple(self._history)

    def prepare_for_investor_review(self, request: EnterpriseWorkflowRequest, *, completed_at: datetime | None = None) -> EnterpriseWorkflowResult:
        request.validate()
        timestamp = completed_at or utc_now()
        if timestamp.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        intelligence = self._intelligence_service.build(request.profile, request.contributions, evidence_count=request.evidence_count, generated_at=timestamp)
        pipeline = self._cio_pipeline.run(
            intelligence,
            proposed_recommendation=request.proposed_recommendation,
            confidence=request.confidence,
            stability_checked=request.stability_checked,
            rationale=request.rationale,
            completed_at=timestamp,
        )
        decision = self._decision_engine.create_decision(
            pipeline,
            request.strategy_advisories,
            constitution_version=request.constitution_version,
            created_at=timestamp,
        )
        result = EnterpriseWorkflowResult(
            workflow_id=f"WF-{decision.identity.public_id}",
            intelligence=intelligence,
            pipeline=pipeline,
            decision=decision,
            completed_stages=("INTELLIGENCE", "AI_CIO_ADVISORY", "ENTERPRISE_DECISION"),
            completed_at=timestamp,
        )
        result.validate()
        self._history.append(result)
        return result

    @staticmethod
    def render_json(result: EnterpriseWorkflowResult) -> str:
        result.validate()
        return JsonSerializer.dumps(_safe_primitive(result))

    @staticmethod
    def render_markdown(result: EnterpriseWorkflowResult) -> str:
        result.validate()
        return "\n".join([
            "# Enterprise Workflow Orchestration", "",
            f"- Workflow ID: {result.workflow_id}",
            f"- Decision ID: {result.decision.identity.public_id}",
            f"- Decision Action: {result.decision.action.value}",
            f"- Decision State: {result.decision.state.value}",
            f"- Intelligence Completeness: {result.intelligence.completeness_score:.1f}",
            f"- Intelligence Quality: {result.intelligence.quality_score:.1f}",
            f"- Evidence Count: {result.intelligence.evidence_count}",
            f"- Completed Stages: {', '.join(result.completed_stages)}",
            f"- Paper Trade Mode: {'YES' if result.paper_trade_mode else 'NO'}", "",
            "## Investor Boundary", "",
            "This workflow stops after canonical decision preparation. Investor approval, capital assignment, portfolio mutation, and broker execution are not performed.", "",
        ])


def _safe_primitive(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _safe_primitive(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _safe_primitive(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_safe_primitive(item) for item in value]
    return value
