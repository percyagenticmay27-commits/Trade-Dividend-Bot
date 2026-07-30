"""Canonical Version 1 Enterprise Plugin SDK models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class PluginContext:
    strategy_id: str
    strategy_root: str
    required_services: Sequence[str]
    configuration: Mapping[str, Any] = field(default_factory=dict)
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if not self.strategy_id.strip():
            raise ValueError("strategy_id is required")
        if not self.strategy_root.strip():
            raise ValueError("strategy_root is required")
        if self.paper_trade_mode is not True:
            raise ValueError("paper_trade_mode must be true")
        if self.live_trading_enabled is not False:
            raise ValueError("live_trading_enabled must be false")
        if self.broker_execution_enabled is not False:
            raise ValueError("broker_execution_enabled must be false")
        services = [str(item).strip() for item in self.required_services]
        if any(not item for item in services):
            raise ValueError("required_services cannot contain empty values")
        if len(services) != len(set(services)):
            raise ValueError("required_services cannot contain duplicates")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        payload = asdict(self)
        payload["required_services"] = list(self.required_services)
        payload["configuration"] = dict(self.configuration)
        return payload


@dataclass(frozen=True)
class PluginRunResult:
    strategy_id: str
    status: str
    output_paths: Mapping[str, str] = field(default_factory=dict)
    warnings: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    ALLOWED_STATUSES = frozenset({"SUCCESS", "WARNING", "FAILED", "SKIPPED"})

    def validate(self) -> None:
        if not self.strategy_id.strip():
            raise ValueError("strategy_id is required")
        if self.status not in self.ALLOWED_STATUSES:
            raise ValueError(f"unsupported run status: {self.status}")
        for name, path in self.output_paths.items():
            if not str(name).strip() or not str(path).strip():
                raise ValueError("output_paths keys and values must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "strategy_id": self.strategy_id,
            "status": self.status,
            "output_paths": dict(self.output_paths),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }
