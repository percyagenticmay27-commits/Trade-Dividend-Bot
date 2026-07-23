"""Shared strategy registry and lifecycle framework for the paper-only platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from .platform_foundation import PlatformValidationError

MODULE_NAME = "strategy_framework"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Strategy-neutral registration, configuration, and lifecycle management."


class StrategyStatus(str, Enum):
    INSTALLED = "INSTALLED"
    CONFIGURED = "CONFIGURED"
    PAPER_VALIDATION = "PAPER_VALIDATION"
    OPERATIONAL = "OPERATIONAL"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"


_ALLOWED_TRANSITIONS: dict[StrategyStatus, frozenset[StrategyStatus]] = {
    StrategyStatus.INSTALLED: frozenset({StrategyStatus.CONFIGURED, StrategyStatus.ARCHIVED}),
    StrategyStatus.CONFIGURED: frozenset(
        {StrategyStatus.PAPER_VALIDATION, StrategyStatus.SUSPENDED, StrategyStatus.ARCHIVED}
    ),
    StrategyStatus.PAPER_VALIDATION: frozenset(
        {StrategyStatus.OPERATIONAL, StrategyStatus.CONFIGURED, StrategyStatus.SUSPENDED}
    ),
    StrategyStatus.OPERATIONAL: frozenset({StrategyStatus.SUSPENDED, StrategyStatus.ARCHIVED}),
    StrategyStatus.SUSPENDED: frozenset(
        {StrategyStatus.CONFIGURED, StrategyStatus.PAPER_VALIDATION, StrategyStatus.ARCHIVED}
    ),
    StrategyStatus.ARCHIVED: frozenset(),
}


@dataclass(frozen=True)
class StrategyDefinition:
    strategy_id: str
    name: str
    version: str
    supported_asset_types: tuple[str, ...]
    required_intelligence: tuple[str, ...]
    supported_report_types: tuple[str, ...]
    supported_audit_types: tuple[str, ...]
    module_entry_point: str
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if not self.strategy_id or self.strategy_id != self.strategy_id.upper():
            raise PlatformValidationError("strategy_id must be non-empty uppercase text")
        if not self.name.strip() or not self.module_entry_point.strip():
            raise PlatformValidationError("strategy name and module_entry_point must not be empty")
        if self.version.count(".") != 2 or not all(part.isdigit() for part in self.version.split(".")):
            raise PlatformValidationError("strategy version must use semantic versioning")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("strategy paper_trade_mode must remain True")
        if self.live_trading_enabled is not False:
            raise PlatformValidationError("strategy live_trading_enabled must remain False")
        if self.broker_execution_enabled is not False:
            raise PlatformValidationError("strategy broker_execution_enabled must remain False")
        if not self.supported_asset_types:
            raise PlatformValidationError("strategy must declare at least one supported asset type")
        if not self.required_intelligence:
            raise PlatformValidationError("strategy must declare required intelligence")


@dataclass(frozen=True)
class StrategyConfiguration:
    strategy_id: str
    version: str
    parameters: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.strategy_id or self.strategy_id != self.strategy_id.upper():
            raise PlatformValidationError("configuration strategy_id must be uppercase")
        if self.version.count(".") != 2 or not all(part.isdigit() for part in self.version.split(".")):
            raise PlatformValidationError("configuration version must use semantic versioning")
        forbidden = {"paper_trade_mode": False, "live_trading_enabled": True, "broker_execution_enabled": True}
        for key, unsafe_value in forbidden.items():
            if self.parameters.get(key) == unsafe_value:
                raise PlatformValidationError(f"unsafe strategy configuration: {key}={unsafe_value}")


@dataclass(frozen=True)
class StrategyLifecycleEvent:
    strategy_id: str
    from_status: StrategyStatus
    to_status: StrategyStatus
    reason: str

    def validate(self) -> None:
        if not self.strategy_id.strip() or not self.reason.strip():
            raise PlatformValidationError("lifecycle strategy_id and reason must not be empty")
        if self.to_status not in _ALLOWED_TRANSITIONS[self.from_status]:
            raise PlatformValidationError(
                f"invalid strategy lifecycle transition: {self.from_status.value} -> {self.to_status.value}"
            )


class StrategyRegistry:
    """In-memory registry enforcing unique, isolated strategy definitions."""

    def __init__(self) -> None:
        self._definitions: dict[str, StrategyDefinition] = {}
        self._configurations: dict[str, StrategyConfiguration] = {}
        self._statuses: dict[str, StrategyStatus] = {}
        self._history: list[StrategyLifecycleEvent] = []

    def register(self, definition: StrategyDefinition) -> None:
        definition.validate()
        existing = self._definitions.get(definition.strategy_id)
        if existing is not None and existing != definition:
            raise PlatformValidationError(f"conflicting strategy registration: {definition.strategy_id}")
        self._definitions[definition.strategy_id] = definition
        self._statuses.setdefault(definition.strategy_id, StrategyStatus.INSTALLED)

    def configure(self, configuration: StrategyConfiguration) -> None:
        configuration.validate()
        definition = self.get(configuration.strategy_id)
        if configuration.version != definition.version:
            raise PlatformValidationError("configuration version must match registered strategy version")
        self._configurations[configuration.strategy_id] = configuration

    def transition(self, strategy_id: str, to_status: StrategyStatus, reason: str) -> StrategyLifecycleEvent:
        self.get(strategy_id)
        from_status = self._statuses[strategy_id]
        if to_status is StrategyStatus.CONFIGURED and strategy_id not in self._configurations:
            raise PlatformValidationError("strategy must be configured before entering CONFIGURED")
        event = StrategyLifecycleEvent(strategy_id, from_status, to_status, reason)
        event.validate()
        self._statuses[strategy_id] = to_status
        self._history.append(event)
        return event

    def get(self, strategy_id: str) -> StrategyDefinition:
        try:
            return self._definitions[strategy_id]
        except KeyError as exc:
            raise PlatformValidationError(f"strategy is not registered: {strategy_id}") from exc

    def get_configuration(self, strategy_id: str) -> StrategyConfiguration:
        self.get(strategy_id)
        try:
            return self._configurations[strategy_id]
        except KeyError as exc:
            raise PlatformValidationError(f"strategy is not configured: {strategy_id}") from exc

    def status(self, strategy_id: str) -> StrategyStatus:
        self.get(strategy_id)
        return self._statuses[strategy_id]

    def list_definitions(self) -> tuple[StrategyDefinition, ...]:
        return tuple(self._definitions[key] for key in sorted(self._definitions))

    def history(self, strategy_id: str | None = None) -> tuple[StrategyLifecycleEvent, ...]:
        if strategy_id is None:
            return tuple(self._history)
        self.get(strategy_id)
        return tuple(event for event in self._history if event.strategy_id == strategy_id)
