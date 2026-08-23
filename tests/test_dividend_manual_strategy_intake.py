import pytest

from src.dividend_bot.dividend_manual_strategy_intake import (
    apply_dividend_manual_strategy_submission,
)
from src.dividend_bot.dividend_strategy_registry import (
    load_strategy_registry,
)


def _submission():
    return {
        "strategy_id": "STRATEGY_C",
        "display_name": "Strategy C",
        "pair": "AMDW / AMDL",
        "description": "AMD pair research challenger.",
        "entry_logic": "AND",
        "entry_conditions": [
            {
                "left": "PRICE",
                "operator": ">",
                "right": "EMA20",
            },
            {
                "left": "EMA20",
                "operator": ">",
                "right": "EMA50",
            },
        ],
        "exit_logic": "AND",
        "exit_conditions": [
            {
                "left": "PRICE",
                "operator": "<",
                "right": "EMA20",
            }
        ],
        "paper_trade_mode": True,
    }


def test_intake_registers_manual_strategy_as_pair_scoped_shadow_candidate(
    tmp_path,
):
    path = tmp_path / "dividend_strategy_registry.json"

    result = apply_dividend_manual_strategy_submission(
        _submission(),
        registry_path=path,
    )

    assert result.status == "REGISTERED"
    assert result.strategy_id == "STRATEGY_C"
    assert result.pair == "AMDW / AMDL"
    assert result.paper_trade_mode is True
    assert result.shadow_only is True

    rows = load_strategy_registry(path)

    strategy = next(
        row
        for row in rows
        if row["strategy_id"] == "STRATEGY_C"
    )

    assert strategy["strategy_role"] == "TEST_CANDIDATE"
    assert strategy["manual_strategy"] is True
    assert strategy["eligible_pairs"] == ["AMDW / AMDL"]

    manual = strategy["manual_definition"]

    assert manual["entry_logic"] == "AND"
    assert manual["exit_logic"] == "AND"
    assert len(manual["entry_conditions"]) == 2
    assert len(manual["exit_conditions"]) == 1


def test_intake_rejects_builtin_strategy_overwrite(tmp_path):
    submission = _submission()
    submission["strategy_id"] = "STRATEGY_A"

    with pytest.raises(ValueError, match="built-in"):
        apply_dividend_manual_strategy_submission(
            submission,
            registry_path=tmp_path / "registry.json",
        )


def test_intake_rejects_live_mode(tmp_path):
    submission = _submission()
    submission["paper_trade_mode"] = False

    with pytest.raises(ValueError, match="paper_trade_mode=True"):
        apply_dividend_manual_strategy_submission(
            submission,
            registry_path=tmp_path / "registry.json",
        )


def test_intake_rejects_user_controlled_capital(tmp_path):
    submission = _submission()
    submission["allocation_amount"] = 5000

    with pytest.raises(
        ValueError,
        match="cannot control Dividend-owned safety/capital",
    ):
        apply_dividend_manual_strategy_submission(
            submission,
            registry_path=tmp_path / "registry.json",
        )


def test_intake_rejects_unsupported_operand(tmp_path):
    submission = _submission()
    submission["entry_conditions"] = [
        {
            "left": "ADX",
            "operator": ">",
            "right": 20,
        }
    ]

    with pytest.raises(ValueError, match="unsupported operand ADX"):
        apply_dividend_manual_strategy_submission(
            submission,
            registry_path=tmp_path / "registry.json",
        )


def test_intake_rejects_unsupported_operator(tmp_path):
    submission = _submission()
    submission["entry_conditions"] = [
        {
            "left": "PRICE",
            "operator": "APPROX",
            "right": "EMA20",
        }
    ]

    with pytest.raises(ValueError, match="unsupported operator"):
        apply_dividend_manual_strategy_submission(
            submission,
            registry_path=tmp_path / "registry.json",
        )


def test_intake_requires_entry_rule(tmp_path):
    submission = _submission()
    submission["entry_conditions"] = []

    with pytest.raises(
        ValueError,
        match="at least one entry condition",
    ):
        apply_dividend_manual_strategy_submission(
            submission,
            registry_path=tmp_path / "registry.json",
        )
