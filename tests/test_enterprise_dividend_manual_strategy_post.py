from urllib.parse import urlencode

import pytest

from src.dividend_bot.enterprise_dividend_manual_strategy_post import (
    parse_dividend_manual_strategy_form,
    submit_dividend_manual_strategy_form,
)
from src.dividend_bot.dividend_strategy_registry import (
    load_strategy_registry,
)


def _body(**overrides):
    values = {
        "strategy_id": "STRATEGY_C",
        "display_name": "Strategy C",
        "pair": "AMDW / AMDL",
        "description": "AMD pair research challenger.",
        "entry_logic": "AND",
        "entry_rule_left": "PRICE",
        "entry_rule_operator": ">",
        "entry_rule_right": "EMA20",
        "exit_logic": "AND",
        "exit_rule_left": "PRICE",
        "exit_rule_operator": "<",
        "exit_rule_right": "EMA20",
    }

    values.update(overrides)

    return urlencode(values, doseq=True).encode("utf-8")


def test_parser_builds_dividend_owned_submission():
    result = parse_dividend_manual_strategy_form(_body())

    assert result["strategy_id"] == "STRATEGY_C"
    assert result["display_name"] == "Strategy C"
    assert result["pair"] == "AMDW / AMDL"

    assert result["entry_logic"] == "AND"
    assert result["entry_conditions"] == [
        {
            "left": "PRICE",
            "operator": ">",
            "right": "EMA20",
        }
    ]

    assert result["exit_conditions"] == [
        {
            "left": "PRICE",
            "operator": "<",
            "right": "EMA20",
        }
    ]

    assert result["paper_trade_mode"] is True


def test_submit_persists_only_through_dividend_intake(tmp_path):
    registry = tmp_path / "dividend_strategy_registry.json"

    response = submit_dividend_manual_strategy_form(
        _body(),
        registry_path=registry,
    )

    assert response["ok"] is True
    assert response["paper_trade_mode"] is True
    assert response["shadow_only"] is True
    assert response["live_trading_enabled"] is False
    assert response["broker_execution_enabled"] is False
    assert response["capital_movement_enabled"] is False
    assert response["automatic_activation_allowed"] is False

    rows = load_strategy_registry(registry)

    strategy = next(
        row
        for row in rows
        if row["strategy_id"] == "STRATEGY_C"
    )

    assert strategy["strategy_role"] == "TEST_CANDIDATE"
    assert strategy["eligible_pairs"] == ["AMDW / AMDL"]
    assert strategy["manual_definition"]["entry_logic"] == "AND"


def test_submit_rejects_builtin_strategy_overwrite(tmp_path):
    registry = tmp_path / "dividend_strategy_registry.json"

    with pytest.raises(ValueError):
        submit_dividend_manual_strategy_form(
            _body(strategy_id="STRATEGY_A"),
            registry_path=registry,
        )


def test_submit_requires_entry_rule(tmp_path):
    registry = tmp_path / "dividend_strategy_registry.json"

    body = urlencode(
        {
            "strategy_id": "STRATEGY_C",
            "display_name": "Strategy C",
            "pair": "AMDW / AMDL",
            "entry_logic": "AND",
        }
    ).encode("utf-8")

    with pytest.raises(
        ValueError,
        match="at least one Dividend entry rule",
    ):
        submit_dividend_manual_strategy_form(
            body,
            registry_path=registry,
        )


def test_parser_rejects_partial_rule():
    with pytest.raises(
        ValueError,
        match="requires source, operator, and value",
    ):
        parse_dividend_manual_strategy_form(
            _body(entry_rule_right="")
        )
