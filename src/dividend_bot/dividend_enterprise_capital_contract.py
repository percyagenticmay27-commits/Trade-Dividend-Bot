"""Read and apply the Enterprise paper-capital contract for DIVIDEND-001.

The Enterprise AI CIO owns strategy allocation. The Dividend paper simulator must
therefore size its paper state from the host allocation rather than silently using
the legacy $500 research baseline. This module performs paper-only accounting
normalization; it never moves broker capital or places orders.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

STRATEGY_ID = "DIVIDEND-001"
LEGACY_BASELINE_CAPITAL = 500.0
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _canonical_id(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("_", "-")
    if raw in {"dividend", "dividend-001"}:
        return STRATEGY_ID
    return str(value or "").strip()


def read_enterprise_dividend_allocation(
    path: str | Path = "state/paper_cash_account.json",
) -> float | None:
    """Return the host-owned DIVIDEND-001 allocation when explicitly reported."""
    source = Path(path)
    if not source.is_file():
        return None
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, Mapping):
        return None

    for key in ("strategy_allocations", "allocations", "allocated_by_strategy"):
        allocations = payload.get(key)
        if not isinstance(allocations, Mapping):
            continue
        for strategy_id, value in allocations.items():
            if _canonical_id(strategy_id) == STRATEGY_ID:
                return _number(value)
    return None


def scale_paper_state_to_allocation(
    state: Mapping[str, Any],
    target_allocation: float,
) -> tuple[dict[str, Any], float]:
    """Return a copy of paper state resized to the Enterprise strategy allocation.

    Resizing is an administrative paper-capital normalization, not a trade. Share
    quantities, SGOV balances, pending distributions, and cumulative distributions
    scale proportionally so economic percentages remain unchanged. Trade history is
    intentionally not rewritten.
    """
    target = _number(target_allocation)
    if target is None:
        raise ValueError("target_allocation must be positive")
    result = dict(state)
    current = _number(result.get("enterprise_capital_contract_amount"))
    if current is None:
        current = _number(result.get("starting_capital")) or LEGACY_BASELINE_CAPITAL
    factor = target / current

    pairs = result.get("pairs")
    if isinstance(pairs, Mapping) and abs(factor - 1.0) > 1e-12:
        normalized_pairs: dict[str, Any] = {}
        for pair_name, raw in pairs.items():
            entry = dict(raw) if isinstance(raw, Mapping) else raw
            if isinstance(entry, dict):
                for key in (
                    "a_shares", "b_shares", "sgov_balance", "a_sgov_balance",
                    "b_sgov_balance", "pending_dividend_a", "pending_dividend_b",
                    "total_dividends_received", "capital_bucket",
                ):
                    value = entry.get(key)
                    try:
                        if value is not None:
                            entry[key] = float(value) * factor
                    except (TypeError, ValueError):
                        pass
            normalized_pairs[str(pair_name)] = entry
        result["pairs"] = normalized_pairs

    result["starting_capital"] = target
    result["enterprise_capital_contract_amount"] = target
    result["enterprise_capital_contract_source"] = "state/paper_cash_account.json"
    result["enterprise_capital_contract_strategy_id"] = STRATEGY_ID
    result["enterprise_capital_scale_factor"] = factor
    result["enterprise_capital_contract_applied"] = True
    result["paper_only"] = True
    return result, factor
