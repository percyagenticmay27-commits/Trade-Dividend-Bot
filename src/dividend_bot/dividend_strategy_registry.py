"""Paper-only registry for Dividend pair management strategies."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False

DEFAULT_STRATEGY_REGISTRY_PATH = Path("state/dividend_strategy_registry.json")

BUILTIN_STRATEGIES = (
    {
        "strategy_id": "STRATEGY_A",
        "display_name": "Strategy A",
        "strategy_role": "PRODUCTION_BASELINE",
        "lifecycle_status": "ACTIVE",
        "version": "1.0",
        "description": "Default production pair timing strategy.",
        "signal_key": "strategy_a",
        "buy_signal_field": "buy_trigger",
        "sell_signal_field": "sell_trigger",
        "eligible_pairs": ["*"],
        "promotion_eligible": True,
    },
    {
        "strategy_id": "STRATEGY_B",
        "display_name": "Strategy B",
        "strategy_role": "TEST_CANDIDATE",
        "lifecycle_status": "ACTIVE",
        "version": "1.0",
        "description": "First shadow/test pair timing strategy.",
        "signal_key": "strategy_b",
        "buy_signal_field": "buy_eligible",
        "sell_signal_field": "sell_trigger",
        "eligible_pairs": ["*"],
        "promotion_eligible": True,
    },
)

_REQUIRED = {
    "strategy_id",
    "display_name",
    "strategy_role",
    "lifecycle_status",
    "version",
    "description",
    "signal_key",
    "buy_signal_field",
    "sell_signal_field",
    "eligible_pairs",
    "promotion_eligible",
}


def _validate(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for source in rows:
        row = dict(source)
        missing = sorted(_REQUIRED - set(row))
        if missing:
            raise ValueError(f"strategy registry row missing fields: {', '.join(missing)}")
        strategy_id = str(row["strategy_id"]).strip().upper()
        if not strategy_id or strategy_id in identifiers:
            raise ValueError("strategy registry IDs must be non-empty and unique")
        if not isinstance(row["eligible_pairs"], list):
            raise ValueError(f"{strategy_id} eligible_pairs must be a list")
        if row["promotion_eligible"] not in (True, False):
            raise ValueError(f"{strategy_id} promotion_eligible must be boolean")
        identifiers.add(strategy_id)
        row["strategy_id"] = strategy_id
        validated.append(row)
    return validated


def load_strategy_registry(path: str | Path) -> list[dict[str, Any]]:
    file = Path(path)
    if not file.is_file():
        return []
    payload = json.loads(file.read_text(encoding="utf-8"))
    rows = payload.get("strategies") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        raise ValueError("strategy registry must contain a strategies list")
    return _validate([row for row in rows if isinstance(row, Mapping)])


def ensure_strategy_registry(
    path: str | Path = DEFAULT_STRATEGY_REGISTRY_PATH,
) -> list[dict[str, Any]]:
    """Create A/B defaults once while preserving future registered strategies."""
    file = Path(path)
    rows = load_strategy_registry(file)
    by_id = {row["strategy_id"]: row for row in rows}
    changed = not file.is_file()
    for builtin in BUILTIN_STRATEGIES:
        if builtin["strategy_id"] not in by_id:
            rows.append(dict(builtin))
            changed = True
    rows = _validate(rows)
    if changed:
        file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "paper_trade_mode": True,
            "live_trading_enabled": False,
            "broker_execution_enabled": False,
            "capital_movement_enabled": False,
            "strategies": rows,
        }
        temporary = file.with_suffix(file.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, file)
    return rows


def active_strategies_for_pair(
    pair: str,
    *,
    path: str | Path = DEFAULT_STRATEGY_REGISTRY_PATH,
) -> list[dict[str, Any]]:
    rows = ensure_strategy_registry(path)
    return [
        row
        for row in rows
        if str(row.get("lifecycle_status") or "").upper() == "ACTIVE"
        and (
            "*" in row.get("eligible_pairs", [])
            or pair in row.get("eligible_pairs", [])
        )
    ]
