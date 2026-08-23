from src.dividend_bot.enterprise_dividend_service_registry_event_wiring import (
    build_service_registry,
    default_dividend_strategy_plugins,
)
from src.dividend_bot.paper_capital_allocation import discover_strategy_plugins


FIXED_TIME = "2026-07-30T18:00:00Z"


def test_default_dividend_strategy_plugin_is_locked_paper_only():
    plugins = default_dividend_strategy_plugins()

    assert len(plugins) == 1
    plugin = plugins[0]
    expected = {
        "strategy_id": "dividend",
        "display_name": "Dividend Income Strategy",
        "plugin_type": "STRATEGY",
        "strategy_plugin": True,
        "status": "READY",
        "enabled": True,
        "version": "1.0.0",
        "health": "HEALTHY",
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
    }

    for key, value in expected.items():
        assert plugin.get(key) == value


def test_build_service_registry_publishes_strategy_plugins_without_changing_services():
    registry = build_service_registry(generated_at_utc=FIXED_TIME)

    assert registry["summary"]["strategy_plugin_count"] == 1
    assert len(registry["strategy_plugins"]) == 1
    assert registry["strategy_plugins"][0]["strategy_id"] == "dividend"
    assert registry["summary"]["service_count"] == len(registry["services"])
    assert registry["services"]


def test_allocation_discovery_finds_exactly_one_dividend_strategy():
    registry = build_service_registry(generated_at_utc=FIXED_TIME)

    discovered = discover_strategy_plugins(registry)

    assert discovered == [{
        "strategy_id": "dividend",
        "display_name": "Dividend Income Strategy",
        "status": "READY",
        "version": "1.0.0",
        "health": "HEALTHY",
        "paper_trade_mode": True,
    }]


def test_registry_remains_deterministic_with_fixed_time():
    first = build_service_registry(generated_at_utc=FIXED_TIME)
    second = build_service_registry(generated_at_utc=FIXED_TIME)

    assert first == second
