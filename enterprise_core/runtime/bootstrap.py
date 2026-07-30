"""Version 1 paper-only Enterprise Runtime bootstrap."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

from enterprise_core.event_bus import EnterpriseEvent, EnterpriseEventBus
from enterprise_core.plugin_sdk import PluginContext, PluginRunResult, PluginRuntime, ServiceRegistry
from enterprise_core.plugin_sdk.plugin import EnterpriseStrategyPlugin


@dataclass(frozen=True)
class EnterpriseRuntimeSnapshot:
    strategy_id: str
    initialized: bool
    run_count: int
    last_status: str | None
    service_names: tuple[str, ...]
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class EnterpriseRuntime:
    """Compose one strategy plugin with Enterprise services and lifecycle events."""

    paper_trade_mode = True
    live_trading_enabled = False
    broker_execution_enabled = False

    def __init__(
        self,
        plugin: EnterpriseStrategyPlugin,
        context: PluginContext,
        services: ServiceRegistry,
        event_bus: EnterpriseEventBus | None = None,
    ) -> None:
        self._runtime = PluginRuntime(plugin, context, services)
        self._context = context
        self._services = services
        self._event_bus = event_bus or EnterpriseEventBus()

    @property
    def event_bus(self) -> EnterpriseEventBus:
        return self._event_bus

    def initialize(self) -> EnterpriseRuntimeSnapshot:
        self._runtime.initialize()
        self._publish("strategy.runtime.initialized", {"status": "INITIALIZED"})
        return self.snapshot()

    def run_once(self) -> PluginRunResult:
        try:
            result = self._runtime.run_once()
        except Exception as exc:
            self._publish(
                "strategy.runtime.failed",
                {"error": str(exc)},
                severity="ERROR",
            )
            raise
        self._publish(
            "strategy.runtime.completed",
            {
                "status": result.status,
                "output_paths": dict(result.output_paths),
                "warnings": list(result.warnings),
            },
            severity="WARNING" if result.status == "WARNING" else "INFO",
        )
        return result

    def shutdown(self) -> EnterpriseRuntimeSnapshot:
        self._runtime.shutdown()
        self._publish("strategy.runtime.shutdown", {"status": "STOPPED"})
        return self.snapshot()

    def snapshot(self) -> EnterpriseRuntimeSnapshot:
        state = self._runtime.state()
        return EnterpriseRuntimeSnapshot(
            strategy_id=state.strategy_id,
            initialized=state.initialized,
            run_count=state.run_count,
            last_status=state.last_status,
            service_names=tuple(sorted(self._service_names())),
        )

    def _service_names(self) -> tuple[str, ...]:
        names = getattr(self._services, "names", None)
        if callable(names):
            return tuple(names())
        raw = getattr(self._services, "_services", {})
        if isinstance(raw, Mapping):
            return tuple(str(name) for name in raw)
        return ()

    def _publish(self, event_type: str, payload: Mapping[str, object], severity: str = "INFO") -> None:
        self._event_bus.publish(
            EnterpriseEvent(
                event_type=event_type,
                source="enterprise_runtime",
                payload=dict(payload),
                strategy_id=self._context.strategy_id,
                severity=severity,
            )
        )
