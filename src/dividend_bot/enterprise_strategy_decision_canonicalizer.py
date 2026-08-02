"""Enterprise-side canonicalization for strategy-owned decision events.

Strategies publish domain-native evidence. This module translates supported aliases
and already-normalized records into the stable Enterprise Decision Journal input
shape. It does not calculate scores, select investments, or change strategy logic.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

MODULE_NAME = "enterprise_strategy_decision_canonicalizer"
MODULE_VERSION = "1.0.0"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False


def _copy_if_missing(target: dict[str, Any], field: str, source: Mapping[str, Any], *aliases: str) -> None:
    if target.get(field) not in (None, ""):
        return
    for alias in aliases:
        value = source.get(alias)
        if value not in (None, ""):
            target[field] = deepcopy(value)
            return


def _canonicalize_dividend(event: Mapping[str, Any]) -> dict[str, Any]:
    canonical = deepcopy(dict(event))
    ecosystem_value = event.get("ecosystem")
    nested = ecosystem_value if isinstance(ecosystem_value, Mapping) else {}

    # Accept compact strategy aliases and canonical nested journal records.
    if not isinstance(ecosystem_value, Mapping):
        _copy_if_missing(canonical, "ecosystem_id", event, "ecosystem")
        _copy_if_missing(canonical, "ecosystem_name", event, "ecosystem", "ecosystem_id")
    else:
        _copy_if_missing(canonical, "ecosystem_id", nested, "ecosystem_id", "id")
        _copy_if_missing(canonical, "ecosystem_name", nested, "ecosystem_name", "name", "ecosystem_id")

    _copy_if_missing(canonical, "ecosystem_mode", event, "ecosystem_node")
    _copy_if_missing(canonical, "ecosystem_mode", nested, "mode", "ecosystem_mode")

    for field in (
        "income_leg",
        "leverage_leg",
        "income_alternatives",
        "leverage_alternatives",
        "income_leg_reason",
        "leverage_leg_reason",
        "pair_compatibility_reason",
        "primary_instrument",
        "self_funding_reason",
        "alternatives",
    ):
        _copy_if_missing(canonical, field, nested, field)

    return canonical


def canonicalize_strategy_decision_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Return one canonical Enterprise input without mutating strategy evidence."""
    if not isinstance(event, Mapping):
        raise TypeError("event must be an object")
    kind = str(event.get("strategy_kind") or "").strip().upper()
    if kind == "DIVIDEND":
        return _canonicalize_dividend(event)
    return deepcopy(dict(event))
