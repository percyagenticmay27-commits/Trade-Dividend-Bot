from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.dividend_bot.dividend_strategy_registry import (
    active_strategies_for_pair,
    ensure_strategy_registry,
    load_strategy_registry,
)


def test_registry_initializes_only_real_a_and_b_definitions(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    rows = ensure_strategy_registry(path)
    assert [row["strategy_id"] for row in rows] == ["STRATEGY_A", "STRATEGY_B"]
    assert rows[0]["strategy_role"] == "PRODUCTION_BASELINE"
    assert rows[1]["strategy_role"] == "TEST_CANDIDATE"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["paper_trade_mode"] is True
    assert payload["broker_execution_enabled"] is False
    assert payload["capital_movement_enabled"] is False


def test_registry_preserves_future_strategy_without_inventing_rules(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    ensure_strategy_registry(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["strategies"].append({
        "strategy_id": "STRATEGY_C",
        "display_name": "Strategy C",
        "strategy_role": "TEST_CANDIDATE",
        "lifecycle_status": "ACTIVE",
        "version": "1.0",
        "description": "Explicit test fixture strategy.",
        "signal_key": "strategy_c",
        "buy_signal_field": "buy_ready",
        "sell_signal_field": "sell_ready",
        "eligible_pairs": ["AMDW / AMDL"],
        "promotion_eligible": True,
    })
    path.write_text(json.dumps(payload), encoding="utf-8")

    rows = ensure_strategy_registry(path)

    assert [row["strategy_id"] for row in rows] == [
        "STRATEGY_A",
        "STRATEGY_B",
        "STRATEGY_C",
    ]
    assert [row["strategy_id"] for row in active_strategies_for_pair(
        "AMDW / AMDL", path=path
    )] == ["STRATEGY_A", "STRATEGY_B", "STRATEGY_C"]
    assert [row["strategy_id"] for row in active_strategies_for_pair(
        "OTHER / PAIR", path=path
    )] == ["STRATEGY_A", "STRATEGY_B"]


def test_registry_rejects_incomplete_future_strategy(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps({"strategies": [{"strategy_id": "STRATEGY_C"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing fields"):
        load_strategy_registry(path)
