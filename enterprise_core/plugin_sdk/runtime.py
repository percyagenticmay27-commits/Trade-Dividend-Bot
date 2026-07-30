"""Safe Version 1 runtime for initialized strategy plugins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import PluginContext, PluginRunResult
from .plugin import EnterpriseStrategyPlugin
from .services import ServiceRegistry


@dataclass(frozen=True)
class PluginRuntimeState:
    strategy_id: str
    initialized: bool
    run_count: int
    last_status: str | None


class PluginRuntime:
    paper_trade_mode = True
    live_trading_enabled = False
    broker_execution_enabled = False

    def __init__(
        self,
        plugin: EnterpriseStrategyPlugin,
        context: PluginContext,
        services: ServiceRegistry,
    ) -> None:
        context.validate()
        if plugin.strategy_id != context.strategy_id:
            raise ValueError("plugin strategy_id does not match context")
        services.require(tuple(context.required_services))
        self._plugin = plugin
        self._context = context
        self._services = services
        self._initialized = False
        self._run_count = 0
        self._last_status: str | None = None

    @property
    def services(self) -> ServiceRegistry:
        return self._services

    def initialize(self) -> None:
        if self._initialized:
            raise RuntimeError("plugin is already initialized")
        self._plugin.initialize(self._context)
        self._initialized = True

    def run_once(self) -> PluginRunResult:
        if not self._initialized:
            raise RuntimeError("plugin must be initialized before run")
        result = self._plugin.run()
        result.validate()
        if result.strategy_id != self._context.strategy_id:
            raise ValueError("plugin run result strategy_id does not match context")
        self._run_count += 1
        self._last_status = result.status
        return result

    def shutdown(self) -> None:
        if self._initialized:
            self._plugin.shutdown()
            self._initialized = False

    def state(self) -> PluginRuntimeState:
        return PluginRuntimeState(
            strategy_id=self._context.strategy_id,
            initialized=self._initialized,
            run_count=self._run_count,
            last_status=self._last_status,
        )
