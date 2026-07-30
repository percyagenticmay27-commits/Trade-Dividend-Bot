from __future__ import annotations

from enterprise_core.event_bus import EnterpriseEventBus
from enterprise_core.plugin_sdk import PluginContext, PluginRunResult, ServiceRegistry
from enterprise_core.plugin_sdk.plugin import EnterpriseStrategyPlugin
from enterprise_core.runtime import EnterpriseRuntime


class DemoPlugin(EnterpriseStrategyPlugin):
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self.initialized = False
        self.stopped = False

    @property
    def strategy_id(self) -> str:
        return "BOT-001"

    def initialize(self, context: PluginContext) -> None:
        context.validate()
        self.initialized = True

    def run(self) -> PluginRunResult:
        if self._fail:
            raise RuntimeError("paper cycle failed")
        return PluginRunResult(strategy_id=self.strategy_id, status="SUCCESS")

    def shutdown(self) -> None:
        self.stopped = True


def _context() -> PluginContext:
    return PluginContext(
        strategy_id="BOT-001",
        strategy_root=".",
        required_services=("enterprise_market_data",),
    )


def _services() -> ServiceRegistry:
    return ServiceRegistry({"enterprise_market_data": object()})


def test_runtime_initializes_plugin_and_emits_event() -> None:
    events = []
    bus = EnterpriseEventBus()
    bus.subscribe("*", events.append)
    runtime = EnterpriseRuntime(DemoPlugin(), _context(), _services(), bus)
    snapshot = runtime.initialize()
    assert snapshot.initialized is True
    assert events[-1].event_type == "strategy.runtime.initialized"


def test_runtime_runs_once_and_tracks_state() -> None:
    runtime = EnterpriseRuntime(DemoPlugin(), _context(), _services())
    runtime.initialize()
    result = runtime.run_once()
    assert result.status == "SUCCESS"
    assert runtime.snapshot().run_count == 1
    assert runtime.snapshot().last_status == "SUCCESS"


def test_runtime_emits_completion_event() -> None:
    events = []
    bus = EnterpriseEventBus()
    bus.subscribe("strategy.runtime.completed", events.append)
    runtime = EnterpriseRuntime(DemoPlugin(), _context(), _services(), bus)
    runtime.initialize()
    runtime.run_once()
    assert len(events) == 1
    assert events[0].strategy_id == "BOT-001"


def test_runtime_emits_failure_event_and_reraises() -> None:
    import pytest

    events = []
    bus = EnterpriseEventBus()
    bus.subscribe("strategy.runtime.failed", events.append)
    runtime = EnterpriseRuntime(DemoPlugin(fail=True), _context(), _services(), bus)
    runtime.initialize()
    with pytest.raises(RuntimeError, match="paper cycle failed"):
        runtime.run_once()
    assert events[0].severity == "ERROR"


def test_runtime_shutdown_updates_snapshot() -> None:
    plugin = DemoPlugin()
    runtime = EnterpriseRuntime(plugin, _context(), _services())
    runtime.initialize()
    snapshot = runtime.shutdown()
    assert snapshot.initialized is False
    assert plugin.stopped is True


def test_snapshot_lists_registered_services() -> None:
    runtime = EnterpriseRuntime(DemoPlugin(), _context(), _services())
    assert runtime.snapshot().service_names == ("enterprise_market_data",)


def test_runtime_rejects_missing_required_service() -> None:
    import pytest

    with pytest.raises(KeyError, match="service not registered"):
        EnterpriseRuntime(DemoPlugin(), _context(), ServiceRegistry())


def test_runtime_rejects_strategy_id_mismatch() -> None:
    import pytest

    bad = PluginContext(strategy_id="OTHER", strategy_root=".", required_services=())
    with pytest.raises(ValueError, match="strategy_id"):
        EnterpriseRuntime(DemoPlugin(), bad, ServiceRegistry())


def test_runtime_is_permanently_paper_only() -> None:
    runtime = EnterpriseRuntime(DemoPlugin(), _context(), _services())
    assert runtime.paper_trade_mode is True
    assert runtime.live_trading_enabled is False
    assert runtime.broker_execution_enabled is False


def test_snapshot_serialization_contains_safety_flags() -> None:
    payload = EnterpriseRuntime(DemoPlugin(), _context(), _services()).snapshot().to_dict()
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
