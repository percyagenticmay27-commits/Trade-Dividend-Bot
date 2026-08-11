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
    assert report["reporting_only"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["capital_movement_enabled"] is False
