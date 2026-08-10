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
