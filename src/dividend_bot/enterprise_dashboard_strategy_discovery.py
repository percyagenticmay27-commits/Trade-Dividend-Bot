"""Read-only strategy-discovery metadata for Enterprise dashboard consumers.

This module enriches already-built dashboard payloads with registry-discovery
metadata. It does not change dashboard calculations, allocations, governance,
capital state, broker state, or strategy execution.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

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
    """Return a copied dashboard with the canonical discovery document attached.

    The existing dashboard object is not mutated. Existing builder fields and
    calculations remain authoritative and unchanged. Every consumer receives
    the same complete discovery contract rather than a reconstructed subset.
    """
    enriched = dict(dashboard)
    enriched["strategy_discovery"] = dict(discovery)
    return enriched


def build_dashboard_refresh_consumer_payloads(
    *,
    registry: Mapping[str, Any],
    executive_dashboard: Mapping[str, Any],
    investor_dashboard: Mapping[str, Any],
    strategy_kpis: Sequence[Mapping[str, Any]] = (),
    kpi_warnings: Sequence[str] = (),
) -> tuple[dict[str, Any], list[str]]:
    """Build identical registry-discovery metadata for all refresh consumers.

    Dashboard calculations are accepted as already complete and are copied
    unchanged. The function creates one discovery document and publishes that
    same reporting view to the Executive Dashboard, Investor Dashboard, KPI
    artifact payload, and refresh summary.
    """
    discovery, discovery_warnings = build_dashboard_strategy_discovery(registry)
    summary = discovery.get("summary")
    normalized_summary = dict(summary) if isinstance(summary, Mapping) else {}
    normalized_kpis = [dict(item) for item in strategy_kpis]

    executive = attach_dashboard_strategy_discovery(
        executive_dashboard,
        discovery,
    )
    investor = attach_dashboard_strategy_discovery(
        investor_dashboard,
        discovery,
    )
    kpi_document = {
        "scope": "ALL_REGISTERED_STRATEGIES",
        "strategy_count": len(normalized_kpis),
        "strategy_discovery": dict(discovery),
        "strategy_discovery_summary": normalized_summary,
        "strategies": normalized_kpis,
        "warnings": [str(item) for item in kpi_warnings if item],
        "paper_trade_mode": True,
        "reporting_only": True,
        "read_only": True,
    }
    refresh_summary = {
        "source": "ENTERPRISE_STRATEGY_DISCOVERY",
        "scope": "ALL_REGISTERED_STRATEGIES",
        "summary": normalized_summary,
        "strategies": list(discovery.get("strategies", [])),
        "paper_trade_mode": True,
        "reporting_only": True,
        "read_only": True,
    }

    return {
        "strategy_discovery": discovery,
        "discovery": discovery,
        "executive_dashboard": executive,
        "investor_dashboard": investor,
        "strategy_kpi_document": kpi_document,
        "refresh_summary": refresh_summary,
    }, discovery_warnings
