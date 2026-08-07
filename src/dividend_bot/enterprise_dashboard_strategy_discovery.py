"""Read-only strategy-discovery metadata for Enterprise dashboard consumers.

This module enriches already-built dashboard payloads with registry-discovery
metadata. It does not change allocations, governance, capital state, broker state,
or strategy execution. When normalized per-strategy holdings evidence is already
available, it also publishes a read-only Enterprise holdings view so legacy
investor consumers do not fall back to UNKNOWN/$0 rows.
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


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
    """Return a copied dashboard with the canonical discovery document attached."""
    enriched = dict(dashboard)
    enriched["strategy_discovery"] = dict(discovery)
    return enriched


def build_enterprise_strategy_holdings_allocation(
    strategy_kpis: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Build a read-only Enterprise holdings view from normalized strategy KPIs.

    This is a consumer projection only. It never changes strategy allocations or
    holdings calculations. Rows without an authoritative symbol or market value
    are skipped rather than converted into UNKNOWN/$0 placeholders.
    """
    rows: list[dict[str, Any]] = []
    total_value = 0.0

    for strategy in strategy_kpis:
        if not isinstance(strategy, Mapping):
            continue
        strategy_id = str(strategy.get("strategy_id") or "").strip()
        holdings = strategy.get("holdings")
        if not isinstance(holdings, list):
            continue
        for holding in holdings:
            if not isinstance(holding, Mapping):
                continue
            symbol = str(
                holding.get("symbol")
                or holding.get("ticker")
                or holding.get("asset")
                or ""
            ).strip().upper()
            market_value = _number(
                holding.get("market_value")
                if holding.get("market_value") is not None
                else holding.get("position_value")
            )
            if not symbol or market_value is None or market_value < 0:
                continue
            row = dict(holding)
            row["symbol"] = symbol
            row["market_value"] = round(market_value, 2)
            row["strategy_id"] = strategy_id
            row["strategy_display_name"] = strategy.get("display_name")
            row["sector"] = str(
                holding.get("sector")
                or holding.get("theme")
                or holding.get("category")
                or "Unclassified"
            ).strip()
            rows.append(row)
            total_value += market_value

    if not rows:
        return None

    for row in rows:
        value = float(row["market_value"])
        row["allocation_percent"] = (
            round((value / total_value) * 100.0, 4) if total_value > 0 else 0.0
        )

    rows.sort(
        key=lambda row: (
            -float(row.get("market_value", 0.0)),
            str(row.get("strategy_id", "")),
            str(row.get("symbol", "")),
        )
    )
    return {
        "holding_count": len(rows),
        "total_position_value": round(total_value, 2),
        "largest_position_symbol": rows[0]["symbol"] if rows else None,
        "largest_position_percent": rows[0]["allocation_percent"] if rows else 0.0,
        "holdings": rows,
        "source": "NORMALIZED_STRATEGY_KPIS",
        "scope": "ALL_REGISTERED_STRATEGIES_WITH_HOLDINGS_EVIDENCE",
        "read_only": True,
    }


def build_dashboard_refresh_consumer_payloads(
    *,
    registry: Mapping[str, Any],
    executive_dashboard: Mapping[str, Any],
    investor_dashboard: Mapping[str, Any],
    strategy_kpis: Sequence[Mapping[str, Any]] = (),
    kpi_warnings: Sequence[str] = (),
) -> tuple[dict[str, Any], list[str]]:
    """Build identical registry-discovery metadata for all refresh consumers.

    Dashboard calculations are accepted as already complete. The function creates
    one discovery document and, when available, projects existing normalized
    strategy holdings into the legacy Enterprise investor allocation consumer.
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
    enterprise_allocation = build_enterprise_strategy_holdings_allocation(
        normalized_kpis
    )
    if enterprise_allocation is not None:
        investor["allocation"] = enterprise_allocation

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
