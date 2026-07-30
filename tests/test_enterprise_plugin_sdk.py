from __future__ import annotations

import pytest

from enterprise_core.plugin_sdk import (
    EnterpriseStrategyPlugin,
    PluginContext,
    PluginRunResult,
    PluginRuntime,
    ServiceRegistry,
)


class DemoPlugin(EnterpriseStrategyPlugin):
    def __init__(self, strategy_id: str = "demo") -> None:
        self._strategy_id = strategy_id
        self.initialized = False
        self.shutdown_called = False

    @property
    def strategy_id(self) -> str:
        return self._strategy_id

    def initialize(self, context: PluginContext) -> None:
        context.validate()
        self.initialized = True

    def run(self) -> PluginRunResult:
        return PluginRunResult(self.strategy_id, "SUCCESS", {"report": "reports/demo.json"})

    def shutdown(self) -> None:
        self.shutdown_called = True


def _context(strategy_id: str = "demo") -> PluginContext:
    return PluginContext(strategy_id, ".", ("enterprise_market_data",))


def test_context_round_trip_and_safety_flags() -> None:
    payload = _context().to_dict()
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False


def test_context_rejects_live_trading() -> None:
    with pytest.raises(ValueError):
        PluginContext("demo", ".", (), live_trading_enabled=True).validate()


def test_context_rejects_duplicate_services() -> None:
    with pytest.raises(ValueError):
        PluginContext("demo", ".", ("x", "x")).validate()


def test_run_result_validation() -> None:
    result = PluginRunResult("demo", "SUCCESS", {"report": "report.json"})
    assert result.to_dict()["status"] == "SUCCESS"


def test_run_result_rejects_unknown_status() -> None:
    with pytest.raises(ValueError):
        PluginRunResult("demo", "UNKNOWN").validate()


def test_service_registry_registers_and_resolves() -> None:
    service = object()
    registry = ServiceRegistry({"enterprise_market_data": service})
    assert registry.resolve("ENTERPRISE_MARKET_DATA") is service


def test_service_registry_rejects_duplicate_name() -> None:
    registry = ServiceRegistry({"x": object()})
    with pytest.raises(ValueError):
        registry.register("X", object())


def test_service_registry_require_rejects_missing() -> None:
    with pytest.raises(KeyError):
        ServiceRegistry().require(("missing",))


def test_runtime_requires_matching_strategy_id() -> None:
    with pytest.raises(ValueError):
        PluginRuntime(DemoPlugin("other"), _context(), ServiceRegistry({"enterprise_market_data": object()}))


def test_runtime_requires_declared_services() -> None:
    with pytest.raises(KeyError):
        PluginRuntime(DemoPlugin(), _context(), ServiceRegistry())


def test_runtime_requires_initialize_before_run() -> None:
    runtime = PluginRuntime(DemoPlugin(), _context(), ServiceRegistry({"enterprise_market_data": object()}))
    with pytest.raises(RuntimeError):
        runtime.run_once()


def test_runtime_initialize_run_and_state() -> None:
    plugin = DemoPlugin()
    runtime = PluginRuntime(plugin, _context(), ServiceRegistry({"enterprise_market_data": object()}))
    runtime.initialize()
    result = runtime.run_once()
    state = runtime.state()
    assert plugin.initialized is True
    assert result.status == "SUCCESS"
    assert state.initialized is True
    assert state.run_count == 1
    assert state.last_status == "SUCCESS"


def test_runtime_rejects_double_initialize() -> None:
    runtime = PluginRuntime(DemoPlugin(), _context(), ServiceRegistry({"enterprise_market_data": object()}))
    runtime.initialize()
    with pytest.raises(RuntimeError):
        runtime.initialize()


def test_runtime_shutdown() -> None:
    plugin = DemoPlugin()
    runtime = PluginRuntime(plugin, _context(), ServiceRegistry({"enterprise_market_data": object()}))
    runtime.initialize()
    runtime.shutdown()
    assert plugin.shutdown_called is True
    assert runtime.state().initialized is False


def test_sdk_components_are_permanently_paper_only() -> None:
    for component in (DemoPlugin(), ServiceRegistry()):
        assert component.paper_trade_mode is True
        assert component.live_trading_enabled is False
        assert component.broker_execution_enabled is False
