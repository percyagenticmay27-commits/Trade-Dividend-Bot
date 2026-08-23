from src.dividend_bot.dividend_manual_strategy_evaluator import (
    evaluate_condition,
    evaluate_manual_strategy,
    evaluate_rule_group,
)


def test_manual_strategy_can_reproduce_strategy_b_buy_logic():
    definition = {
        "strategy_id": "STRATEGY_C",
        "manual_definition": {
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
                },
            ],
        },
    }

    evidence = {
        "price": 105.0,
        "ema20": 100.0,
        "ema50": 95.0,
    }

    result = evaluate_manual_strategy(
        definition,
        evidence,
    )

    assert result["available"] is True
    assert result["strategy_id"] == "STRATEGY_C"
    assert result["buy_trigger"] is True
    assert result["sell_trigger"] is False
    assert result["paper_trade_mode"] is True
    assert result["shadow_only"] is True
    assert result["broker_execution_enabled"] is False
    assert result["capital_movement_enabled"] is False


def test_manual_strategy_can_reproduce_strategy_b_sell_logic():
    definition = {
        "strategy_id": "STRATEGY_C",
        "manual_definition": {
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
                },
            ],
        },
    }

    evidence = {
        "price": 90.0,
        "ema20": 100.0,
        "ema50": 95.0,
    }

    result = evaluate_manual_strategy(
        definition,
        evidence,
    )

    assert result["buy_trigger"] is False
    assert result["sell_trigger"] is True


def test_cross_above_uses_previous_values():
    evidence = {
        "stoch_rsi_k_previous": 40.0,
        "stoch_rsi_d_previous": 45.0,
        "stoch_rsi_k": 55.0,
        "stoch_rsi_d": 50.0,
    }

    condition = {
        "left": "STOCH_RSI_K",
        "operator": "CROSS_ABOVE",
        "right": "STOCH_RSI_D",
    }

    assert evaluate_condition(
        condition,
        evidence,
    ) is True


def test_cross_below_uses_previous_values():
    evidence = {
        "stoch_k_previous": 80.0,
        "stoch_d_previous": 70.0,
        "stoch_k": 60.0,
        "stoch_d": 65.0,
    }

    condition = {
        "left": "STOCH_K",
        "operator": "CROSS_BELOW",
        "right": "STOCH_D",
    }

    assert evaluate_condition(
        condition,
        evidence,
    ) is True


def test_missing_operand_fails_closed():
    condition = {
        "left": "PRICE",
        "operator": ">",
        "right": "EMA20",
    }

    assert evaluate_condition(
        condition,
        {"price": 100.0},
    ) is False


def test_rule_group_supports_and_and_or():
    evidence = {
        "price": 105.0,
        "ema20": 100.0,
        "ema50": 110.0,
    }

    rules = [
        {
            "left": "PRICE",
            "operator": ">",
            "right": "EMA20",
        },
        {
            "left": "PRICE",
            "operator": ">",
            "right": "EMA50",
        },
    ]

    assert evaluate_rule_group(
        rules,
        evidence,
        logic="AND",
    ) is False

    assert evaluate_rule_group(
        rules,
        evidence,
        logic="OR",
    ) is True


def test_definition_without_manual_rules_fails_closed():
    result = evaluate_manual_strategy(
        {"strategy_id": "STRATEGY_C"},
        {"price": 100.0},
    )

    assert result["available"] is False
    assert result["buy_trigger"] is False
    assert result["sell_trigger"] is False
    assert result["paper_trade_mode"] is True
    assert result["shadow_only"] is True


def test_shadow_tracker_flattens_existing_technical_evidence():
    from src.dividend_bot.dividend_shadow_strategy_tracker import (
        _manual_evidence,
    )

    signals = {
        "strategy_a": {
            "rsi14": 55.0,
            "rsi14_previous": 48.0,
            "stoch_oscillator": {
                "k": 60.0,
                "k_previous": 45.0,
                "d": 55.0,
                "d_previous": 50.0,
            },
            "stoch_rsi": {
                "k": 70.0,
                "k_previous": 40.0,
                "d": 60.0,
                "d_previous": 45.0,
            },
        },
        "strategy_b": {
            "price": 105.0,
            "ema20": 100.0,
            "ema50": 95.0,
        },
    }

    evidence = _manual_evidence(signals)

    assert evidence["price"] == 105.0
    assert evidence["ema20"] == 100.0
    assert evidence["ema50"] == 95.0
    assert evidence["rsi14"] == 55.0
    assert evidence["rsi14_previous"] == 48.0
    assert evidence["stoch_k"] == 60.0
    assert evidence["stoch_k_previous"] == 45.0
    assert evidence["stoch_rsi_k"] == 70.0
    assert evidence["stoch_rsi_k_previous"] == 40.0


def test_shadow_tracker_evaluates_manual_strategy_c():
    from src.dividend_bot.dividend_shadow_strategy_tracker import (
        _strategy_signal,
    )

    signals = {
        "strategy_a": {},
        "strategy_b": {
            "price": 105.0,
            "ema20": 100.0,
            "ema50": 95.0,
        },
    }

    definition = {
        "strategy_id": "STRATEGY_C",
        "manual_strategy": True,
        "manual_definition": {
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
            "exit_conditions": [
                {
                    "left": "PRICE",
                    "operator": "<",
                    "right": "EMA20",
                },
            ],
        },
    }

    buy, sell = _strategy_signal(signals, definition)

    assert buy is True
    assert sell is False


def test_shadow_tracker_preserves_builtin_strategy_b_path():
    from src.dividend_bot.dividend_shadow_strategy_tracker import (
        _strategy_signal,
    )

    signals = {
        "strategy_b": {
            "buy_eligible": True,
            "sell_trigger": False,
            "price": 105.0,
            "ema20": 100.0,
            "ema50": 95.0,
        },
    }

    definition = {
        "strategy_id": "STRATEGY_B",
        "signal_key": "strategy_b",
        "buy_signal_field": "buy_eligible",
        "sell_signal_field": "sell_trigger",
    }

    buy, sell = _strategy_signal(signals, definition)

    assert buy is True
    assert sell is False
