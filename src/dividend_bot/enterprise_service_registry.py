"""Governed dependency registry for shared enterprise platform services.

The registry constructs and exposes platform services in dependency order without
executing workflows. It preserves singleton identity for shared platform services,
prevents conflicting registrations, and keeps strategy-scoped services isolated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from .enterprise_daily_cycle import EnterpriseDailyCycle
from .enterprise_decision_engine import EnterpriseDecisionEngine
from .enterprise_intelligence_cio_pipeline import EnterpriseIntelligenceCIOPipeline
from .enterprise_intelligence_service import EnterpriseIntelligenceService
from .enterprise_workflow_orchestrator import EnterpriseWorkflowOrchestrator
from .platform_foundation import JsonSerializer, PlatformValidationError

MODULE_NAME = "enterprise_service_registry"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Register, validate, and construct shared enterprise services in dependency order."


class ServiceScope(str, Enum):
    PLATFORM = "PLATFORM"
    STRATEGY = "STRATEGY"


@dataclass(frozen=True)
class ServiceRegistration:
    service_id: str
    instance: object
    dependencies: tuple[str, ...] = ()
    scope: ServiceScope = ServiceScope.PLATFORM
    strategy_id: str | None = None

    def validate(self) -> None:
        if not self.service_id or self.service_id != self.service_id.upper():
            raise PlatformValidationError("service_id must be non-empty uppercase text")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise PlatformValidationError("service dependencies must not contain duplicates")
        if self.service_id in self.dependencies:
            raise PlatformValidationError("service must not depend on itself")
        if any(not item or item != item.upper() for item in self.dependencies):
            raise PlatformValidationError("dependency identifiers must be non-empty uppercase text")
        if self.scope is ServiceScope.STRATEGY:
            if not self.strategy_id or self.strategy_id != self.strategy_id.upper():
                raise PlatformValidationError("strategy-scoped services require an uppercase strategy_id")
        elif self.strategy_id is not None:
            raise PlatformValidationError("platform-scoped services must not declare strategy_id")


class EnterpriseServiceRegistry:
    """Mutable-until-frozen registry with deterministic dependency resolution."""

    def __init__(self) -> None:
        self._registrations: dict[str, ServiceRegistration] = {}
        self._frozen = False

    @property
    def frozen(self) -> bool:
        return self._frozen

    def register(self, registration: ServiceRegistration) -> None:
        if self._frozen:
            raise PlatformValidationError("service registry is frozen")
        registration.validate()
        existing = self._registrations.get(registration.service_id)
        if existing is not None:
            if existing != registration:
                raise PlatformValidationError(f"conflicting service registration: {registration.service_id}")
            return
        self._registrations[registration.service_id] = registration

    def freeze(self) -> None:
        self._validate_dependencies()
        self.ordered_service_ids()
        self._frozen = True

    def resolve(self, service_id: str) -> object:
        key = service_id.upper()
        try:
            return self._registrations[key].instance
        except KeyError as exc:
            raise PlatformValidationError(f"service is not registered: {key}") from exc

    def registration(self, service_id: str) -> ServiceRegistration:
        key = service_id.upper()
        try:
            return self._registrations[key]
        except KeyError as exc:
            raise PlatformValidationError(f"service is not registered: {key}") from exc

    def registrations(self) -> tuple[ServiceRegistration, ...]:
        return tuple(self._registrations[key] for key in sorted(self._registrations))

    def for_strategy(self, strategy_id: str) -> tuple[ServiceRegistration, ...]:
        key = strategy_id.upper()
        return tuple(
            item
            for item in self.registrations()
            if item.scope is ServiceScope.STRATEGY and item.strategy_id == key
        )

    def ordered_service_ids(self) -> tuple[str, ...]:
        self._validate_dependencies()
        temporary: set[str] = set()
        permanent: set[str] = set()
        ordered: list[str] = []

        def visit(service_id: str) -> None:
            if service_id in permanent:
                return
            if service_id in temporary:
                raise PlatformValidationError("cyclic service dependency detected")
            temporary.add(service_id)
            for dependency in self._registrations[service_id].dependencies:
                visit(dependency)
            temporary.remove(service_id)
            permanent.add(service_id)
            ordered.append(service_id)

        for service_id in sorted(self._registrations):
            visit(service_id)
        return tuple(ordered)

    def _validate_dependencies(self) -> None:
        for registration in self._registrations.values():
            missing = [item for item in registration.dependencies if item not in self._registrations]
            if missing:
                raise PlatformValidationError(
                    f"service {registration.service_id} has missing dependencies: {', '.join(missing)}"
                )

    def render_json(self) -> str:
        payload = {
            "module_name": MODULE_NAME,
            "module_version": MODULE_VERSION,
            "frozen": self._frozen,
            "ordered_service_ids": self.ordered_service_ids(),
            "services": [
                {
                    "service_id": item.service_id,
                    "dependencies": item.dependencies,
                    "scope": item.scope,
                    "strategy_id": item.strategy_id,
                    "instance_type": type(item.instance).__name__,
                }
                for item in self.registrations()
            ],
            "paper_trade_mode": True,
            "live_trading_enabled": False,
            "broker_execution_enabled": False,
        }
        return JsonSerializer.dumps(payload)

    def render_markdown(self) -> str:
        lines = [
            "# Enterprise Service Dependency Registry",
            "",
            f"- Module Version: {MODULE_VERSION}",
            f"- Frozen: {'YES' if self._frozen else 'NO'}",
            f"- Service Count: {len(self._registrations)}",
            "- Paper Trade Mode: YES",
            "",
            "## Dependency Order",
            "",
        ]
        for index, service_id in enumerate(self.ordered_service_ids(), start=1):
            registration = self._registrations[service_id]
            dependencies = ", ".join(registration.dependencies) or "NONE"
            scope = registration.scope.value
            if registration.strategy_id:
                scope += f" ({registration.strategy_id})"
            lines.append(f"{index}. {service_id} | Dependencies: {dependencies} | Scope: {scope}")
        lines.extend(
            [
                "",
                "## Execution Boundary",
                "",
                "This registry constructs services only. It does not run workflows, approve decisions, allocate capital, mutate portfolios, or call broker APIs.",
                "",
            ]
        )
        return "\n".join(lines)


@dataclass(frozen=True)
class EnterpriseServiceContainer:
    registry: EnterpriseServiceRegistry
    intelligence_service: EnterpriseIntelligenceService
    cio_pipeline: EnterpriseIntelligenceCIOPipeline
    decision_engine: EnterpriseDecisionEngine
    workflow_orchestrator: EnterpriseWorkflowOrchestrator
    daily_cycle: EnterpriseDailyCycle

    @classmethod
    def build_default(cls) -> "EnterpriseServiceContainer":
        registry = EnterpriseServiceRegistry()
        intelligence_service = EnterpriseIntelligenceService()
        cio_pipeline = EnterpriseIntelligenceCIOPipeline()
        decision_engine = EnterpriseDecisionEngine()
        workflow_orchestrator = EnterpriseWorkflowOrchestrator(
            intelligence_service=intelligence_service,
            cio_pipeline=cio_pipeline,
            decision_engine=decision_engine,
        )
        daily_cycle = EnterpriseDailyCycle(orchestrator=workflow_orchestrator)

        registrations: Iterable[ServiceRegistration] = (
            ServiceRegistration("ENTERPRISE_INTELLIGENCE_SERVICE", intelligence_service),
            ServiceRegistration("ENTERPRISE_CIO_PIPELINE", cio_pipeline),
            ServiceRegistration("ENTERPRISE_DECISION_ENGINE", decision_engine),
            ServiceRegistration(
                "ENTERPRISE_WORKFLOW_ORCHESTRATOR",
                workflow_orchestrator,
                dependencies=(
                    "ENTERPRISE_INTELLIGENCE_SERVICE",
                    "ENTERPRISE_CIO_PIPELINE",
                    "ENTERPRISE_DECISION_ENGINE",
                ),
            ),
            ServiceRegistration(
                "ENTERPRISE_DAILY_CYCLE",
                daily_cycle,
                dependencies=("ENTERPRISE_WORKFLOW_ORCHESTRATOR",),
            ),
        )
        for registration in registrations:
            registry.register(registration)
        registry.freeze()
        container = cls(
            registry=registry,
            intelligence_service=intelligence_service,
            cio_pipeline=cio_pipeline,
            decision_engine=decision_engine,
            workflow_orchestrator=workflow_orchestrator,
            daily_cycle=daily_cycle,
        )
        container.validate()
        return container

    def validate(self) -> None:
        if not self.registry.frozen:
            raise PlatformValidationError("enterprise service registry must be frozen")
        expected = {
            "ENTERPRISE_INTELLIGENCE_SERVICE": self.intelligence_service,
            "ENTERPRISE_CIO_PIPELINE": self.cio_pipeline,
            "ENTERPRISE_DECISION_ENGINE": self.decision_engine,
            "ENTERPRISE_WORKFLOW_ORCHESTRATOR": self.workflow_orchestrator,
            "ENTERPRISE_DAILY_CYCLE": self.daily_cycle,
        }
        for service_id, instance in expected.items():
            if self.registry.resolve(service_id) is not instance:
                raise PlatformValidationError(f"container identity mismatch for {service_id}")
        if self.workflow_orchestrator.decision_engine is not self.decision_engine:
            raise PlatformValidationError("orchestrator must share the registered decision engine")
