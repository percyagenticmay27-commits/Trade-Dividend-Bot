"""Explicit migration helpers for pre-ownership Dividend paper positions.

This module never assigns Strategy A or Strategy B retroactively. It only marks
currently-open positions that predate strategy ownership as LEGACY_UNASSIGNED so
the conservative A+B consensus exit policy can manage them deterministically.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .dividend_strategy_ownership import LEGACY_UNASSIGNED

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False

BLOCKED_SOURCES = {
    "QUALIFIED_ENTRY_GATE",
    "ENTRY_GATE_UNRESOLVED",
    "WAIT_IN_SGOV",
    "CLOSED_TO_SGOV",
}


def _positive(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def mark_legacy_unassigned_open_positions(state: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return a migrated copy plus an audit trail of explicit legacy markers."""
    result = deepcopy(dict(state or {}))
    pairs = result.get("pairs")
    if not isinstance(pairs, dict):
        return result, []

    changes: list[dict[str, Any]] = []
    for pair, entry in pairs.items():
        if not isinstance(entry, dict):
            continue

        a_open = _positive(entry.get("a_shares"))
        b_open = _positive(entry.get("b_shares"))
        if not (a_open or b_open):
            continue

        source = str(entry.get("strategy_ownership_source") or "").strip().upper()
        current_owner = str(entry.get("strategy_owner") or "").strip().upper()

        # Existing/new ownership lifecycle states are authoritative and must never
        # be rewritten by the compatibility migration.
        if current_owner in {"STRATEGY_A", "STRATEGY_B", LEGACY_UNASSIGNED}:
            continue
        if source in BLOCKED_SOURCES:
            continue

        # Pair-level marker supports pair-managed positions and supplies a common
        # compatibility state for old positions lacking any ownership metadata.
        entry["strategy_owner"] = LEGACY_UNASSIGNED
        entry["strategy_ownership_source"] = "LEGACY_PRE_OWNERSHIP_POSITION"
        if a_open:
            entry["a_strategy_owner"] = LEGACY_UNASSIGNED
            entry["a_strategy_ownership_source"] = "LEGACY_PRE_OWNERSHIP_POSITION"
        if b_open:
            entry["b_strategy_owner"] = LEGACY_UNASSIGNED
            entry["b_strategy_ownership_source"] = "LEGACY_PRE_OWNERSHIP_POSITION"

        changes.append({
            "pair": str(pair),
            "a_open": a_open,
            "b_open": b_open,
            "strategy_owner": LEGACY_UNASSIGNED,
            "strategy_ownership_source": "LEGACY_PRE_OWNERSHIP_POSITION",
            "management_policy": "REQUIRE_STRATEGY_A_AND_B_SELL_CONSENSUS",
        })

    return result, changes
