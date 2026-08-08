import json

from paper_trading_engine import PaperTradingEngine


class _Provider:
    def fetch(self, symbols):
        return {}


def _engine(tmp_path, watch_status="READY", entry_status="GOOD_ENTRY"):
    engine = PaperTradingEngine(_Provider())
    engine.watchlist_path = tmp_path / "watchlist_report.json"
    engine.entry_score_path = tmp_path / "entry_score_report.json"
    engine.watchlist_path.write_text(
        json.dumps({
            "watchlist": [
                {"symbol": "AAA", "status": watch_status, "market_data_stale": False, "currently_held": False},
                {"symbol": "BBB", "status": watch_status, "market_data_stale": False, "currently_held": False},
            ]
        }),
        encoding="utf-8",
    )
    engine.entry_score_path.write_text(
        json.dumps({"entry_status": entry_status, "entry_score": 80}),
        encoding="utf-8",
    )
    return engine


def _pair_entry():
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


def _pair_config():
    return {
        "a": "AAA",
        "b": "BBB",
        "a_signal": "BASE",
        "b_signal": "BASE",
        "architecture": "pair_managed",
    }


def test_pair_reentry_hold_remains_in_sgov(tmp_path):
    engine = _engine(tmp_path)
    entry = _pair_entry()
    logs = []

    engine.buy_pair(
        "AAA / BBB",
        entry,
        _pair_config(),
        {"A": "HOLD", "B": "HOLD"},
        {"A": 10.0, "B": 20.0},
        "2026-06-18",
        "Underlying HOLD",
        logs,
    )

    assert entry["a_shares"] == 0.0
    assert entry["b_shares"] == 0.0
    assert entry["sgov_balance"] == 100.0
    assert entry["last_action"] == "PAPER_WAIT_IN_SGOV"
    assert entry["entry_gate"]["approved"] is False
    assert "TECHNICAL_SIGNAL_HOLD" in entry["entry_gate"]["reasons"]
    assert logs == []


def test_pair_reentry_buy_requires_ready_watchlist_and_entry_quality(tmp_path):
    engine = _engine(tmp_path)
    entry = _pair_entry()
    logs = []

    engine.buy_pair(
        "AAA / BBB",
        entry,
        _pair_config(),
        {"A": "BUY", "B": "BUY"},
        {"A": 10.0, "B": 20.0},
        "2026-07-01",
        "Underlying BUY",
        logs,
    )

    assert entry["a_in_sgov"] is False
    assert entry["b_in_sgov"] is False
    assert entry["sgov_balance"] == 0.0
    assert entry["a_shares"] == 6.0
    assert entry["b_shares"] == 2.0
    assert entry["entry_gate"]["approved"] is True
    assert entry["last_action"] == "PAPER_BUY_FROM_SGOV"
    assert len(logs) == 2


def test_pair_reentry_unknown_entry_quality_fails_closed(tmp_path):
    engine = _engine(tmp_path, entry_status="UNKNOWN")
    entry = _pair_entry()
    logs = []

    engine.buy_pair(
        "AAA / BBB",
        entry,
        _pair_config(),
        {"A": "BUY", "B": "BUY"},
        {"A": 10.0, "B": 20.0},
        "2026-07-01",
        "Underlying BUY",
        logs,
    )

    assert entry["sgov_balance"] == 100.0
    assert entry["entry_gate"]["approved"] is False
    assert "ENTRY_STATUS_NOT_APPROVED_UNKNOWN" in entry["entry_gate"]["reasons"]
    assert logs == []


def test_pair_reentry_unpromoted_watchlist_fails_closed(tmp_path):
    engine = _engine(tmp_path, watch_status="WATCH")
    entry = _pair_entry()

    engine.buy_pair(
        "AAA / BBB",
        entry,
        _pair_config(),
        {"A": "BUY", "B": "BUY"},
        {"A": 10.0, "B": 20.0},
        "2026-07-01",
        "Underlying BUY",
        [],
    )

    assert entry["sgov_balance"] == 100.0
    assert entry["entry_gate"]["approved"] is False
    assert "WATCHLIST_NOT_PROMOTED_WATCH" in entry["entry_gate"]["reasons"]


def test_missing_entry_evidence_fails_closed(tmp_path):
    engine = PaperTradingEngine(_Provider())
    engine.watchlist_path = tmp_path / "missing_watchlist.json"
    engine.entry_score_path = tmp_path / "missing_entry_score.json"
    entry = _pair_entry()

    engine.buy_pair(
        "AAA / BBB",
        entry,
        _pair_config(),
        {"A": "BUY", "B": "BUY"},
        {"A": 10.0, "B": 20.0},
        "2026-07-01",
        "Underlying BUY",
        [],
    )

    assert entry["sgov_balance"] == 100.0
    assert entry["entry_gate"]["approved"] is False
    assert "NOT_ON_STRATEGY_WATCHLIST" in entry["entry_gate"]["reasons"]
    assert "ENTRY_STATUS_NOT_APPROVED_MISSING" in entry["entry_gate"]["reasons"]


def test_safety_flags_remain_paper_only(tmp_path):
    engine = _engine(tmp_path)
    decision = engine._gate_pair(
        pair="AAA / BBB",
        config=_pair_config(),
        signals={"A": "BUY", "B": "BUY"},
    )
    assert decision["paper_trade_mode"] is True
    assert decision["live_trading_enabled"] is False
    assert decision["broker_execution_enabled"] is False
    assert decision["order_placement_enabled"] is False
