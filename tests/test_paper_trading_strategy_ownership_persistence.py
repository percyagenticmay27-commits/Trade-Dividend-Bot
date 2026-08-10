from __future__ import annotations

import json

from paper_trading_engine import PaperTradingEngine


class _Provider:
    def fetch(self, symbols):
        return {}


def _engine(tmp_path, *, owner: str = "STRATEGY_A") -> PaperTradingEngine:
    engine = PaperTradingEngine(_Provider())
    engine.watchlist_path = tmp_path / "watchlist_report.json"
    engine.entry_score_path = tmp_path / "entry_score_report.json"
    engine.watchlist_path.write_text(
        json.dumps({
            "watchlist": [
                {"symbol": "AAA", "status": "READY", "market_data_stale": False, "currently_held": False},
                {"symbol": "BBB", "status": "READY", "market_data_stale": False, "currently_held": False},
            ]
        }),
        encoding="utf-8",
    )
    engine.entry_score_path.write_text(
        json.dumps({
            "symbol_specific": True,
            "entries": [
                {
                    "symbol": "AAA",
                    "entry_score": 90,
                    "entry_status": "STRONG_ENTRY",
                    "strategy_entry_approved": True,
                    "strategy_ownership": {
                        "strategy_owner": owner,
                        "reason": "SINGLE_ACTIVE_ENTRY_STRATEGY",
                    },
                    "reasons": ["STRATEGY_ENTRY_TRIGGER_ACTIVE"],
                },
                {
                    "symbol": "BBB",
                    "entry_score": 90,
                    "entry_status": "STRONG_ENTRY",
                    "strategy_entry_approved": True,
                    "strategy_ownership": {
                        "strategy_owner": owner,
                        "reason": "SINGLE_ACTIVE_ENTRY_STRATEGY",
                    },
                    "reasons": ["STRATEGY_ENTRY_TRIGGER_ACTIVE"],
                },
            ],
        }),
        encoding="utf-8",
    )
    return engine


def _pair_entry() -> dict:
    return {
        "architecture": "pair_managed",
        "a_shares": 0.0,
        "b_shares": 0.0,
        "sgov_balance": 100.0,
        "a_sgov_balance": 0.0,
        "b_sgov_balance": 0.0,
        "a_in_sgov": True,
        "b_in_sgov": True,
        "pending_dividend_a": 0.0,
        "pending_dividend_b": 0.0,
        "restoration_a_weight": 0.6,
        "last_action": "PAPER_WAIT_IN_SGOV",
    }


def _pair_config() -> dict:
    return {
        "a": "AAA",
        "b": "BBB",
        "a_signal": "AAA",
        "b_signal": "BBB",
        "architecture": "pair_managed",
    }


def test_pair_reentry_persists_single_strategy_owner(tmp_path) -> None:
    engine = _engine(tmp_path, owner="STRATEGY_A")
    entry = _pair_entry()
    logs = []

    engine.buy_pair(
        "AAA / BBB",
        entry,
        _pair_config(),
        {"A": "SELL", "B": "SELL"},
        {"A": 10.0, "B": 20.0},
        "2026-08-10",
        "Strategy-owned qualified re-entry",
        logs,
    )

    assert entry["entry_gate"]["approved"] is True
    assert entry["strategy_owner"] == "STRATEGY_A"
    assert entry["a_strategy_owner"] == "STRATEGY_A"
    assert entry["b_strategy_owner"] == "STRATEGY_A"
    assert entry["strategy_ownership_source"] == "QUALIFIED_ENTRY_GATE"
    assert entry["a_in_sgov"] is False
    assert entry["b_in_sgov"] is False


def test_sleeve_reentry_persists_owner_on_that_sleeve_only(tmp_path) -> None:
    engine = _engine(tmp_path, owner="STRATEGY_B")
    entry = _pair_entry()
    entry["architecture"] = "independent_sleeves"
    entry["a_sgov_balance"] = 60.0
    entry["b_sgov_balance"] = 40.0
    logs = []

    engine.buy_sleeve(
        "AAA / BBB",
        entry,
        _pair_config(),
        "A",
        "SELL",
        10.0,
        "2026-08-10",
        "Strategy-owned qualified re-entry",
        logs,
    )

    assert entry["entry_gate"]["A"]["approved"] is True
    assert entry["a_strategy_owner"] == "STRATEGY_B"
    assert entry["a_strategy_ownership_source"] == "QUALIFIED_ENTRY_GATE"
    assert "b_strategy_owner" not in entry
    assert entry["a_in_sgov"] is False
    assert entry["b_in_sgov"] is True


