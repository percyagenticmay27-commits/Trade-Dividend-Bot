from __future__ import annotations

import json

from paper_trading_engine import PaperTradingEngine


class _Provider:
    def fetch(self, symbols):
        return {}


def _engine(tmp_path, entries):
    engine = PaperTradingEngine(_Provider())
    engine.watchlist_path = tmp_path / "watchlist.json"
    engine.entry_score_path = tmp_path / "entry_score.json"
    engine.watchlist_path.write_text(json.dumps({"watchlist": []}), encoding="utf-8")
    engine.entry_score_path.write_text(
        json.dumps({"symbol_specific": True, "entries": entries}), encoding="utf-8"
    )
    return engine


def _signals(*, a_sell=False, b_sell=False):
    return {
        "available": True,
        "strategy_a": {
            "buy_trigger": False,
            "sell_trigger": a_sell,
            "sell_reasons": ["STOCH_RSI_D_CROSSED_ABOVE_K"] if a_sell else [],
        },
        "strategy_b": {
            "buy_eligible": False,
            "sell_trigger": b_sell,
            "sell_reason": "PRICE_BELOW_EMA20" if b_sell else None,
        },
    }


def test_strategy_a_owned_sleeve_ignores_strategy_b_sell(tmp_path):
    engine = _engine(tmp_path, [{"symbol": "AAA", "strategy_signals": _signals(b_sell=True)}])
    entry = {
        "a_strategy_owner": "STRATEGY_A",
        "a_strategy_ownership_source": "QUALIFIED_ENTRY_GATE",
    }
    decision = engine._owned_sleeve_exit_decision(
        entry=entry,
        config={"a": "AAA"},
        side="A",
    )
    assert decision["strategy_owner"] == "STRATEGY_A"
    assert decision["sell_trigger"] is False
    assert decision["sell_reasons"] == []


def test_strategy_a_owned_sleeve_accepts_strategy_a_sell(tmp_path):
    engine = _engine(tmp_path, [{"symbol": "AAA", "strategy_signals": _signals(a_sell=True)}])
    entry = {
        "a_strategy_owner": "STRATEGY_A",
        "a_strategy_ownership_source": "QUALIFIED_ENTRY_GATE",
    }
    decision = engine._owned_sleeve_exit_decision(
        entry=entry,
        config={"a": "AAA"},
        side="A",
    )
    assert decision["sell_trigger"] is True
    assert decision["sell_reasons"] == ["STOCH_RSI_D_CROSSED_ABOVE_K"]


def test_strategy_b_owned_sleeve_ignores_strategy_a_sell(tmp_path):
    engine = _engine(tmp_path, [{"symbol": "AAA", "strategy_signals": _signals(a_sell=True)}])
    entry = {
        "a_strategy_owner": "STRATEGY_B",
        "a_strategy_ownership_source": "QUALIFIED_ENTRY_GATE",
    }
    decision = engine._owned_sleeve_exit_decision(
        entry=entry,
        config={"a": "AAA"},
        side="A",
    )
    assert decision["strategy_owner"] == "STRATEGY_B"
    assert decision["sell_trigger"] is False


def test_strategy_b_owned_sleeve_accepts_price_below_ema20_sell(tmp_path):
    engine = _engine(tmp_path, [{"symbol": "AAA", "strategy_signals": _signals(b_sell=True)}])
    entry = {
        "a_strategy_owner": "STRATEGY_B",
        "a_strategy_ownership_source": "QUALIFIED_ENTRY_GATE",
    }
    decision = engine._owned_sleeve_exit_decision(
        entry=entry,
        config={"a": "AAA"},
        side="A",
    )
    assert decision["sell_trigger"] is True
    assert decision["sell_reasons"] == ["PRICE_BELOW_EMA20"]


def test_unknown_owner_fails_closed_even_when_both_sell(tmp_path):
    engine = _engine(tmp_path, [{"symbol": "AAA", "strategy_signals": _signals(a_sell=True, b_sell=True)}])
    entry = {
        "a_strategy_owner": None,
        "a_strategy_ownership_source": "LEGACY_UNOWNED",
    }
    decision = engine._owned_sleeve_exit_decision(
        entry=entry,
        config={"a": "AAA"},
        side="A",
    )
    assert decision["sell_trigger"] is False
    assert decision["reason"] == "STRATEGY_OWNERSHIP_UNKNOWN_FAIL_CLOSED"


def test_pair_exit_uses_common_persisted_owner_only(tmp_path):
    engine = _engine(
        tmp_path,
        [
            {"symbol": "AAA", "strategy_signals": _signals(b_sell=True)},
            {"symbol": "BBB", "strategy_signals": _signals(a_sell=True)},
        ],
    )
    entry = {
        "strategy_owner": "STRATEGY_A",
        "strategy_ownership_source": "QUALIFIED_ENTRY_GATE",
    }
    decision = engine._owned_pair_exit_decision(
        entry=entry,
        config={"a": "AAA", "b": "BBB"},
    )
    assert decision["strategy_owner"] == "STRATEGY_A"
    assert decision["sell_trigger"] is True
    assert decision["sell_reasons"] == ["STOCH_RSI_D_CROSSED_ABOVE_K"]


def test_closing_pair_preserves_last_exit_owner_and_reason():
    entry = {
        "strategy_owner": "STRATEGY_A",
        "a_strategy_owner": "STRATEGY_A",
        "b_strategy_owner": "STRATEGY_A",
    }
    PaperTradingEngine._clear_pair_strategy_owner(
        entry,
        {"sell_reasons": ["STOCH_RSI_D_CROSSED_ABOVE_K"]},
    )
    assert entry["last_exit_strategy_owner"] == "STRATEGY_A"
    assert entry["last_exit_strategy_reasons"] == ["STOCH_RSI_D_CROSSED_ABOVE_K"]
    assert entry["strategy_owner"] is None
    assert entry["a_strategy_owner"] is None
    assert entry["b_strategy_owner"] is None
    assert entry["strategy_ownership_source"] == "CLOSED_TO_SGOV"


def test_closing_sleeve_preserves_last_exit_owner_and_reason():
    entry = {"b_strategy_owner": "STRATEGY_B"}
    PaperTradingEngine._clear_sleeve_strategy_owner(
        entry,
        "B",
        {"sell_reasons": ["PRICE_BELOW_EMA20"]},
    )
    assert entry["b_last_exit_strategy_owner"] == "STRATEGY_B"
    assert entry["b_last_exit_strategy_reasons"] == ["PRICE_BELOW_EMA20"]
    assert entry["b_strategy_owner"] is None
    assert entry["b_strategy_ownership_source"] == "CLOSED_TO_SGOV"
