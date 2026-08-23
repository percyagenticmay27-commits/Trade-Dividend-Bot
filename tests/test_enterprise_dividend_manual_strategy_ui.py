from src.dividend_bot.enterprise_dividend_manual_strategy_ui import (
    dividend_manual_strategy_ui_css,
    render_dividend_manual_strategy_panel,
)


def test_dividend_manual_strategy_form_is_shadow_only():
    output = render_dividend_manual_strategy_panel()

    assert "Dividend Manual Strategy" in output
    assert "PAPER / SHADOW ONLY" in output
    assert "TEST_CANDIDATE" in output
    assert "Execution:</strong> NONE" in output
    assert "Capital Movement:</strong> NONE" in output
    assert "Automatic Promotion:</strong> DISABLED" in output
    assert "Save Shadow Strategy" in output


def test_dividend_manual_strategy_form_posts_to_dividend_route():
    output = render_dividend_manual_strategy_panel()

    assert (
        "action='/strategy/dividend-manual-entry'"
        in output
    )

    assert "/strategy/manual-entry" not in output
    assert "/strategy/shadow-promote" not in output


def test_dividend_manual_strategy_form_exposes_supported_operands():
    output = render_dividend_manual_strategy_panel()

    for operand in (
        "PRICE",
        "EMA20",
        "EMA50",
        "RSI14",
        "STOCH_K",
        "STOCH_D",
        "STOCH_RSI_K",
        "STOCH_RSI_D",
    ):
        assert operand in output


def test_dividend_manual_strategy_form_has_dynamic_rules():
    output = render_dividend_manual_strategy_panel()

    assert "data-add-dividend-rule='entry_rule'" in output
    assert "data-add-dividend-rule='exit_rule'" in output
    assert "data-remove-dividend-rule='entry_rule'" in output
    assert "data-remove-dividend-rule='exit_rule'" in output


def test_dividend_manual_strategy_css_is_available():
    css = dividend_manual_strategy_ui_css()

    assert ".dividend-manual-strategy-panel" in css
    assert ".dividend-manual-rule-row" in css
