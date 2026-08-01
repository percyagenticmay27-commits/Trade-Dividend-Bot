"""Read-only strategy-discovery metadata for Enterprise dashboard consumers.

This module enriches already-built dashboard payloads with registry-discovery
metadata. It does not change dashboard calculations, allocations, governance,
capital state, broker state, or strategy execution.
"""
from __future__ import annotations

from typing import Any, Mapping

from src.dividend_bot.enterprise_strategy_discovery import (
    discover_registered_strategies,
    summarize_strategy_discovery,
)

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True


def build_dashboard_strategy_discovery(
    registry: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Build the authoritative discovery document used by both dashboards."""
    strategies, warnings = discover_registered_strategies(registry)
    summary = summarize_strategy_discovery(strategies)
    return {
        "schema_version": "1.0",
        "source": "ENTERPRISE_STRATEGY_DISCOVERY",
        "scope": "ALL_REGISTERED_STRATEGIES",
        "summary": summary,
        "strategies": [
            {
                "strategy_id": item["strategy_id"],
                "display_name": item["display_name"],
                "strategy_type": item["strategy_type"],
                "lifecycle_status": item["lifecycle_status"],
                "runtime_status": item["runtime_status"],
                "health_status": item["health_status"],
                "readiness": item["readiness"],
                "enabled": item["enabled"],
                "paper_trade_mode": item["paper_trade_mode"],
                "paper_compatible": item["paper_compatible"],
                "advisory_only": item["advisory_only"],
                "reporting_only": item["reporting_only"],
            }
            for item in strategies
        ],
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "read_only": True,
    }, warnings


def attach_dashboard_strategy_discovery(
    dashboard: Mapping[str, Any],
    discovery: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a copied dashboard payload with discovery metadata attached.

    The existing dashboard object is not mutated. Existing builder fields and
    calculations remain authoritative and unchanged.
    """
    enriched = dict(dashboard)
    summary = discovery.get("summary")
    strategies = discovery.get("strategies")
    enriched["strategy_discovery"] = {
        "source": str(discovery.get("source", "ENTERPRISE_STRATEGY_DISCOVERY")),
        "scope": str(discovery.get("scope", "ALL_REGISTERED_STRATEGIES")),
        "summary": dict(summary) if isinstance(summary, Mapping) else {},
        "strategies": list(strategies) if isinstance(strategies, list) else [],
        "read_only": True,
    }
    return enriched
