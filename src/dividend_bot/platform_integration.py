"""Integrate existing Dividend Bot engines into the shared paper-only platform."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from importlib.util import find_spec
from typing import Any, Mapping

from .dividend_strategy_adapter import DividendEvaluationResult, DividendStrategyAdapter
from .platform_entities import MasterCompanyIntelligenceProfile
from .platform_foundation import PlatformValidationError, utc_now

MODULE_NAME = "platform_integration"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Strategy-neutral service registration, MCIP enrichment, and Dividend paper-cycle orchestration."


class ServiceDomain(str, Enum):
    DISCOVERY = "DISCOVERY"
    FUNDAMENTALS = "FUNDAMENTALS"
    GROWTH = "GROWTH"
    INCOME = "INCOME"
    FINANCIAL_HEALTH = "FINANCIAL_HEALTH"
    RISK = "RISK"
    TECHNICAL = "TECHNICAL"
    MARKET_INTELLIGENCE = "MARKET_INTELLIGENCE"
    EARNINGS = "EARNINGS"
    WATCHLIST = "WATCHLIST"
    PORTFOLIO = "PORTFOLIO"
    LEARNING = "LEARNING"
    GOVERNANCE = "GOVERNANCE"
    REPORTING = "REPORTING"


_MCIP_DOMAIN_FIELDS: dict[ServiceDomain, str] = {
    ServiceDomain.DISCOVERY: "discovery",
    ServiceDomain.FUNDAMENTALS: "fundamentals",
    ServiceDomain.GROWTH: "growth",
    ServiceDomain.INCOME: "income",
    ServiceDomain.FINANCIAL_HEALTH: "financial_health",
    ServiceDomain.RISK: "risk",
    ServiceDomain.TECHNICAL: "technical",
    ServiceDomain.MARKET_INTELLIGENCE: "market_intelligence",
    ServiceDomain.EARNINGS: "earnings",
    ServiceDomain.WATCHLIST: "watchlist_intelligence",
}


@dataclass(frozen=True)
class PlatformServiceDefinition:
    service_id: str
    domain: ServiceDomain
    module_name: str
    version: str = "legacy"
    required: bool = False
    strategy_neutral: bool = True

    def validate(self) -> None:
        if not self.service_id or self.service_id != self.service_id.upper():
            raise PlatformValidationError("service_id must be non-empty uppercase text")
        if not self.module_name.strip():
            raise PlatformValidationError("module_name must not be empty")
        if self.strategy_neutral is not True:
            raise PlatformValidationError("shared platform services must remain strategy-neutral")


@dataclass(frozen=True)
class ServiceAvailability:
    definition: PlatformServiceDefinition
    available: bool


class PlatformServiceRegistry:
    """Register existing modules without executing or rewriting them."""

    def __init__(self) -> None:
        self._services: dict[str, PlatformServiceDefinition] = {}

    def register(self, definition: PlatformServiceDefinition) -> None:
        definition.validate()
        existing = self._services.get(definition.service_id)
        if existing is not None and existing != definition:
            raise PlatformValidationError(f"conflicting service registration: {definition.service_id}")
        self._services[definition.service_id] = definition

    def get(self, service_id: str) -> PlatformServiceDefinition:
        try:
            return self._services[service_id]
        except KeyError as exc:
            raise PlatformValidationError(f"service is not registered: {service_id}") from exc

    def list_definitions(self) -> tuple[PlatformServiceDefinition, ...]:
        return tuple(self._services[key] for key in sorted(self._services))

    def availability(self) -> tuple[ServiceAvailability, ...]:
        results: list[ServiceAvailability] = []
        for definition in self.list_definitions():
            results.append(ServiceAvailability(definition, find_spec(definition.module_name) is not None))
        return tuple(results)

    def require_ready(self) -> None:
        missing = [
            item.definition.service_id
            for item in self.availability()
            if item.definition.required and not item.available
        ]
        if missing:
            raise PlatformValidationError(f"required platform services are unavailable: {', '.join(missing)}")


DEFAULT_PLATFORM_SERVICES: tuple[PlatformServiceDefinition, ...] = (
    PlatformServiceDefinition("DISCOVERY", ServiceDomain.DISCOVERY, "src.dividend_bot.candidate_discovery_engine"),
    PlatformServiceDefinition("MARKET_INTELLIGENCE", ServiceDomain.MARKET_INTELLIGENCE, "src.dividend_bot.market_intelligence_engine"),
    PlatformServiceDefinition("EARNINGS", ServiceDomain.EARNINGS, "src.dividend_bot.earnings_event_manager"),
    PlatformServiceDefinition("RISK", ServiceDomain.RISK, "src.dividend_bot.portfolio_risk_intelligence"),
    PlatformServiceDefinition("PORTFOLIO_LIFECYCLE", ServiceDomain.PORTFOLIO, "src.dividend_bot.portfolio_lifecycle_engine"),
    PlatformServiceDefinition("WEALTH_ATTRIBUTION", ServiceDomain.PORTFOLIO, "src.dividend_bot.wealth_attribution_engine"),
    PlatformServiceDefinition("RESEARCH", ServiceDomain.MARKET_INTELLIGENCE, "src.dividend_bot.research_intelligence_engine"),
    PlatformServiceDefinition("AI_CIO", ServiceDomain.GOVERNANCE, "src.dividend_bot.ai_cio_decision_engine"),
    PlatformServiceDefinition("LEARNING", ServiceDomain.LEARNING, "src.dividend_bot.ai_cio_learning_engine"),
)


def build_default_service_registry() -> PlatformServiceRegistry:
    registry = PlatformServiceRegistry()
    for definition in DEFAULT_PLATFORM_SERVICES:
        registry.register(definition)
    return registry


class MCIPIntegrationService:
    """Create immutable MCIP revisions from strategy-neutral engine outputs."""

    @staticmethod
    def apply_section(
        profile: MasterCompanyIntelligenceProfile,
        domain: ServiceDomain,
        values: Mapping[str, Any],
        *,
        quality_score: float | None = None,
    ) -> MasterCompanyIntelligenceProfile:
        profile.validate()
        if domain not in _MCIP_DOMAIN_FIELDS:
            raise PlatformValidationError(f"service domain does not map to MCIP: {domain.value}")
        if not isinstance(values, Mapping):
            raise PlatformValidationError("MCIP section values must be a mapping")

        field_name = _MCIP_DOMAIN_FIELDS[domain]
        merged = dict(getattr(profile, field_name))
        merged.update(dict(values))
        changes: dict[str, object] = {field_name: merged, "refreshed_at": utc_now()}
        if quality_score is not None:
            if not 0.0 <= float(quality_score) <= 100.0:
                raise PlatformValidationError("quality_score must be between 0 and 100")
            changes["quality_score"] = float(quality_score)
        revised = replace(profile, **changes)
        revised.validate()
        return revised

    @classmethod
    def apply_batch(
        cls,
        profile: MasterCompanyIntelligenceProfile,
        updates: Mapping[ServiceDomain, Mapping[str, Any]],
        *,
        quality_score: float | None = None,
    ) -> MasterCompanyIntelligenceProfile:
        revised = profile
        for domain, values in updates.items():
            revised = cls.apply_section(revised, domain, values)
        if quality_score is not None:
            revised = replace(revised, quality_score=float(quality_score), refreshed_at=utc_now())
            revised.validate()
        return revised


@dataclass(frozen=True)
class DividendPaperCycleResult:
    profile: MasterCompanyIntelligenceProfile
    dividend_result: DividendEvaluationResult
    completed_steps: tuple[str, ...]


class DividendPlatformPaperCycle:
    """Run the first integrated, non-executable Dividend platform cycle."""

    def __init__(self, adapter: DividendStrategyAdapter | None = None) -> None:
        self._adapter = adapter or DividendStrategyAdapter()

    def run(
        self,
        profile: MasterCompanyIntelligenceProfile,
        intelligence_updates: Mapping[ServiceDomain, Mapping[str, Any]],
        *,
        quality_score: float | None = None,
    ) -> DividendPaperCycleResult:
        updated = MCIPIntegrationService.apply_batch(
            profile,
            intelligence_updates,
            quality_score=quality_score,
        )
        result = self._adapter.evaluate(updated)
        return DividendPaperCycleResult(
            profile=updated,
            dividend_result=result,
            completed_steps=(
                "MCIP_UPDATE",
                "DIVIDEND_EVALUATION",
                "DIVIDEND_RECOMMENDATION",
                "PAPER_ONLY_COMPLETE",
            ),
        )
