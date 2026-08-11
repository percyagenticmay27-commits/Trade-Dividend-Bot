from dividend_entry_gate import evaluate_entry_gate, evaluate_pair_entry_gate


def _watch(symbol="AAA", status="READY", stale=False):
    return {
        "watchlist": [{
            "symbol": symbol,
            "status": status,
            "market_data_stale": stale,
            "currently_held": False,
            "opportunity_score": 88,
        }]
    }


def _entry(status="GOOD_ENTRY", score=80):
    return {"entry_status": status, "entry_score": score}


def _tech(signal="BUY"):
    return {
        "signal": signal,
        "close": 100,
        "ema20": 98,
        "ema50": 95,
        "rsi14": 60,
    }


def test_hold_can_never_be_approved():
    row = evaluate_entry_gate(
        symbol="AAA",
        pair="AAA / BBB",
        sleeve="A",
        signal_symbol="BASE",
        technical_snapshot=_tech("HOLD"),
        watchlist_report=_watch(),
        entry_score_report=_entry(),
    )
    assert row["approved"] is False
    assert row["final_decision"] == "WAIT_IN_SGOV"
    assert "TECHNICAL_SIGNAL_HOLD" in row["reasons"]


def test_sell_can_never_be_approved():
    row = evaluate_entry_gate(
        symbol="AAA",
        pair="AAA / BBB",
        sleeve="A",
        signal_symbol="BASE",
        technical_snapshot=_tech("SELL"),
        watchlist_report=_watch(),
        entry_score_report=_entry(),
    )
    assert row["approved"] is False
    assert "TECHNICAL_SIGNAL_SELL" in row["reasons"]


def test_missing_or_unknown_entry_evidence_fails_closed():
    row = evaluate_entry_gate(
        symbol="AAA",
        pair="AAA / BBB",
        sleeve="A",
        signal_symbol="BASE",
        technical_snapshot=_tech(),
        watchlist_report=_watch(),
        entry_score_report={"entry_status": "UNKNOWN", "entry_score": 0},
    )
    assert row["approved"] is False
    assert "ENTRY_STATUS_NOT_APPROVED_UNKNOWN" in row["reasons"]


def test_watchlist_candidate_must_be_ready_and_fresh():
    row = evaluate_entry_gate(
        symbol="AAA",
        pair="AAA / BBB",
        sleeve="A",
        signal_symbol="BASE",
        technical_snapshot=_tech(),
        watchlist_report=_watch(status="WATCH"),
        entry_score_report=_entry(),
    )
    assert row["approved"] is False
    assert "WATCHLIST_NOT_PROMOTED_WATCH" in row["reasons"]

    stale = evaluate_entry_gate(
        symbol="AAA",
        pair="AAA / BBB",
        sleeve="A",
        signal_symbol="BASE",
        technical_snapshot=_tech(),
        watchlist_report=_watch(stale=True),
        entry_score_report=_entry(),
    )
    assert stale["approved"] is False
    assert "MARKET_FRESHNESS_NOT_CONFIRMED" in stale["reasons"]


def test_explicit_buy_ready_fresh_and_good_entry_is_approved():
    row = evaluate_entry_gate(
        symbol="AAA",
        pair="AAA / BBB",
        sleeve="A",
        signal_symbol="BASE",
        technical_snapshot=_tech(),
        watchlist_report=_watch(),
        entry_score_report=_entry(),
    )
    assert row["approved"] is True
    assert row["final_decision"] == "BUY_APPROVED"
    assert row["reasons"] == []


def test_pair_managed_requires_both_sleeves_ready():
    report = {
        "watchlist": [
            {"symbol": "AAA", "status": "READY", "market_data_stale": False, "currently_held": False},
            {"symbol": "BBB", "status": "WATCH", "market_data_stale": False, "currently_held": False},
        ]
    }
    result = evaluate_pair_entry_gate(
        pair="AAA / BBB",
        config={
            "a": "AAA",
            "b": "BBB",
            "a_signal": "BASE",
            "b_signal": "BASE",
            "architecture": "pair_managed",
        },
        technical_snapshot=_tech(),
        watchlist_report=report,
        entry_score_report=_entry(),
    )
    assert result["approved"] is False
    assert result["final_decision"] == "WAIT_IN_SGOV"


def test_safety_flags_are_permanently_paper_only():
    row = evaluate_entry_gate(
        symbol="AAA",
        pair="AAA / BBB",
        sleeve="A",
        signal_symbol="BASE",
        technical_snapshot=_tech(),
        watchlist_report=_watch(),
        entry_score_report=_entry(),
    )
    assert row["paper_trade_mode"] is True
    assert row["live_trading_enabled"] is False
    assert row["broker_execution_enabled"] is False
    assert row["order_placement_enabled"] is False


def test_promoted_strategy_b_controls_new_entry_even_if_report_embeds_old_a_owner():
    report = {
        "symbol_specific": True,
        "entries": [{
            "symbol": "AAA",
            "entry_status": "STRONG_ENTRY",
            "entry_score": 90,
            "strategy_entry_approved": False,
            "strategy_ownership": {
                "strategy_owner": "STRATEGY_A",
                "reason": "STALE_PRE_PROMOTION_OWNER",
            },
            "strategy_signals": {
                "strategy_a": {"buy_trigger": False},
                "strategy_b": {"buy_eligible": True},
            },
            "reasons": ["STRATEGY_ENTRY_TRIGGER_ACTIVE"],
        }],
    }
    row = evaluate_entry_gate(
        symbol="AAA",
        pair="AAA / BBB",
        sleeve="A",
        signal_symbol="BASE",
        technical_snapshot=_tech("HOLD"),
        watchlist_report=_watch(),
        entry_score_report=report,
        pair_primary_strategy="STRATEGY_B",
    )
    assert row["approved"] is True
    assert row["strategy_owner"] == "STRATEGY_B"
    assert row["technical_snapshot"]["pair_primary_strategy"] == "STRATEGY_B"
