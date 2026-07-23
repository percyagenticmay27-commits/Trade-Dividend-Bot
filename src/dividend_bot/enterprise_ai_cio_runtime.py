"""Enterprise AI CIO runtime for advisory, paper-only decisions.

This module coordinates shared company intelligence, evidence readiness, decision
stability, and existing AI CIO service availability. It never allocates capital,
creates orders, or calls broker APIs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from importlib.util import find_spec
from types import MappingProxyType
from typing import Mapping

from .platform_entities import MasterCompanyIntelligenceProfile
from .platform_foundation import JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_ai_cio_runtime"
MODULE_VERSION = "1.0.1"
MODULE_DESCRIPTION = "Strategy-neutral Enterprise AI CIO advisory runtime."


class EnterpriseRecommendation(str, Enum):
    BUY = "BUY"
    HOLD = "HOLD"
    WATCH = "WATCH"
    REVIEW = "REVIEW"
    DO_NOT_BUY = "DO_NOT_BUY"


class ServiceStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class RuntimeServiceState:
    service_id: str
    module_name: str
    status: ServiceStatus


@dataclass(frozen=True)
class EnterpriseCIOAdvisory:
    generated_at: datetime
    company_id: str
    profile_id: str
    recommendation: EnterpriseRecommendation
    confidence: float
    rationale: str
    stability_checked: bool
    evidence_present: bool
    services: tuple[RuntimeServiceState, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if self.generated_at.tzinfo is None:
            raise PlatformValidationError("generated_at must be timezone-aware")
        if not self.company_id or not self.profile_id:
            raise PlatformValidationError("company_id and profile_id are required")
        if not 0.0 <= float(self.confidence) <= 100.0:
            raise PlatformValidationError("confidence must be between 0 and 100")
        if not self.rationale.strip():
            raise PlatformValidationError("rationale must not be empty")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")
        if not self.services:
            raise PlatformValidationError("runtime must report service status")


_DEFAULT_SERVICES: tuple[tuple[str, str], ...] = (
    ("AI_CIO_DECISION", "src.dividend_bot.ai_cio_decision_engine"),
    ("AI_CIO_EVIDENCE", "src.dividend_bot.ai_cio_evidence_registry"),
    ("AI_CIO_LEARNING", "src.dividend_bot.ai_cio_learning_engine"),
    ("DECISION_STABILITY", "src.dividend_bot.decision_stability_engine"),
    ("AI_CIO_DASHBOARD", "src.dividend_bot.ai_cio_executive_dashboard"),
)


class EnterpriseAICIORuntime:
    """Build immutable advisory decisions from MCIP and evidence readiness."""

    def __init__(self) -> None:
        self._history: list[EnterpriseCIOAdvisory] = []

    def history(self) -> tuple[EnterpriseCIOAdvisory, ...]:
        return tuple(self._history)

    def discover_services(self) -> tuple[RuntimeServiceState, ...]:
        states: list[RuntimeServiceState] = []
        for service_id, module_name in _DEFAULT_SERVICES:
            try:
                available = find_spec(module_name) is not None
                status = ServiceStatus.AVAILABLE if available else ServiceStatus.UNAVAILABLE
            except Exception:
                status = ServiceStatus.ERROR
            states.append(RuntimeServiceState(service_id, module_name, status))
        return tuple(states)

    def run(
        self,
        profile: MasterCompanyIntelligenceProfile,
        *,
        evidence_count: int,
        proposed_recommendation: EnterpriseRecommendation | str,
        confidence: float,
        stability_checked: bool,
        rationale: str,
        generated_at: datetime | None = None,
    ) -> EnterpriseCIOAdvisory:
        profile.validate()
        if evidence_count < 0:
            raise PlatformValidationError("evidence_count must not be negative")
        if isinstance(proposed_recommendation, str):
            try:
                proposed_recommendation = EnterpriseRecommendation(proposed_recommendation.upper())
            except ValueError as exc:
                raise PlatformValidationError("unsupported Enterprise CIO recommendation") from exc

        evidence_present = evidence_count > 0
        services = self.discover_services()
        recommendation = proposed_recommendation
        resolved_rationale = rationale
        resolved_confidence = float(confidence)

        if not evidence_present or not stability_checked:
            recommendation = EnterpriseRecommendation.REVIEW
            resolved_confidence = min(resolved_confidence, 50.0)
            reasons: list[str] = []
            if not evidence_present:
                reasons.append("evidence is missing")
            if not stability_checked:
                reasons.append("decision stability was not evaluated")
            resolved_rationale = f"Review required because {' and '.join(reasons)}."

        advisory = EnterpriseCIOAdvisory(
            generated_at=generated_at or utc_now(),
            company_id=profile.company_id,
            profile_id=str(profile.identity.internal_id),
            recommendation=recommendation,
            confidence=resolved_confidence,
            rationale=resolved_rationale,
            stability_checked=stability_checked,
            evidence_present=evidence_present,
            services=services,
            metadata=MappingProxyType(
                {
                    "runtime_version": MODULE_VERSION,
                    "constitution_version": "1.0.0",
                    "profile_quality_score": profile.quality_score,
                    "evidence_count": evidence_count,
                }
            ),
        )
        advisory.validate()
        self._history.append(advisory)
        return advisory

    @staticmethod
    def render_json(advisory: EnterpriseCIOAdvisory) -> str:
        """Render without asking dataclasses.asdict to deepcopy MappingProxyType."""
        advisory.validate()
        payload = {
            "generated_at": advisory.generated_at,
            "company_id": advisory.company_id,
            "profile_id": advisory.profile_id,
            "recommendation": advisory.recommendation,
            "confidence": advisory.confidence,
            "rationale": advisory.rationale,
            "stability_checked": advisory.stability_checked,
            "evidence_present": advisory.evidence_present,
            "services": [
                {
                    "service_id": state.service_id,
                    "module_name": state.module_name,
                    "status": state.status,
                }
                for state in advisory.services
            ],
            "metadata": dict(advisory.metadata),
            "paper_trade_mode": advisory.paper_trade_mode,
            "live_trading_enabled": advisory.live_trading_enabled,
            "broker_execution_enabled": advisory.broker_execution_enabled,
        }
        return JsonSerializer.dumps(payload)

    @staticmethod
    def render_markdown(advisory: EnterpriseCIOAdvisory) -> str:
        advisory.validate()
        lines = [
            "# Enterprise AI CIO Runtime",
            "",
            f"- Generated At: {JsonSerializer.to_primitive(advisory.generated_at)}",
            f"- Company ID: {advisory.company_id}",
            f"- Profile ID: {advisory.profile_id}",
            f"- Recommendation: {advisory.recommendation.value}",
            f"- Confidence: {advisory.confidence:.1f}",
            f"- Evidence Present: {'YES' if advisory.evidence_present else 'NO'}",
            f"- Stability Checked: {'YES' if advisory.stability_checked else 'NO'}",
            f"- Paper Trade Mode: {'YES' if advisory.paper_trade_mode else 'NO'}",
            "",
            "## Rationale",
            "",
            advisory.rationale,
            "",
            "## Services",
            "",
        ]
        lines.extend(f"- {state.service_id}: {state.status.value}" for state in advisory.services)
        lines.extend(
            [
                "",
                "## Advisory Boundary",
                "",
                "This runtime does not assign capital, place orders, or call broker APIs.",
                "",
            ]
        )
        return "\n".join(lines)
