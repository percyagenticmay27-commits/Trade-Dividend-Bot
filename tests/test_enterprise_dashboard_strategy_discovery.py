from __future__ import annotations

from copy import deepcopy

from src.dividend_bot.enterprise_dashboard_strategy_discovery import (
    attach_dashboard_strategy_discovery,
    build_dashboard_strategy_discovery,
)


def _registry() -> dict[str, object]:
    return {
        "strategy_plugins": [
            {
                "strategy_id": "SWING-001",
                "display_name": "Trade Swing Bot",
                "strategy_type": "SWING",
                "lifecycle_status": "ACTIVE",
                "runtime_status": "ONLINE",
                "health_status": "HEALTHY",
                "readiness": "READY",
                "enabled": True,
                "paper_trade_mode": True,
                "paper_compatible": True,
                "advisory_only": True,
                "reporting_only": True,
            },
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Income Strategy",
                "strategy_type": "DIVIDEND_ETF",
                "lifecycle_status": "PRODUCTION",
                "runtime_status": "ONLINE",
                "health_status": "HEALTHY",
                "readiness": "READY",
                "enabled": True,
                "paper_trade_mode": True,
                "paper_compatible": True,
                "advisory_only": False,
                "reporting_only": True,
            },
        ]
    }


def test_builds_summary_for_all_registered_strategies() -> None:
    discovery, warnings = build_dashboard_strategy_discovery(_registry())

    assert warnings == []
    assert discovery["summary"] == {
        "registered_strategy_count": 2,
        "enabled_strategy_count": 2,
        "paper_compatible_strategy_count": 2,
        "strategy_ids": ["DIVIDEND-001", "SWING-001"],
        "paper_trade_mode": True,
        "reporting_only": True,
    }
    assert [item["strategy_id"] for item in discovery["strategies"]] == [
        "DIVIDEND-001",
        "SWING-001",
    ]


def test_preserves_per_strategy_safety_and_status_metadata() -> None:
    discovery, _ = build_dashboard_strategy_discovery(_registry())
    swing = next(
        item for item in discovery["strategies"] if item["strategy_id"] == "SWING-001"
    )

    assert swing["runtime_status"] == "ONLINE"
    assert swing["health_status"] == "HEALTHY"
    assert swing["readiness"] == "READY"
    assert swing["paper_trade_mode"] is True
    assert swing["paper_compatible"] is True
    assert swing["advisory_only"] is True
    assert swing["reporting_only"] is True


def test_duplicate_strategy_is_ignored_with_warning() -> None:
    registry = _registry()
    registry["strategy_plugins"].append(
        {
            "strategy_id": "SWING-001",
            "display_name": "Duplicate Swing",
        }
    )

    discovery, warnings = build_dashboard_strategy_discovery(registry)

    assert discovery["summary"]["registered_strategy_count"] == 2
    assert warnings == ["Duplicate strategy ID ignored: SWING-001"]


def test_malformed_registry_returns_safe_empty_discovery() -> None:
    discovery, warnings = build_dashboard_strategy_discovery({})

    assert discovery["summary"]["registered_strategy_count"] == 0
    assert discovery["strategies"] == []
    assert warnings == ["Enterprise registry does not contain strategy_plugins."]
    assert discovery["paper_trade_mode"] is True
    assert discovery["broker_execution_enabled"] is False
    assert discovery["capital_movement_enabled"] is False


def test_attach_does_not_mutate_dashboard_or_change_calculations() -> None:
    dashboard = {
        "enterprise_summary": {
            "portfolio_value": 12500.0,
            "projected_annual_income": 900.0,
        },
        "strategy_kpis": [{"strategy_id": "DIVIDEND-001", "income": 900.0}],
    }
    before = deepcopy(dashboard)
    discovery, _ = build_dashboard_strategy_discovery(_registry())

    enriched = attach_dashboard_strategy_discovery(dashboard, discovery)

    assert dashboard == before
    assert enriched["enterprise_summary"] == before["enterprise_summary"]
    assert enriched["strategy_kpis"] == before["strategy_kpis"]
    assert enriched["strategy_discovery"]["summary"]["registered_strategy_count"] == 2
    assert enriched["strategy_discovery"]["read_only"] is True


def test_executive_and_investor_payloads_receive_identical_discovery() -> None:
    discovery, _ = build_dashboard_strategy_discovery(_registry())
    executive = attach_dashboard_strategy_discovery(
        {"dashboard_type": "EXECUTIVE"}, discovery
    )
    investor = attach_dashboard_strategy_discovery(
        {"dashboard_type": "INVESTOR"}, discovery
    )

    assert executive["strategy_discovery"] == investor["strategy_discovery"]
