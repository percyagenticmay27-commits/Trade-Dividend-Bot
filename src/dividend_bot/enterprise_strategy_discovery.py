"""Read-only strategy discovery for Enterprise AI CIO consumers.

This module treats the Enterprise service registry as the single source of truth
for which strategy plugins exist. It normalizes identity and status fields only;
it never imports plugin code, executes strategies, changes allocations, moves
capital, or writes broker state.
"""
from __future__ import annotations

from typing import Any, Mapping

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True


def _first(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return default


def discover_registered_strategies(
    registry: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return deterministic normalized records for every valid registry plugin.

    Malformed records and duplicate strategy IDs are skipped with warnings. A
    missing or malformed external strategy can therefore never remove a valid
    Dividend strategy already present in the registry.
    """
    raw_plugins = registry.get("strategy_plugins")
    if not isinstance(raw_plugins, list):
        return [], ["Enterprise registry does not contain strategy_plugins."]

    discovered: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()

    for index, plugin in enumerate(raw_plugins):
        if not isinstance(plugin, Mapping):
            warnings.append(f"strategy_plugins[{index}] is not an object and was ignored.")
            continue

        strategy_id = str(
            _first(plugin, "strategy_id", "plugin_id", "service_id", default="")
        ).strip()
        if not strategy_id:
            warnings.append(f"strategy_plugins[{index}] has no strategy identity and was ignored.")
            continue
        if strategy_id in seen_ids:
            warnings.append(f"Duplicate strategy ID ignored: {strategy_id}")
            continue
        seen_ids.add(strategy_id)

        display_name = str(
            _first(plugin, "display_name", "strategy_name", "name", default=strategy_id)
        ).strip() or strategy_id

        discovered.append(
            {
                "strategy_id": strategy_id,
                "display_name": display_name,
                "strategy_type": str(
                    _first(plugin, "strategy_type", "plugin_type", "bot_type", default="STRATEGY")
                ),
                "lifecycle_status": str(
                    _first(plugin, "lifecycle_status", "service_lifecycle", "status", default="UNKNOWN")
                ),
                "runtime_status": str(
                    _first(plugin, "runtime_status", "status", default="UNKNOWN")
                ),
                "health_status": str(
                    _first(plugin, "health_status", "health", default="UNKNOWN")
                ),
                "readiness": str(
                    _first(plugin, "readiness", "readiness_status", "status", default="UNKNOWN")
                ),
                "paper_trade_mode": bool(plugin.get("paper_trade_mode", False)),
                "paper_compatible": bool(plugin.get("paper_compatible", False)),
                "advisory_only": bool(plugin.get("advisory_only", False)),
                "reporting_only": bool(plugin.get("reporting_only", False)),
                "enabled": bool(plugin.get("enabled", True)),
                "plugin": dict(plugin),
            }
        )

    discovered.sort(key=lambda item: item["strategy_id"])
    return discovered, sorted(set(warnings))


def summarize_strategy_discovery(
    strategies: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a read-only discovery summary without changing registry schemas."""
    return {
        "registered_strategy_count": len(strategies),
        "enabled_strategy_count": sum(bool(item.get("enabled", True)) for item in strategies),
        "paper_compatible_strategy_count": sum(
            bool(item.get("paper_trade_mode")) and bool(item.get("paper_compatible"))
            for item in strategies
        ),
        "strategy_ids": [str(item.get("strategy_id")) for item in strategies],
        "paper_trade_mode": True,
        "reporting_only": True,
    }
