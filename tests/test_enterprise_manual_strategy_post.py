from urllib.parse import urlencode

import pytest

from dividend_bot.enterprise_manual_strategy_post import parse_manual_strategy_form, submit_manual_strategy_form


def _body(**overrides) -> bytes:
    values = [
        ("strategy_id", "M_HMA50_DAILY"), ("name", "M-HMA50 Daily"), ("underlying_symbol", "NFLX"),
        ("assignment_mode", "DIRECT"), ("direction", "LONG"), ("timeframe", "1D"),
        ("session", "08:30-14:30 CT"), ("number_of_entries", "1"), ("confirmation_bars", "2"),
        ("rule_logic", "ALL"),
        ("entry_rule_left", "close"), ("entry_rule_operator", ">"), ("entry_rule_right", "keltner_middle"),
        ("entry_rule_period", "14"), ("entry_rule_factor", "1"), ("entry_rule_smoothing", "WILDER"), ("entry_rule_price_source", "OHLC_AVERAGE"),
        ("regime_logic", "ALL"), ("regime_rule_left", "chop"), ("regime_rule_operator", "<"), ("regime_rule_right", "60"), ("regime_rule_period", "14"),
        ("normal_exit_logic", "ANY"), ("normal_exit_rule_left", "close"), ("normal_exit_rule_operator", "<"), ("normal_exit_rule_right", "ema"), ("normal_exit_rule_period", "18"),
        ("conditional_exit_enabled", "true"), ("conditional_exit_pl_threshold", "0"),
        ("conditional_exit_rule_left", "close"), ("conditional_exit_rule_operator", "<"), ("conditional_exit_rule_right", "hma"), ("conditional_exit_rule_period", "50"),
        ("conditional_exit_cooldown_bars", "2"), ("conditional_exit_cooldown_unit", "TRADING_DAY"),
    ]
    for key, value in overrides.items():
        values = [(k, v) for k, v in values if k != key]
        if isinstance(value, list):
            values.extend((key, item) for item in value)
        elif value is not None:
            values.append((key, value))
    return urlencode(values, doseq=True).encode("utf-8")


def test_form_parser_builds_frozen_m_hma50_submission() -> None:
    payload = parse_manual_strategy_form(_body())
    assert payload["strategy_id"] == "M_HMA50_DAILY"
    assert payload["underlying_symbol"] == "NFLX"
    assert payload["confirmation_bars"] == 2
    entry = payload["rules"][0]
    assert entry["right"] == "keltner_middle"
    assert entry["period"] == 14
    assert entry["factor"] == 1.0
    assert entry["smoothing"] == "WILDER"
    assert entry["price_source"] == "OHLC_AVERAGE"
    assert payload["regime_filters"][0] == {"left": "chop", "operator": "<", "right": 60.0, "period": 14}
    assert payload["normal_exit_rules"][0]["period"] == 18
    conditional = payload["conditional_exits"][0]
    assert conditional["condition"] == {"left": "position_pl", "operator": ">", "right": 0.0, "label": "Position P/L above activation threshold"}
    assert conditional["rules"][0]["right"] == "hma"
    assert conditional["rules"][0]["period"] == 50
    assert conditional["cooldown_bars"] == 2
    assert conditional["cooldown_unit"] == "TRADING_DAY"
    assert payload["paper_trade_mode"] is True
    assert "allocation" not in payload
    assert "execution_symbol" not in payload


def test_form_parser_supports_multiple_entry_rules() -> None:
    body = urlencode([
        ("strategy_id", "MULTI"), ("name", "Multi"), ("underlying_symbol", "NVDA"), ("timeframe", "1D"),
        ("entry_rule_left", "close"), ("entry_rule_left", "rsi"),
        ("entry_rule_operator", ">"), ("entry_rule_operator", "between"),
        ("entry_rule_right", "ema"), ("entry_rule_right", "45,65"),
        ("entry_rule_period", "20"), ("entry_rule_period", "14"),
    ]).encode()
    payload = parse_manual_strategy_form(body)
    assert len(payload["rules"]) == 2
    assert payload["rules"][1]["right"] == [45.0, 65.0]


def test_form_parser_rejects_incomplete_rule_row() -> None:
    with pytest.raises(ValueError, match="requires source, operator, and value"):
        parse_manual_strategy_form(_body(entry_rule_right=""))


def test_conditional_exit_requires_a_rule_when_enabled() -> None:
    with pytest.raises(ValueError, match="conditional exit is enabled"):
        parse_manual_strategy_form(_body(conditional_exit_rule_left="", conditional_exit_rule_operator="", conditional_exit_rule_right="", conditional_exit_rule_period=""))


def test_submit_delegates_only_parsed_payload_to_transport() -> None:
    captured = {}
    def fake_transport(submission):
        captured.update(submission)
        return {"ok": True, "paper_trade_mode": True, "result": {"status": "SAVED", "strategy_id": submission["strategy_id"]}}
    response = submit_manual_strategy_form(_body(), transport=fake_transport)
    assert response["ok"] is True
    assert captured["strategy_id"] == "M_HMA50_DAILY"
    assert captured["confirmation_bars"] == 2


def test_submit_requires_at_least_one_entry_rule() -> None:
    body = urlencode({"strategy_id": "EMPTY", "name": "Empty", "underlying_symbol": "NFLX", "timeframe": "1D"}).encode()
    with pytest.raises(ValueError, match="at least one entry rule"):
        submit_manual_strategy_form(body, transport=lambda payload: {})
