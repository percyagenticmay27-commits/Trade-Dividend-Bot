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


def test_register_test_strategy_adds_pair_scoped_manual_candidate(tmp_path):
    from src.dividend_bot.dividend_strategy_registry import (
        load_strategy_registry,
        register_test_strategy,
    )

    path = tmp_path / "dividend_strategy_registry.json"

    result = register_test_strategy(
        {
            "strategy_id": "STRATEGY_C",
            "display_name": "Strategy C",
            "eligible_pairs": ["AMDW / AMDL"],
            "description": "Research challenger for AMD pair.",
            "manual_definition": {
                "timeframe": "4H",
                "entry_rules": [
                    {
                        "left": "close",
                        "operator": ">",
                        "right": "ema",
                        "period": 14,
                    }
                ],
            },
        },
        path=path,
    )

    assert result["strategy_id"] == "STRATEGY_C"
    assert result["strategy_role"] == "TEST_CANDIDATE"
    assert result["eligible_pairs"] == ["AMDW / AMDL"]
    assert result["manual_strategy"] is True
    assert result["paper_trade_mode"] is True
    assert result["broker_execution_enabled"] is False
    assert result["capital_movement_enabled"] is False

    rows = load_strategy_registry(path)
    assert [row["strategy_id"] for row in rows] == [
        "STRATEGY_A",
        "STRATEGY_B",
        "STRATEGY_C",
    ]


def test_register_test_strategy_cannot_overwrite_builtin_primary(tmp_path):
    from src.dividend_bot.dividend_strategy_registry import (
        register_test_strategy,
    )

    path = tmp_path / "dividend_strategy_registry.json"

    import pytest

    with pytest.raises(ValueError, match="protected built-in"):
        register_test_strategy(
            {
                "strategy_id": "STRATEGY_A",
                "display_name": "Fake Strategy A",
                "eligible_pairs": ["AMDW / AMDL"],
            },
            path=path,
        )


def test_register_test_strategy_updates_same_manual_strategy_without_duplicates(
    tmp_path,
):
    from src.dividend_bot.dividend_strategy_registry import (
        load_strategy_registry,
        register_test_strategy,
    )

    path = tmp_path / "dividend_strategy_registry.json"

    register_test_strategy(
        {
            "strategy_id": "STRATEGY_C",
            "display_name": "Strategy C",
            "eligible_pairs": ["AMDW / AMDL"],
        },
        path=path,
    )

    register_test_strategy(
        {
            "strategy_id": "STRATEGY_C",
            "display_name": "Strategy C Revised",
            "eligible_pairs": ["AMDW / AMDL"],
        },
        path=path,
    )

    rows = load_strategy_registry(path)

    strategy_c = [
        row
        for row in rows
        if row["strategy_id"] == "STRATEGY_C"
    ]

    assert len(strategy_c) == 1
    assert strategy_c[0]["display_name"] == "Strategy C Revised"
