from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.dividend_bot.codex_robinhood_market_data_bridge import (
    read_codex_market_data_handoff,
    run_codex_market_data,
)


def test_tradebot_reader_consumes_sanitized_quote_handoff(tmp_path: Path) -> None:
    payload = {
        "symbol": "SOXL",
        "price": 42.5,
        "quote_timestamp": "2026-08-04T17:00:00+00:00",
        "trading_date": "2026-08-04",
        "source_type": "LIVE_QUOTE",
        "confidence": 0.95,
        "warnings": [],
    }
    (tmp_path / "SOXL.quote.json").write_text(json.dumps(payload), encoding="utf-8")

    result = read_codex_market_data_handoff(
        "get_quote", "SOXL", handoff_dir=tmp_path
    )

    assert result["provider"] == "ROBINHOOD_MCP"
    assert result["price"] == 42.5


def test_reader_rejects_symbol_mismatch(tmp_path: Path) -> None:
    payload = {"symbol": "TQQQ", "price": 10.0}
    (tmp_path / "SOXL.quote.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="symbol does not match"):
        read_codex_market_data_handoff("get_quote", "SOXL", handoff_dir=tmp_path)


def test_reader_rejects_authentication_material(tmp_path: Path) -> None:
    payload = {"symbol": "SOXL", "price": 10.0, "oauth": "forbidden"}
    (tmp_path / "SOXL.quote.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="sensitive"):
        read_codex_market_data_handoff("get_quote", "SOXL", handoff_dir=tmp_path)


def test_reader_rejects_order_operation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        read_codex_market_data_handoff("place_order", "SOXL", handoff_dir=tmp_path)


def test_codex_runner_defaults_to_real_server_path(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class Completed:
        returncode = 0
        stdout = '{"symbol":"SOXL","price":42,"quote_timestamp":"2026-08-04T17:00:00+00:00"}'
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["environment"] = kwargs["env"]
        return Completed()

    monkeypatch.setattr("subprocess.run", fake_run)
    result = run_codex_market_data("get_quote", "SOXL")

    assert captured["command"][0] == "/usr/local/bin/codex"
    assert captured["environment"] == {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": "/root",
    }
    assert result["provider"] == "ROBINHOOD_MCP"
