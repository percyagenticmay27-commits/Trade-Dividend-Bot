from urllib.parse import urlencode

import pytest

from dividend_bot.enterprise_manual_strategy_post import (
    parse_manual_strategy_form,
    submit_manual_strategy_form,
)


def _body(**overrides) -> bytes:
    values = [
        ("strategy_id", "NFLX_TEST"),
        ("name", "NFLX Test"),
        ("underlying_symbol", "NFLX"),
        ("direction", "LONG"),
        ("timeframe", "1D"),
        ("session", "REGULAR_SESSION"),
        ("number_of_entries", "2"),
        ("rule_logic", "ALL"),
        ("entry_rule_left", "close"),
        ("entry_rule_operator", ">"),
        ("entry_rule_right", "ema"),
        ("entry_rule_period", "20"),
        ("entry_rule_label", "Close above EMA(20)"),
        ("regime_logic", "ALL"),
        ("regime_rule_left", "rsi"),
        ("regime_rule_operator", "between"),
        ("regime_rule_right", "45,65"),
        ("regime_rule_period", "14"),
        ("confirmation", "2 consecutive qualifying Daily closes"),
        ("reentry_cooldown", "Reset after exit"),
    ]
    for key, value in overrides.items():
        values = [(k, v) for k, v in values if k != key]
        if isinstance(value, list):
            values.extend((key, item) for item in value)
        elif value is not None:
            values.append((key, value))
    return urlencode(values, doseq=True).encode("utf-8")


def test_form_parser_builds_structured_swing_submission() -> None:
    payload = parse_manual_strategy_form(_body())

    assert payload["strategy_id"] == "NFLX_TEST"
    assert payload["underlying_symbol"] == "NFLX"
    assert payload["number_of_entries"] == 2
    assert payload["rules"] == [
        {
            "left": "close",
            "operator": ">",
            "right": "ema",
            "period": 20,
            "label": "Close above EMA(20)",
        }
    ]
    assert payload["regime_filters"][0]["right"] == [45.0, 65.0]
    assert payload["confirmation"]["description"].startswith("2 consecutive")
    assert payload["reentry_cooldown"]["description"] == "Reset after exit"
    assert payload["paper_trade_mode"] is True
    assert "allocation" not in payload
    assert "execution_symbol" not in payload


def test_form_parser_supports_multiple_entry_rules() -> None:
    body = urlencode(
        [
            ("strategy_id", "MULTI"),
            ("name", "Multi"),
            ("underlying_symbol", "NVDA"),
            ("timeframe", "1D"),
            ("entry_rule_left", "close"),
            ("entry_rule_left", "rsi"),
            ("entry_rule_operator", ">"),
            ("entry_rule_operator", "between"),
            ("entry_rule_right", "ema"),
            ("entry_rule_right", "45,65"),
            ("entry_rule_period", "20"),
            ("entry_rule_period", "14"),
        ]
    ).encode()
    payload = parse_manual_strategy_form(body)
    assert len(payload["rules"]) == 2
    assert payload["rules"][1]["right"] == [45.0, 65.0]


def test_form_parser_rejects_incomplete_rule_row() -> None:
    with pytest.raises(ValueError, match="requires source, operator, and value"):
        parse_manual_strategy_form(_body(entry_rule_right=""))


def test_submit_delegates_only_parsed_payload_to_transport() -> None:
    captured = {}

    def fake_transport(submission):
        captured.update(submission)
        return {
            "ok": True,
            "paper_trade_mode": True,
            "result": {"status": "SAVED", "strategy_id": submission["strategy_id"]},
        }

    response = submit_manual_strategy_form(_body(), transport=fake_transport)
    assert response["ok"] is True
    assert captured["strategy_id"] == "NFLX_TEST"
    assert captured["number_of_entries"] == 2


def test_submit_requires_at_least_one_entry_rule() -> None:
    body = urlencode(
        {
            "strategy_id": "EMPTY",
            "name": "Empty",
            "underlying_symbol": "NFLX",
            "timeframe": "1D",
        }
    ).encode()
    with pytest.raises(ValueError, match="at least one entry rule"):
        submit_manual_strategy_form(body, transport=lambda payload: {})
