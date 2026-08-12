from __future__ import annotations

from src.dividend_bot.dividend_decision_journal import build_dividend_decision_journal


def test_journal_explains_hold_warning_and_confirmed_sell() -> None:
    report = build_dividend_decision_journal(
        holdings=[
            {
                "pair": "AMDW / AMDL",
                "symbol": "AMDW",
                "strategy_owner": "STRATEGY_A",
                "sell_trigger": False,
                "exit_warning_active": True,
                "exit_warning_reasons": ["FAST_WARNING_ONLY"],
                "exit_evidence_source": "entry_score_report.json",
                "exit_evidence_generated_at_utc": "2026-08-11T12:00:00Z",
            },
            {
                "pair": "AVGW / AVGX",
                "symbol": "AVGW",
                "strategy_owner": "STRATEGY_B",
                "sell_trigger": True,
                "sell_reasons": ["PRICE_BELOW_EMA20"],
                "exit_evidence_source": "entry_score_report.json",
            },
        ],
        watchlist=[],
        historical_positions=[],
    )
    hold, sell = report["decisions"]
    assert hold["decision_type"] == "HOLD"
    assert hold["status"] == "MONITOR"
    assert "warning is buffered" in hold["final_rationale"]
    assert sell["decision_type"] == "SELL"
    assert sell["status"] == "ACTION_REQUIRED"
    assert sell["committee_evidence"][0]["engine"] == "STRATEGY_B"


def test_watchlist_decision_explains_what_blocks_purchase() -> None:
    report = build_dividend_decision_journal(
        holdings=[],
        watchlist=[{
            "symbol": "TEST",
            "entry_status": "WAIT",
            "entry_score": 61,
            "entry_confidence_level": "MEDIUM",
            "requirements_for_buy": ["PRICE_ABOVE_EMA20", "MOMENTUM_CONFIRMED"],
            "entry_evidence_source": "entry_score_report.json",
            "entry_evidence_generated_at_utc": "2026-08-11T12:00:00Z",
        }],
        historical_positions=[],
    )
    decision = report["decisions"][0]
    assert decision["decision_type"] == "WATCHLIST"
    assert decision["status"] == "WAITING_FOR_ENTRY"
    assert "price above ema20" in decision["final_rationale"]
    assert "momentum confirmed" in decision["final_rationale"]


def test_historical_exit_preserves_reported_reason() -> None:
    report = build_dividend_decision_journal(
        holdings=[],
        watchlist=[],
        historical_positions=[{
            "pair": "NVDW / NVDX",
            "exit_date": "2026-06-28",
            "exit_reason": "OWNER_SPECIFIC_SELL_CONFIRMED",
            "exit_strategy": "STRATEGY_A",
        }],
    )
    decision = report["decisions"][0]
    assert decision["decision_type"] == "SELL"
    assert decision["status"] == "COMPLETED"
    assert "owner specific sell confirmed" in decision["final_rationale"]


def test_journal_is_read_only_and_paper_only() -> None:
    report = build_dividend_decision_journal(
        holdings=[], watchlist=[], historical_positions=[]
    )
    assert report["paper_trade_mode"] is True
    assert report["read_only"] is True
    assert report["reporting_only"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["capital_movement_enabled"] is False


def test_historical_exit_preserves_lifecycle_reason_score_and_confidence() -> None:
    report = build_dividend_decision_journal(
        holdings=[],
        watchlist=[],
        historical_positions=[{
            "pair": "AVGW / AVGX",
            "last_exit_date": "2026-06-28",
            "last_exit_reason": "PRICE_BELOW_EMA20",
            "last_exit_strategy_reasons": ["PRICE_BELOW_EMA20"],
            "last_exit_strategy_owner": "STRATEGY_A",
            "exit_score": 42,
            "exit_confidence": "HIGH",
        }],
    )

    decision = report["decisions"][0]
    evidence = decision["committee_evidence"][0]
    assert "price below ema20" in decision["final_rationale"]
    assert evidence["engine"] == "STRATEGY_A"
    assert evidence["score"] == 42
    assert evidence["confidence"] == "HIGH"
    assert evidence["evidence_status"] == "AVAILABLE"


def test_legacy_historical_exit_does_not_fabricate_reason_or_score() -> None:
    report = build_dividend_decision_journal(
        holdings=[],
        watchlist=[],
        historical_positions=[{
            "pair": "NVDW / NVDX",
            "last_exit_date": "2026-06-28",
            "last_exit_action": "PAPER_SELL_TO_SGOV",
        }],
    )

    decision = report["decisions"][0]
    evidence = decision["committee_evidence"][0]
    assert decision["final_rationale"] == (
        "Historical evidence records an exit, but no detailed reason was reported."
    )
    assert evidence["score"] is None
    assert evidence["confidence"] is None
    assert evidence["evidence_status"] == "PARTIAL"