def test_failed_entry_does_not_fabricate_strategy_owner(tmp_path) -> None:
    engine = _engine(tmp_path, owner="STRATEGY_A")
    engine.watchlist_path.write_text(json.dumps({"watchlist": []}), encoding="utf-8")
    entry = _pair_entry()

    engine.buy_pair(
        "AAA / BBB",
        entry,
        _pair_config(),
        {"A": "BUY", "B": "BUY"},
        {"A": 10.0, "B": 20.0},
        "2026-08-10",
        "Blocked re-entry",
        [],
    )

    assert entry["entry_gate"]["approved"] is False
    assert entry.get("strategy_owner") is None
    assert entry["a_in_sgov"] is True
    assert entry["b_in_sgov"] is True


def test_pair_owner_helper_refuses_multiple_owners() -> None:
    entry: dict = {}
    PaperTradingEngine._persist_pair_strategy_owner(
        entry,
        {"strategy_owners": ["STRATEGY_A", "STRATEGY_B"]},
    )
    assert entry["strategy_owner"] is None
    assert entry["a_strategy_owner"] is None
    assert entry["b_strategy_owner"] is None
    assert entry["strategy_ownership_source"] == "ENTRY_GATE_UNRESOLVED"

def test_legacy_pair_exit_uses_configured_current_signal_symbol_not_persisted_last_signal(tmp_path) -> None:
    engine = _engine(tmp_path)
    engine.entry_score_path.write_text(
        json.dumps({
            "symbol_specific": True,
            "entries": [{
                "symbol": "AMD",
                "strategy_signals": {
                    "strategy_a": {
                        "sell_trigger": True,
                        "sell_reasons": ["STOCH_OSC_D_CROSSED_ABOVE_K"],
                        "exit_warning_active": False,
                        "exit_buffered": False,
                        "exit_warning_reasons": [],
                    },
                    "strategy_b": {
                        "sell_trigger": True,
                        "sell_reason": "PRICE_BELOW_EMA20",
                    },
                },
            }],
        }),
        encoding="utf-8",
    )
    entry = {
        "strategy_owner": "LEGACY_UNASSIGNED",
        "strategy_ownership_source": "LEGACY_PRE_OWNERSHIP_POSITION",
        "last_signal": {"A": "BUY", "B": "BUY"},
    }
    config = {
        "a": "AMDW",
        "b": "AMDL",
        "a_signal": "AMD",
        "b_signal": "AMD",
        "architecture": "pair_managed",
    }

    result = engine._owned_pair_exit_decision(entry=entry, config=config)

    assert result["strategy_owner"] == "LEGACY_UNASSIGNED"
    assert result["sell_trigger"] is True
    assert result["reason"] == "PAIR_OWNER_EXIT_TRIGGERED"
    assert result["ownership_source"] == "LEGACY_PRE_OWNERSHIP_POSITION"
    assert {row["symbol"] for row in result["sleeves"]} == {"AMDW", "AMDL"}
    assert {row["signal_symbol"] for row in result["sleeves"]} == {"AMD"}
    assert all(row["exit_state"] == "SELL_CONFIRMED" for row in result["sleeves"])


def test_legacy_pair_single_current_strategy_sell_is_buffered(tmp_path) -> None:
    engine = _engine(tmp_path)
    engine.entry_score_path.write_text(
        json.dumps({
            "symbol_specific": True,
            "entries": [{
                "symbol": "AMD",
                "strategy_signals": {
                    "strategy_a": {
                        "sell_trigger": True,
                        "sell_reasons": ["STOCH_OSC_D_CROSSED_ABOVE_K"],
                        "exit_warning_active": False,
                        "exit_buffered": False,
                        "exit_warning_reasons": [],
                    },
                    "strategy_b": {
                        "sell_trigger": False,
                        "sell_reason": None,
                    },
                },
            }],
        }),
        encoding="utf-8",
    )
    entry = {
        "strategy_owner": "LEGACY_UNASSIGNED",
        "strategy_ownership_source": "LEGACY_PRE_OWNERSHIP_POSITION",
        "last_signal": {"A": "SELL", "B": "SELL"},
    }
    config = {
        "a": "AMDW",
        "b": "AMDL",
        "a_signal": "AMD",
        "b_signal": "AMD",
        "architecture": "pair_managed",
    }

    result = engine._owned_pair_exit_decision(entry=entry, config=config)

    assert result["sell_trigger"] is False
    assert all(row["exit_state"] == "WARNING_BUFFERED" for row in result["sleeves"])
    assert all(row["strategy_a_sell_trigger"] is True for row in result["sleeves"])
    assert all(row["strategy_b_sell_trigger"] is False for row in result["sleeves"])

