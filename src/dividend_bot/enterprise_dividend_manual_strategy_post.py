"""Parse and submit the DIVIDEND-001 manual shadow-strategy form.

Persistence remains owned by Dividend through
apply_dividend_manual_strategy_submission().

This adapter cannot place orders, move capital, enable live trading,
or automatically promote a strategy.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs

from .dividend_manual_strategy_intake import (
    apply_dividend_manual_strategy_submission,
    result_payload,
)
from .dividend_strategy_registry import (
    DEFAULT_STRATEGY_REGISTRY_PATH,
)


PAPER_TRADE_MODE = True
SHADOW_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
AUTO_PROMOTION_ENABLED = False


def _scalar(
    values: dict[str, list[str]],
    name: str,
    default: str = "",
) -> str:
    items = values.get(name) or []
    return items[0].strip() if items else default


def _coerce_operand(raw: str) -> float | str:
    value = raw.strip()

    try:
        return float(value)
    except ValueError:
        return value.upper()


def _rule_rows(
    values: dict[str, list[str]],
    prefix: str,
) -> list[dict[str, Any]]:
    lefts = values.get(f"{prefix}_left", [])
    operators = values.get(f"{prefix}_operator", [])
    rights = values.get(f"{prefix}_right", [])

    count = max(
        len(lefts),
        len(operators),
        len(rights),
        0,
    )

    rows: list[dict[str, Any]] = []

    for index in range(count):
        left = (
            lefts[index].strip()
            if index < len(lefts)
            else ""
        )
        operator = (
            operators[index].strip()
            if index < len(operators)
            else ""
        )
        right = (
            rights[index].strip()
            if index < len(rights)
            else ""
        )

        if not any((left, operator, right)):
            continue

        if not left or not operator or not right:
            raise ValueError(
                f"{prefix} rule requires source, operator, and value"
            )

        rows.append(
            {
                "left": left.upper(),
                "operator": operator.upper(),
                "right": _coerce_operand(right),
            }
        )

    return rows


def parse_dividend_manual_strategy_form(
    body: bytes,
) -> dict[str, Any]:
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(
            "Dividend manual strategy form must be UTF-8"
        ) from exc

    values = parse_qs(
        text,
        keep_blank_values=True,
        strict_parsing=False,
    )

    entry_logic = _scalar(
        values,
        "entry_logic",
        "AND",
    ).upper()

    exit_logic = _scalar(
        values,
        "exit_logic",
        "AND",
    ).upper()

    submission: dict[str, Any] = {
        "strategy_id": _scalar(
            values,
            "strategy_id",
        ).upper(),
        "display_name": _scalar(
            values,
            "display_name",
        ),
        "pair": _scalar(
            values,
            "pair",
        ).upper(),
        "description": _scalar(
            values,
            "description",
            "User-authored Dividend shadow strategy.",
        ),
        "entry_logic": entry_logic,
        "entry_conditions": _rule_rows(
            values,
            "entry_rule",
        ),
        "exit_logic": exit_logic,
        "exit_conditions": _rule_rows(
            values,
            "exit_rule",
        ),
        "paper_trade_mode": True,
    }

    return submission


def submit_dividend_manual_strategy_form(
    body: bytes,
    *,
    registry_path: str | Path = DEFAULT_STRATEGY_REGISTRY_PATH,
) -> dict[str, Any]:
    submission = parse_dividend_manual_strategy_form(body)

    if not submission["strategy_id"]:
        raise ValueError("strategy_id is required")

    if not submission["display_name"]:
        raise ValueError("display_name is required")

    if not submission["pair"]:
        raise ValueError("pair is required")

    if not submission["entry_conditions"]:
        raise ValueError(
            "at least one Dividend entry rule is required"
        )

    result = apply_dividend_manual_strategy_submission(
        submission,
        registry_path=registry_path,
    )

    payload = result_payload(result)

    if not isinstance(payload, Mapping):
        raise RuntimeError(
            "Dividend manual strategy intake returned invalid evidence"
        )

    if payload.get("paper_trade_mode") is not True:
        raise RuntimeError(
            "Dividend manual strategy intake did not preserve paper mode"
        )

    if payload.get("shadow_only") is not True:
        raise RuntimeError(
            "Dividend manual strategy intake did not preserve shadow-only mode"
        )

    return {
        "ok": True,
        "paper_trade_mode": True,
        "shadow_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
        "result": dict(payload),
    }
