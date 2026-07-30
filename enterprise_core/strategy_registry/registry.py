"""Validated in-memory registry for discovered strategies."""

from __future__ import annotations

from .manifest import StrategyManifest


class DuplicateStrategyError(ValueError):
    """Raised when a stable strategy ID is registered more than once."""


class StrategyRegistry:
    paper_trade_mode = True
    live_trading_enabled = False
    broker_execution_enabled = False

    def __init__(self) -> None:
        self._manifests: dict[str, StrategyManifest] = {}

    def register(self, manifest: StrategyManifest) -> None:
        manifest.validate()
        key = manifest.strategy_id.strip().lower()
        if key in self._manifests:
            raise DuplicateStrategyError(f"strategy already registered: {manifest.strategy_id}")
        self._manifests[key] = manifest

    def replace(self, manifest: StrategyManifest) -> None:
        manifest.validate()
        self._manifests[manifest.strategy_id.strip().lower()] = manifest

    def unregister(self, strategy_id: str) -> StrategyManifest:
        key = strategy_id.strip().lower()
        if key not in self._manifests:
            raise KeyError(strategy_id)
        return self._manifests.pop(key)

    def get(self, strategy_id: str) -> StrategyManifest:
        key = strategy_id.strip().lower()
        if key not in self._manifests:
            raise KeyError(strategy_id)
        return self._manifests[key]

    def contains(self, strategy_id: str) -> bool:
        return strategy_id.strip().lower() in self._manifests

    def list(self) -> tuple[StrategyManifest, ...]:
        return tuple(sorted(self._manifests.values(), key=lambda item: item.strategy_id.lower()))

    def by_lifecycle(self, lifecycle_status: str) -> tuple[StrategyManifest, ...]:
        target = lifecycle_status.strip().upper()
        return tuple(item for item in self.list() if item.lifecycle_status.upper() == target)

    def __len__(self) -> int:
        return len(self._manifests)
