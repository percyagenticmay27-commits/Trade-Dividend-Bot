"""Generic paper-only evaluator for manually registered Dividend strategies.

This module evaluates declarative strategy rules against technical evidence.
It cannot place orders, move capital, enable live trading, or promote a
strategy into production.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


PAPER_TRADE_MODE = True
SHADOW_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False


SUPPORTED_OPERATORS = {
    ">",
    "<",
    ">=",
    "<=",
    "==",
    "CROSS_ABOVE",
    "CROSS_BELOW",
}


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve(
    operand: Any,
    evidence: Mapping[str, Any],
    *,
    previous: bool = False,
) -> float | None:
    """Resolve either a numeric literal or named technical operand."""
    if isinstance(operand, (int, float)):
        return float(operand)

    key = str(operand or "").strip().upper()

    if not key:
        return None

    # Numeric strings are valid constants.
    literal = _number(key)
    if literal is not None:
        return literal

    suffix = "_previous" if previous else ""

    aliases = {
        "PRICE": "price_previous" if previous else "price",
        "EMA20": "ema20_previous" if previous else "ema20",
        "EMA50": "ema50_previous" if previous else "ema50",
        "RSI14": "rsi14_previous" if previous else "rsi14",
        "STOCH_K": "stoch_k_previous" if previous else "stoch_k",
        "STOCH_D": "stoch_d_previous" if previous else "stoch_d",
        "STOCH_RSI_K": (
            "stoch_rsi_k_previous" if previous else "stoch_rsi_k"
        ),
        "STOCH_RSI_D": (
            "stoch_rsi_d_previous" if previous else "stoch_rsi_d"
        ),
    }

    field = aliases.get(key, key.lower() + suffix)
    return _number(evidence.get(field))


def evaluate_condition(
    condition: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> bool:
    left_name = condition.get("left")
    right_name = condition.get("right")
    operator = str(condition.get("operator") or "").strip().upper()

    if operator not in SUPPORTED_OPERATORS:
        return False

    left = _resolve(left_name, evidence)
    right = _resolve(right_name, evidence)

    if left is None or right is None:
        return False

    if operator == ">":
        return left > right
    if operator == "<":
        return left < right
    if operator == ">=":
        return left >= right
    if operator == "<=":
        return left <= right
    if operator == "==":
        return left == right

    previous_left = _resolve(left_name, evidence, previous=True)
    previous_right = _resolve(right_name, evidence, previous=True)

    if previous_left is None or previous_right is None:
        return False

    if operator == "CROSS_ABOVE":
        return previous_left <= previous_right and left > right

    if operator == "CROSS_BELOW":
        return previous_left >= previous_right and left < right

    return False


def evaluate_rule_group(
    conditions: Sequence[Mapping[str, Any]],
    evidence: Mapping[str, Any],
    *,
    logic: str = "AND",
) -> bool:
    """Evaluate a group using explicit AND/OR semantics."""
    rows = [
        condition
        for condition in conditions
        if isinstance(condition, Mapping)
    ]

    if not rows:
        return False

    results = [
        evaluate_condition(condition, evidence)
        for condition in rows
    ]

    if str(logic).upper() == "OR":
        return any(results)

    return all(results)


def evaluate_manual_strategy(
    definition: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate one declarative manual strategy without execution authority."""
    manual = definition.get("manual_definition")

    if not isinstance(manual, Mapping):
        return {
            "available": False,
            "reason": "NO_MANUAL_DEFINITION",
            "buy_trigger": False,
            "sell_trigger": False,
            "paper_trade_mode": True,
            "shadow_only": True,
        }

    entry_conditions = manual.get("entry_conditions", [])
    exit_conditions = manual.get("exit_conditions", [])

    if not isinstance(entry_conditions, list):
        entry_conditions = []

    if not isinstance(exit_conditions, list):
        exit_conditions = []

    buy = evaluate_rule_group(
        entry_conditions,
        evidence,
        logic=str(manual.get("entry_logic") or "AND"),
    )

    sell = evaluate_rule_group(
        exit_conditions,
        evidence,
        logic=str(manual.get("exit_logic") or "AND"),
    )

    return {
        "available": True,
        "strategy_id": str(definition.get("strategy_id") or ""),
        "buy_trigger": buy,
        "sell_trigger": sell,
        "entry_logic": str(manual.get("entry_logic") or "AND").upper(),
        "exit_logic": str(manual.get("exit_logic") or "AND").upper(),
        "paper_trade_mode": True,
        "shadow_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
    }
