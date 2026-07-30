"""Canonical Version 1 Enterprise Event contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4


@dataclass(frozen=True)
class EnterpriseEvent:
    event_type: str
    source: str
    payload: Mapping[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = "1.0"
    correlation_id: str | None = None
    strategy_id: str | None = None
    severity: str = "INFO"
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        for name, value in {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "occurred_at": self.occurred_at,
            "schema_version": self.schema_version,
        }.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if self.schema_version != "1.0":
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.severity not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"unsupported severity: {self.severity}")
        if not isinstance(self.payload, Mapping):
            raise ValueError("payload must be a mapping")
        if self.paper_trade_mode is not True:
            raise ValueError("paper_trade_mode must be true")
        if self.live_trading_enabled is not False:
            raise ValueError("live_trading_enabled must be false")
        if self.broker_execution_enabled is not False:
            raise ValueError("broker_execution_enabled must be false")
        datetime.fromisoformat(self.occurred_at.replace("Z", "+00:00"))

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        result = asdict(self)
        result["payload"] = dict(self.payload)
        return result

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EnterpriseEvent":
        event = cls(
            event_id=str(payload.get("event_id") or uuid4()),
            event_type=str(payload.get("event_type", "")).strip(),
            source=str(payload.get("source", "")).strip(),
            payload=dict(payload.get("payload") or {}),
            occurred_at=str(payload.get("occurred_at") or datetime.now(timezone.utc).isoformat()),
            schema_version=str(payload.get("schema_version", "1.0")),
            correlation_id=payload.get("correlation_id"),
            strategy_id=payload.get("strategy_id"),
            severity=str(payload.get("severity", "INFO")).upper(),
            paper_trade_mode=payload.get("paper_trade_mode", True),
            live_trading_enabled=payload.get("live_trading_enabled", False),
            broker_execution_enabled=payload.get("broker_execution_enabled", False),
        )
        event.validate()
        return event
