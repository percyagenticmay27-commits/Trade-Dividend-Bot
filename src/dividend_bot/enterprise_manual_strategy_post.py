"""Parse and submit the SWING-001 manual strategy form.

This module is the host-side POST adapter only. It never writes Swing storage
itself; validated persistence remains owned by the Swing intake transport.
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
        return value


def _rule_rows(values: dict[str, list[str]], prefix: str) -> list[dict[str, Any]]:
    lefts = values.get(f"{prefix}_left", [])
    operators = values.get(f"{prefix}_operator", [])
    rights = values.get(f"{prefix}_right", [])
    periods = values.get(f"{prefix}_period", [])
    labels = values.get(f"{prefix}_label", [])
    count = max(len(lefts), len(operators), len(rights), len(periods), len(labels), 0)
    rows: list[dict[str, Any]] = []
    for index in range(count):
        left = lefts[index].strip() if index < len(lefts) else ""
        operator = operators[index].strip() if index < len(operators) else ""
        right_raw = rights[index].strip() if index < len(rights) else ""
        period_raw = periods[index].strip() if index < len(periods) else ""
        label = labels[index].strip() if index < len(labels) else ""
        if not any((left, operator, right_raw, period_raw, label)):
            continue
        if not left or not operator or not right_raw:
            raise ValueError(f"{prefix} rule requires source, operator, and value")
        row: dict[str, Any] = {
            "left": left,
            "operator": operator,
            "right": _coerce_rule_value(right_raw, operator),
        }
        if period_raw:
            row["period"] = int(period_raw)
        if label:
            row["label"] = label
        rows.append(row)
    return rows


def parse_manual_strategy_form(body: bytes) -> dict[str, Any]:
    """Convert one application/x-www-form-urlencoded form body to Swing JSON."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("manual strategy form must be UTF-8") from exc
    values = parse_qs(text, keep_blank_values=True, strict_parsing=False)

    confirmation_text = _scalar(values, "confirmation")
    reentry_text = _scalar(values, "reentry_cooldown")
    assignment_mode = _scalar(values, "assignment_mode", "DIRECT").upper()
    if assignment_mode not in {"DIRECT", "SHADOW"}:
        raise ValueError("assignment_mode must be DIRECT or SHADOW")
    submission: dict[str, Any] = {
        "strategy_id": _scalar(values, "strategy_id").upper(),
        "name": _scalar(values, "name"),
        "underlying_symbol": _scalar(values, "underlying_symbol").upper(),
        "assignment_mode": assignment_mode,
        "enabled": _scalar(values, "enabled", "true").lower() not in {"0", "false", "off", "no"},
        "assignment_enabled": _scalar(values, "assignment_enabled", "true").lower() not in {"0", "false", "off", "no"},
        "direction": _scalar(values, "direction", "LONG").upper(),
        "timeframe": _scalar(values, "timeframe").upper(),
        "session": _scalar(values, "session", "REGULAR_SESSION"),
        "number_of_entries": int(_scalar(values, "number_of_entries", "1")),
        "rule_logic": _scalar(values, "rule_logic", "ALL").upper(),
        "rules": _rule_rows(values, "entry_rule"),
        "regime_logic": _scalar(values, "regime_logic", "ALL").upper(),
        "regime_filters": _rule_rows(values, "regime_rule"),
        "exit_policy_id": _scalar(values, "exit_policy_id") or None,
        "paper_trade_mode": True,
    }
    if confirmation_text:
        submission["confirmation"] = {"description": confirmation_text}
    if reentry_text:
        submission["reentry_cooldown"] = {"description": reentry_text}
    return submission


def submit_manual_strategy_form(
    body: bytes,
    *,
    transport: Transport = submit_manual_strategy_to_swing,
) -> dict[str, Any]:
    """Parse one host form submission and delegate it to Swing-owned intake."""
    submission = parse_manual_strategy_form(body)
    if not submission["strategy_id"] or not submission["name"] or not submission["underlying_symbol"]:
        raise ValueError("strategy_id, name, and underlying_symbol are required")
    if not submission["rules"]:
        raise ValueError("at least one entry rule is required")
    response = transport(submission)
    if response.get("paper_trade_mode") is not True or response.get("ok") is not True:
        raise RuntimeError("Swing manual strategy transport did not return a valid paper-only success")
    return response
