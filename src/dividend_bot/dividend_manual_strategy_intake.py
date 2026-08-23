"""Validated paper-only intake for user-authored Dividend strategies.

Dividend owns validation and persistence. The Enterprise AI CIO may render
the form and submit requests, but it must not write the Dividend strategy
registry directly.

Manual strategies are research/shadow candidates only. This module cannot
place orders, move capital, enable broker execution, or automatically promote
a strategy.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping

from .dividend_manual_strategy_evaluator import SUPPORTED_OPERATORS
from .dividend_strategy_registry import (
    DEFAULT_STRATEGY_REGISTRY_PATH,
    register_test_strategy,
)


PAPER_TRADE_MODE = True
SHADOW_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
AUTO_PROMOTION_ENABLED = False

SUPPORTED_LOGIC = {"AND", "OR"}

# These are the technical operands currently exposed by the Dividend
# entry-score evidence and flattened by dividend_shadow_strategy_tracker.
SUPPORTED_OPERANDS = {
    "PRICE",
    "EMA20",
    "EMA50",
    "RSI14",
    "STOCH_K",
    "STOCH_D",
    "STOCH_RSI_K",
    "STOCH_RSI_D",
}


@dataclass(frozen=True)
class DividendManualStrategyIntakeResult:
    status: str
    strategy_id: str
    pair: str
    registry_path: str
    paper_trade_mode: bool = True
    shadow_only: bool = True


def _logic(value: object, field: str) -> str:
    result = str(value or "AND").strip().upper()
    if result not in SUPPORTED_LOGIC:
        raise ValueError(f"{field} must be AND or OR")
    return result


def _operand(value: object, field: str) -> object:
    if isinstance(value, (int, float)):
        return value

    text = str(value).strip()
    if not text:
        raise ValueError(f"{field} cannot be empty")

    # Numeric constants submitted as strings are accepted.
    try:
        return float(text)
    except ValueError:
        pass

    canonical = text.upper()
    if canonical not in SUPPORTED_OPERANDS:
        raise ValueError(
            f"{field} uses unsupported operand {canonical}"
        )
    return canonical


def _condition(raw: Mapping[str, Any], field: str) -> dict[str, Any]:
    missing = [
        name for name in ("left", "operator", "right")
        if raw.get(name) in (None, "")
    ]
    if missing:
        raise ValueError(
            f"{field} missing required fields: {', '.join(missing)}"
        )

    operator = str(raw["operator"]).strip().upper()
    if operator not in SUPPORTED_OPERATORS:
        raise ValueError(f"{field} uses unsupported operator {operator}")

    return {
        "left": _operand(raw["left"], f"{field}.left"),
        "operator": operator,
        "right": _operand(raw["right"], f"{field}.right"),
    }


def _conditions(value: object, field: str) -> list[dict[str, Any]]:
    if value in (None, []):
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a structured list")

    output: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise ValueError(f"{field}[{index}] must be an object")
        output.append(_condition(raw, f"{field}[{index}]"))
    return output


def apply_dividend_manual_strategy_submission(
    submission: Mapping[str, Any],
    *,
    registry_path: str | Path = DEFAULT_STRATEGY_REGISTRY_PATH,
) -> DividendManualStrategyIntakeResult:
    """Validate and persist one Dividend-owned manual shadow strategy."""

    forbidden = {
        "allocation",
        "allocation_amount",
        "allocated_capital",
        "capital_amount",
        "position_size",
        "live_trading_enabled",
        "broker_execution_enabled",
        "capital_movement_enabled",
        "promotion_eligible",
    } & set(submission)

    if forbidden:
        raise ValueError(
            "User submission cannot control Dividend-owned safety/capital "
            "fields: " + ", ".join(sorted(forbidden))
        )

    if submission.get("paper_trade_mode", True) is not True:
        raise ValueError("paper_trade_mode=True is mandatory")

    strategy_id = str(submission.get("strategy_id") or "").strip().upper()
    display_name = str(submission.get("display_name") or "").strip()
    pair = str(submission.get("pair") or "").strip().upper()

    if not strategy_id:
        raise ValueError("strategy_id is required")
    if not display_name:
        raise ValueError("display_name is required")
    if not pair:
        raise ValueError("pair is required")

    if strategy_id in {"STRATEGY_A", "STRATEGY_B"}:
        raise ValueError(
            f"{strategy_id} is a built-in strategy and cannot be overwritten"
        )

    entry_conditions = _conditions(
        submission.get("entry_conditions"),
        "entry_conditions",
    )
    exit_conditions = _conditions(
        submission.get("exit_conditions"),
        "exit_conditions",
    )

    if not entry_conditions:
        raise ValueError("at least one entry condition is required")

    manual_definition = {
        "entry_logic": _logic(
            submission.get("entry_logic", "AND"),
            "entry_logic",
        ),
        "entry_conditions": entry_conditions,
        "exit_logic": _logic(
            submission.get("exit_logic", "AND"),
            "exit_logic",
        ),
        "exit_conditions": exit_conditions,
    }

    register_test_strategy(
        {
            "strategy_id": strategy_id,
            "display_name": display_name,
            "eligible_pairs": [pair],
            "description": str(
                submission.get("description")
                or "User-authored Dividend shadow strategy."
            ).strip(),
            "manual_definition": manual_definition,
        },
        path=registry_path,
    )

    return DividendManualStrategyIntakeResult(
        status="REGISTERED",
        strategy_id=strategy_id,
        pair=pair,
        registry_path=str(registry_path),
    )


def result_payload(
    result: DividendManualStrategyIntakeResult,
) -> dict[str, Any]:
    return asdict(result)
