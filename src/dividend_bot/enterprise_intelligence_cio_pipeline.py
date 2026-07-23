"""Governed bridge from Enterprise Intelligence to the advisory AI CIO runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .enterprise_ai_cio_runtime import (
    EnterpriseAICIORuntime,
    EnterpriseCIOAdvisory,
    EnterpriseRecommendation,
)
from .enterprise_intelligence_service import EnterpriseIntelligenceProfile
from .platform_foundation import PlatformValidationError, utc_now

MODULE_NAME = "enterprise_intelligence_cio_pipeline"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Apply intelligence quality gates before Enterprise AI CIO advisory generation."


@dataclass(frozen=True)
class IntelligenceCIOPolicy:
    minimum_completeness_score: float = 70.0
    minimum_quality_score: float = 50.0
    minimum_evidence_count: int = 1

    def validate(self) -> None:
        if not 0.0 <= self.minimum_completeness_score <= 100.0:
            raise PlatformValidationError("minimum_completeness_score must be between 0 and 100")
        if not 0.0 <= self.minimum_quality_score <= 100.0:
            raise PlatformValidationError("minimum_quality_score must be between 0 and 100")
        if self.minimum_evidence_count < 0:
            raise PlatformValidationError("minimum_evidence_count must not be negative")


@dataclass(frozen=True)
class IntelligenceCIOPipelineResult:
    intelligence: EnterpriseIntelligenceProfile
    advisory: EnterpriseCIOAdvisory
    gates_passed: bool
    gate_failures: tuple[str, ...]
    completed_at: datetime
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        self.intelligence.validate()
        self.advisory.validate()
        if self.completed_at.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")
        if self.gates_passed == bool(self.gate_failures):
            raise PlatformValidationError("gates_passed must agree with gate_failures")
        if not self.gates_passed and self.advisory.recommendation is not EnterpriseRecommendation.REVIEW:
            raise PlatformValidationError("failed intelligence gates must produce REVIEW")


class EnterpriseIntelligenceCIOPipeline:
    """Require governed intelligence readiness before AI CIO advice is accepted."""

    def __init__(
        self,
        runtime: EnterpriseAICIORuntime | None = None,
        policy: IntelligenceCIOPolicy | None = None,
    ) -> None:
        self._runtime = runtime or EnterpriseAICIORuntime()
        self._policy = policy or IntelligenceCIOPolicy()
        self._policy.validate()
        self._history: list[IntelligenceCIOPipelineResult] = []

    def history(self) -> tuple[IntelligenceCIOPipelineResult, ...]:
        return tuple(self._history)

    def run(
        self,
        intelligence: EnterpriseIntelligenceProfile,
        *,
        proposed_recommendation: EnterpriseRecommendation | str,
        confidence: float,
        stability_checked: bool,
        rationale: str,
        completed_at: datetime | None = None,
    ) -> IntelligenceCIOPipelineResult:
        intelligence.validate()
        failures = self._gate_failures(intelligence)
        gates_passed = not failures

        recommendation = proposed_recommendation if gates_passed else EnterpriseRecommendation.REVIEW
        resolved_stability = stability_checked if gates_passed else False
        resolved_rationale = rationale
        if failures:
            resolved_rationale = "Review required because " + "; ".join(failures) + "."

        advisory = self._runtime.run(
            intelligence.profile,
            evidence_count=intelligence.evidence_count,
            proposed_recommendation=recommendation,
            confidence=confidence,
            stability_checked=resolved_stability,
            rationale=resolved_rationale,
            generated_at=completed_at,
        )
        result = IntelligenceCIOPipelineResult(
            intelligence=intelligence,
            advisory=advisory,
            gates_passed=gates_passed,
            gate_failures=failures,
            completed_at=completed_at or utc_now(),
        )
        result.validate()
        self._history.append(result)
        return result

    def _gate_failures(self, intelligence: EnterpriseIntelligenceProfile) -> tuple[str, ...]:
        failures: list[str] = []
        if intelligence.completeness_score < self._policy.minimum_completeness_score:
            failures.append(
                f"intelligence completeness {intelligence.completeness_score:.1f} is below "
                f"{self._policy.minimum_completeness_score:.1f}"
            )
        if intelligence.quality_score < self._policy.minimum_quality_score:
            failures.append(
                f"intelligence quality {intelligence.quality_score:.1f} is below "
                f"{self._policy.minimum_quality_score:.1f}"
            )
        if intelligence.evidence_count < self._policy.minimum_evidence_count:
            failures.append(
                f"evidence count {intelligence.evidence_count} is below "
                f"{self._policy.minimum_evidence_count}"
            )
        return tuple(failures)
