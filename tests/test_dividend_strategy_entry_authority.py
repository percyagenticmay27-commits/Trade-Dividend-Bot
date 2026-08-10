from __future__ import annotations

import src.dividend_bot.dividend_technical_entry_evidence as evidence_module


def _record(symbol: str, closes: list[float], *, stale: bool = False) -> dict:
    return {
        "symbol": symbol,
        "is_stale": stale,
        "history": {
            "rows": [
                {
                    "open": close - 0.5,
                    "high": close + 2.0,
                    "low": close - 2.0,
                    "close": close,
                }
                for close in closes
            ]
        },
    }


def test_strategy_a_buy_is_not_blocked_by_strategy_b_ema_context(monkeypatch) -> None:
    """EMA/HMA context must not silently impose Strategy B rules on Strategy A."""
    strategy_signals = {
        "available": True,
        "strategy_a": {
            "buy_trigger": True,
            "sell_trigger": False,
            "entry_armed": True,
        },
        "strategy_b": {
            "buy_eligible": False,
            "sell_trigger": False,
        },
    }
    monkeypatch.setattr(evidence_module, "build_strategy_signals", lambda frame: strategy_signals)

    # A decline deliberately creates weak legacy EMA/HMA context. Strategy A is
    # still the authoritative entry model in this test.
    row = evidence_module.build_symbol_entry_evidence(
        _record("AAA", [150.0 - index * 0.25 for index in range(90)])
    )

    assert row["strategy_entry_approved"] is True
    assert row["strategy_ownership"]["strategy_owner"] == "STRATEGY_A"
    assert row["technical_signal"] == "BUY"
    assert row["entry_status"] in {"GOOD_ENTRY", "STRONG_ENTRY"}
    assert "EMA20_EMA50_BULLISH_ALIGNMENT_NOT_CONFIRMED" in row["technical_evidence"]["legacy_context_reasons"]
    assert "EMA20_EMA50_BULLISH_ALIGNMENT_NOT_CONFIRMED" not in row["reasons"]


def test_no_strategy_trigger_cannot_be_promoted_by_high_legacy_context(monkeypatch) -> None:
    strategy_signals = {
        "available": True,
        "strategy_a": {
            "buy_trigger": False,
            "sell_trigger": False,
            "entry_armed": False,
        },
        "strategy_b": {
            "buy_eligible": False,
            "sell_trigger": False,
        },
    }
    monkeypatch.setattr(evidence_module, "build_strategy_signals", lambda frame: strategy_signals)

    row = evidence_module.build_symbol_entry_evidence(
        _record("AAA", [100.0 + index * 0.5 for index in range(90)])
    )

    assert row["strategy_entry_approved"] is False
    assert row["entry_status"] == "WAIT"
    assert row["technical_signal"] == "HOLD"
    assert row["strategy_ownership"]["reason"] == "NO_ACTIVE_ENTRY_STRATEGY"


def test_stale_data_blocks_even_an_active_strategy_a_signal(monkeypatch) -> None:
    strategy_signals = {
        "available": True,
        "strategy_a": {
            "buy_trigger": True,
            "sell_trigger": False,
            "entry_armed": True,
        },
        "strategy_b": {
            "buy_eligible": False,
            "sell_trigger": False,
        },
    }
    monkeypatch.setattr(evidence_module, "build_strategy_signals", lambda frame: strategy_signals)

    row = evidence_module.build_symbol_entry_evidence(
        _record("AAA", [100.0 + index * 0.2 for index in range(90)], stale=True)
    )

    assert row["strategy_entry_approved"] is False
    assert row["entry_status"] == "WAIT"
    assert "STALE_MARKET_DATA" in row["reasons"]
