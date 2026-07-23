"""Strategy-neutral Enterprise Intelligence Service for MCIP assembly and validation."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Mapping

from .platform_entities import MasterCompanyIntelligenceProfile
from .platform_foundation import JsonSerializer, PlatformValidationError, utc_now
from .platform_integration import MCIPIntegrationService, ServiceDomain

MODULE_NAME = "enterprise_intelligence_service"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Build and validate shared company intelligence without recommendations or capital actions."

_REQUIRED_SECTIONS = (
    "fundamentals",
    "income",
    "financial_health",
    "risk",
    "market_intelligence",
    "technical",
    "earnings",
)


@dataclass(frozen=True)
class IntelligenceContribution:
    service_id: str
    domain: ServiceDomain
    values: Mapping[str, Any]
    contributed_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        if not self.service_id or self.service_id != self.service_id.upper():
            raise PlatformValidationError("service_id must be non-empty uppercase text")
        if self.contributed_at.tzinfo is None:
            raise PlatformValidationError("contributed_at must be timezone-aware")
        if not isinstance(self.values, Mapping):
            raise PlatformValidationError("contribution values must be a mapping")


@dataclass(frozen=True)
class EnterpriseIntelligenceProfile:
    generated_at: datetime
    profile: MasterCompanyIntelligenceProfile
    completeness_score: float
    quality_score: float
    contributing_services: tuple[str, ...]
    missing_sections: tuple[str, ...]
    evidence_count: int
    warnings: tuple[str, ...] = ()
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if self.generated_at.tzinfo is None:
            raise PlatformValidationError("generated_at must be timezone-aware")
        self.profile.validate()
        if not 0.0 <= self.completeness_score <= 100.0:
            raise PlatformValidationError("completeness_score must be between 0 and 100")
        if not 0.0 <= self.quality_score <= 100.0:
            raise PlatformValidationError("quality_score must be between 0 and 100")
        if self.evidence_count < 0:
            raise PlatformValidationError("evidence_count must not be negative")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterpriseIntelligenceService:
    """Assemble immutable MCIP revisions from registered strategy-neutral contributions."""

    def build(
        self,
        profile: MasterCompanyIntelligenceProfile,
        contributions: tuple[IntelligenceContribution, ...],
        *,
        evidence_count: int | None = None,
        generated_at: datetime | None = None,
    ) -> EnterpriseIntelligenceProfile:
        profile.validate()
        if evidence_count is None:
            evidence_count = len(profile.evidence_ids)
        if evidence_count < 0:
            raise PlatformValidationError("evidence_count must not be negative")

        seen_domains: set[ServiceDomain] = set()
        updated = profile
        service_ids: list[str] = []
        for contribution in contributions:
            contribution.validate()
            if contribution.domain in seen_domains:
                raise PlatformValidationError(f"duplicate intelligence domain: {contribution.domain.value}")
            seen_domains.add(contribution.domain)
            updated = MCIPIntegrationService.apply_section(updated, contribution.domain, contribution.values)
            service_ids.append(contribution.service_id)

        populated = [name for name in _REQUIRED_SECTIONS if bool(getattr(updated, name))]
        missing = tuple(name for name in _REQUIRED_SECTIONS if name not in populated)
        completeness = round((len(populated) / len(_REQUIRED_SECTIONS)) * 100.0, 2)
        quality = float(updated.quality_score)
        warnings = tuple(f"Missing required intelligence section: {name}" for name in missing)
        if evidence_count == 0:
            warnings += ("No evidence is linked to the intelligence profile",)

        updated = replace(updated, refreshed_at=generated_at or utc_now())
        updated.validate()
        result = EnterpriseIntelligenceProfile(
            generated_at=generated_at or utc_now(),
            profile=updated,
            completeness_score=completeness,
            quality_score=quality,
            contributing_services=tuple(service_ids),
            missing_sections=missing,
            evidence_count=evidence_count,
            warnings=warnings,
        )
        result.validate()
        return result

    @staticmethod
    def render_json(result: EnterpriseIntelligenceProfile) -> str:
        result.validate()
        return JsonSerializer.dumps(result)

    @staticmethod
    def render_markdown(result: EnterpriseIntelligenceProfile) -> str:
        result.validate()
        lines = [
            "# Enterprise Intelligence Report",
            "",
            f"- Generated At: {JsonSerializer.to_primitive(result.generated_at)}",
            f"- Company ID: {result.profile.company_id}",
            f"- Profile ID: {result.profile.identity.internal_id}",
            f"- Overall Quality: {result.quality_score:.1f}",
            f"- Overall Completeness: {result.completeness_score:.1f}",
            f"- Evidence Count: {result.evidence_count}",
            f"- Paper Trade Mode: {'YES' if result.paper_trade_mode else 'NO'}",
            "",
            "## Available Intelligence",
            "",
        ]
        available = [name for name in _REQUIRED_SECTIONS if name not in result.missing_sections]
        lines.extend(f"- {name}" for name in available)
        lines.extend(["", "## Missing Intelligence", ""])
        lines.extend(f"- {name}" for name in result.missing_sections)
        lines.extend(["", "## Registered Services", ""])
        lines.extend(f"- {service_id}" for service_id in result.contributing_services)
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in result.warnings)
        lines.extend(["", "## Advisory Boundary", "", "This service does not create recommendations, allocate capital, or call broker APIs.", ""])
        return "\n".join(lines)
