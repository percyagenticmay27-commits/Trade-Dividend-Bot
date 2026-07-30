"""Canonical Version 1 strategy manifest contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class StrategyManifest:
    strategy_id: str
    strategy_name: str
    version: str
    lifecycle_status: str
    certification_level: str
    entrypoint: str
    capabilities: Sequence[str]
    permissions: Sequence[str]
    required_services: Sequence[str]
    output_paths: Mapping[str, str]
    state_owner: str
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False
    schema_version: str = "1.0"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        required_text = {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "version": self.version,
            "lifecycle_status": self.lifecycle_status,
            "certification_level": self.certification_level,
            "entrypoint": self.entrypoint,
            "state_owner": self.state_owner,
            "schema_version": self.schema_version,
        }
        for field_name, value in required_text.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} is required")
        if self.paper_trade_mode is not True:
            raise ValueError("paper_trade_mode must be true")
        if self.live_trading_enabled is not False:
            raise ValueError("live_trading_enabled must be false")
        if self.broker_execution_enabled is not False:
            raise ValueError("broker_execution_enabled must be false")
        for field_name, values in {
            "capabilities": self.capabilities,
            "permissions": self.permissions,
            "required_services": self.required_services,
        }.items():
            if isinstance(values, (str, bytes)):
                raise ValueError(f"{field_name} must be a sequence")
            normalized = [str(value).strip() for value in values]
            if any(not value for value in normalized):
                raise ValueError(f"{field_name} cannot contain empty values")
            if len(normalized) != len(set(normalized)):
                raise ValueError(f"{field_name} cannot contain duplicates")
        required_outputs = {"manifest", "status", "health", "outputs"}
        missing = required_outputs.difference(self.output_paths)
        if missing:
            raise ValueError(f"missing required output paths: {', '.join(sorted(missing))}")
        for name, path in self.output_paths.items():
            if not str(name).strip() or not str(path).strip():
                raise ValueError("output_paths keys and values must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        result = asdict(self)
        result["capabilities"] = list(self.capabilities)
        result["permissions"] = list(self.permissions)
        result["required_services"] = list(self.required_services)
        result["output_paths"] = dict(self.output_paths)
        result["metadata"] = dict(self.metadata)
        return result

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StrategyManifest":
        manifest = cls(
            strategy_id=str(payload.get("strategy_id", "")).strip(),
            strategy_name=str(payload.get("strategy_name", "")).strip(),
            version=str(payload.get("version", "")).strip(),
            lifecycle_status=str(payload.get("lifecycle_status", "")).strip(),
            certification_level=str(payload.get("certification_level", "")).strip(),
            entrypoint=str(payload.get("entrypoint", "")).strip(),
            capabilities=tuple(payload.get("capabilities") or ()),
            permissions=tuple(payload.get("permissions") or ()),
            required_services=tuple(payload.get("required_services") or ()),
            output_paths=dict(payload.get("output_paths") or {}),
            state_owner=str(payload.get("state_owner", "")).strip(),
            paper_trade_mode=payload.get("paper_trade_mode", True),
            live_trading_enabled=payload.get("live_trading_enabled", False),
            broker_execution_enabled=payload.get("broker_execution_enabled", False),
            schema_version=str(payload.get("schema_version", "1.0")).strip(),
            metadata=dict(payload.get("metadata") or {}),
        )
        manifest.validate()
        return manifest
