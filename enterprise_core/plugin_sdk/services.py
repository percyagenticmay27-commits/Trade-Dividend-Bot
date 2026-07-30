"""Restricted Enterprise service registry exposed to strategy plugins."""

from __future__ import annotations

from typing import Any, Mapping


class ServiceRegistry:
    paper_trade_mode = True
    live_trading_enabled = False
    broker_execution_enabled = False

    def __init__(self, services: Mapping[str, Any] | None = None) -> None:
        self._services: dict[str, Any] = {}
        for name, service in dict(services or {}).items():
            self.register(name, service)

    def register(self, name: str, service: Any) -> None:
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("service name is required")
        if normalized in self._services:
            raise ValueError(f"service already registered: {normalized}")
        if service is None:
            raise ValueError("service cannot be None")
        self._services[normalized] = service

    def resolve(self, name: str) -> Any:
        normalized = name.strip().lower()
        if normalized not in self._services:
            raise KeyError(f"service not registered: {normalized}")
        return self._services[normalized]

    def require(self, names: list[str] | tuple[str, ...]) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for name in names:
            normalized = name.strip().lower()
            if normalized in resolved:
                raise ValueError(f"duplicate required service: {normalized}")
            resolved[normalized] = self.resolve(normalized)
        return resolved

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._services))
