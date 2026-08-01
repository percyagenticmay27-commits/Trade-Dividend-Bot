from __future__ import annotations

from copy import deepcopy

from src.dividend_bot.enterprise_strategy_discovery import (
    discover_registered_strategies,
    summarize_strategy_discovery,
)


def _plugin(strategy_id: str, display_name: str) -> dict:
    return {
        "strategy_id": strategy_id,
        "display_name": display_name,
        "strategy_type": "SWING" if strategy_id.startswith("SWING") else "DIVIDEND",
        "lifecycle_status": "PRODUCTION",
        "runtime_status": "ONLINE",
        "health_status": "HEALTHY",
        "readiness": "READY",
        "enabled": True,
        "paper_trade_mode": True,
        "paper_compatible": True,
        "advisory_only": True,
        "reporting_only": True,
    }


def test_discovers_dividend_and_swing_deterministically() -> None:
    registry = {
        "strategy_plugins": [
            _plugin("SWING-001", "Trade Swing Bot"),
            _plugin("DIVIDEND-001", "Dividend Income Strategy"),
        ]
    }

    strategies, warnings = discover_registered_strategies(registry)

    assert warnings == []
    assert [item["strategy_id"] for item in strategies] == [
        "DIVIDEND-001",
        "SWING-001",
    ]
    assert strategies[0]["display_name"] == "Dividend Income Strategy"
    assert strategies[1]["display_name"] == "Trade Swing Bot"


def test_discovery_preserves_registry_status_fields() -> None:
    strategies, warnings = discover_registered_strategies(
        {"strategy_plugins": [_plugin("SWING-001", "Trade Swing Bot")]}
    )

    assert warnings == []
    strategy = strategies[0]
    assert strategy["strategy_type"] == "SWING"
    assert strategy["lifecycle_status"] == "PRODUCTION"
    assert strategy["runtime_status"] == "ONLINE"
    assert strategy["health_status"] == "HEALTHY"
    assert strategy["readiness"] == "READY"


def test_duplicate_strategy_ids_are_ignored_safely() -> None:
    registry = {
        "strategy_plugins": [
            _plugin("DIVIDEND-001", "Dividend Income Strategy"),
            _plugin("DIVIDEND-001", "Duplicate Dividend"),
            _plugin("SWING-001", "Trade Swing Bot"),
        ]
    }

    strategies, warnings = discover_registered_strategies(registry)

    assert [item["strategy_id"] for item in strategies] == [
        "DIVIDEND-001",
        "SWING-001",
    ]
    assert warnings == ["Duplicate strategy ID ignored: DIVIDEND-001"]


def test_malformed_plugin_does_not_remove_valid_dividend_strategy() -> None:
    registry = {
        "strategy_plugins": [
            _plugin("DIVIDEND-001", "Dividend Income Strategy"),
            None,
            {"display_name": "Missing ID"},
        ]
    }

    strategies, warnings = discover_registered_strategies(registry)

    assert [item["strategy_id"] for item in strategies] == ["DIVIDEND-001"]
    assert len(warnings) == 2


def test_missing_strategy_collection_returns_structured_warning() -> None:
    strategies, warnings = discover_registered_strategies({})

    assert strategies == []
    assert warnings == ["Enterprise registry does not contain strategy_plugins."]


def test_summary_reports_enterprise_strategy_counts() -> None:
    strategies, _ = discover_registered_strategies(
        {
            "strategy_plugins": [
                _plugin("DIVIDEND-001", "Dividend Income Strategy"),
                _plugin("SWING-001", "Trade Swing Bot"),
            ]
        }
    )

    summary = summarize_strategy_discovery(strategies)

    assert summary["registered_strategy_count"] == 2
    assert summary["enabled_strategy_count"] == 2
    assert summary["paper_compatible_strategy_count"] == 2
    assert summary["strategy_ids"] == ["DIVIDEND-001", "SWING-001"]
    assert summary["paper_trade_mode"] is True
    assert summary["reporting_only"] is True


def test_discovery_is_read_only() -> None:
    registry = {"strategy_plugins": [_plugin("DIVIDEND-001", "Dividend Income Strategy")]}
    original = deepcopy(registry)

    discover_registered_strategies(registry)

    assert registry == original


def test_discovery_module_contains_no_strategy_production_imports() -> None:
    from pathlib import Path

    source = Path("src/dividend_bot/enterprise_strategy_discovery.py").read_text(
        encoding="utf-8"
    )

    assert "Trade-Swing-Bot" not in source
    assert "swing_trade_bot" not in source
    assert "importlib" not in source
