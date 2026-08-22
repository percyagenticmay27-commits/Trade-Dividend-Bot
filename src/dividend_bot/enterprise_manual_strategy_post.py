"""Parse and submit the SWING-001 manual strategy form.

This host-side adapter never writes Swing storage itself; validated persistence
remains owned by the Swing intake transport.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping
from urllib.parse import parse_qs

from .enterprise_manual_strategy_transport import submit_manual_strategy_to_swing

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False

Transport = Callable[[Mapping[str, Any]], dict[str, Any]]


def _scalar(values: dict[str, list[str]], name: str, default: str = "") -> str:
    items = values.get(name) or []
    return items[0].strip() if items else default


def _truthy(value: str, default: bool = False) -> bool:
    if not value:
        return default
    return value.lower() not in {"0", "false", "off", "no"}


def _coerce_rule_value(raw: str, operator: str) -> float | str | list[float]:
    value = raw.strip()
    if operator == "between":
        parts = [item.strip() for item in value.split(",") if item.strip()]
        if len(parts) != 2:
            raise ValueError("between rule values must contain minimum,maximum")
        return [float(parts[0]), float(parts[1])]
    try:
        return float(value)
    except ValueError:
        return value.lower()


def _rule_rows(values: dict[str, list[str]], prefix: str) -> list[dict[str, Any]]:
    fields = {
        "left": values.get(f"{prefix}_left", []),
        "operator": values.get(f"{prefix}_operator", []),
        "right": values.get(f"{prefix}_right", []),
        "period": values.get(f"{prefix}_period", []),
        "factor": values.get(f"{prefix}_factor", []),
        "smoothing": values.get(f"{prefix}_smoothing", []),
        "price_source": values.get(f"{prefix}_price_source", []),
        "label": values.get(f"{prefix}_label", []),
    }
    count = max((len(items) for items in fields.values()), default=0)
    rows: list[dict[str, Any]] = []
    for index in range(count):
        raw = {name: (items[index].strip() if index < len(items) else "") for name, items in fields.items()}
        if not any(raw.values()):
            continue
        if not raw["left"] or not raw["operator"] or not raw["right"]:
            raise ValueError(f"{prefix} rule requires source, operator, and value")
        row: dict[str, Any] = {
            "left": raw["left"].lower(),
            "operator": raw["operator"],
            "right": _coerce_rule_value(raw["right"], raw["operator"]),
        }
        if raw["period"]:
            row["period"] = int(raw["period"])
        if raw["factor"]:
            row["factor"] = float(raw["factor"])
        if raw["smoothing"]:
            row["smoothing"] = raw["smoothing"].upper()
        if raw["price_source"]:
            row["price_source"] = raw["price_source"].upper()
        if raw["label"]:
            row["label"] = raw["label"]
        rows.append(row)
    return rows


def parse_manual_strategy_form(body: bytes) -> dict[str, Any]:
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("manual strategy form must be UTF-8") from exc
    values = parse_qs(text, keep_blank_values=True, strict_parsing=False)

    assignment_mode = _scalar(values, "assignment_mode", "DIRECT").upper()
    if assignment_mode not in {"DIRECT", "SHADOW"}:
        raise ValueError("assignment_mode must be DIRECT or SHADOW")

    conditional_enabled = _truthy(_scalar(values, "conditional_exit_enabled"), False)
    conditional_rules = _rule_rows(values, "conditional_exit_rule")
    conditional_exits: list[dict[str, Any]] = []
    if conditional_enabled:
        if not conditional_rules:
            raise ValueError("conditional exit is enabled but no conditional exit rule was supplied")
        conditional_exits.append(
            {
                "condition": {
                    "left": "position_pl",
                    "operator": ">",
                    "right": float(_scalar(values, "conditional_exit_pl_threshold", "0")),
                    "label": "Position P/L above activation threshold",
                },
                "rule_logic": "ANY",
                "rules": conditional_rules,
                "action": "SELL",
                "label": "Profit-conditional exit",
                "cooldown_bars": int(_scalar(values, "conditional_exit_cooldown_bars", "0")),
                "cooldown_unit": _scalar(values, "conditional_exit_cooldown_unit", "TRADING_DAY").upper(),
                "reset_entry_confirmation": True,
            }
        )

    submission: dict[str, Any] = {
        "strategy_id": _scalar(values, "strategy_id").upper(),
        "name": _scalar(values, "name"),
        "underlying_symbol": _scalar(values, "underlying_symbol").upper(),
        "assignment_mode": assignment_mode,
        "enabled": _truthy(_scalar(values, "enabled", "true"), True),
        "assignment_enabled": _truthy(_scalar(values, "assignment_enabled", "true"), True),
        "direction": _scalar(values, "direction", "LONG").upper(),
        "timeframe": _scalar(values, "timeframe").upper(),
        "session": _scalar(values, "session", "REGULAR_SESSION"),
        "number_of_entries": int(_scalar(values, "number_of_entries", "1")),
        "rule_logic": _scalar(values, "rule_logic", "ALL").upper(),
        "rules": _rule_rows(values, "entry_rule"),
        "confirmation_bars": int(_scalar(values, "confirmation_bars", "1")),
        "regime_logic": _scalar(values, "regime_logic", "ALL").upper(),
        "regime_filters": _rule_rows(values, "regime_rule"),
        "normal_exit_logic": _scalar(values, "normal_exit_logic", "ANY").upper(),
        "normal_exit_rules": _rule_rows(values, "normal_exit_rule"),
        "conditional_exits": conditional_exits,
        "exit_policy_id": _scalar(values, "exit_policy_id") or None,
        "paper_trade_mode": True,
    }
    return submission


def submit_manual_strategy_form(body: bytes, *, transport: Transport = submit_manual_strategy_to_swing) -> dict[str, Any]:
    submission = parse_manual_strategy_form(body)
    if not submission["strategy_id"] or not submission["name"] or not submission["underlying_symbol"]:
        raise ValueError("strategy_id, name, and underlying_symbol are required")
    if not submission["rules"]:
        raise ValueError("at least one entry rule is required")
    response = transport(submission)
    if response.get("paper_trade_mode") is not True or response.get("ok") is not True:
        raise RuntimeError("Swing manual strategy transport did not return a valid paper-only success")
    return response
