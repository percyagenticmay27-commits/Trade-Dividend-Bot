from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.dividend_strategy_kpi_evidence import (
    build_dividend_strategy_kpi_evidence,
    write_dividend_strategy_kpi_evidence,
)


def test_normalizes_dividend_owned_kpi_sources(tmp_path: Path) -> None:
    (tmp_path / "candidate_discovery.json").write_text(
        json.dumps({"watchlist_count": 4, "candidates": []}),
        encoding="utf-8",
    )
    (tmp_path / "dividend_rankings.json").write_text(
        json.dumps({"rankings": [{"symbol": "AAA", "overall_score": 72}, {"symbol": "BBB", "overall_score": 88}]}),
        encoding="utf-8",
    )
    results = tmp_path / "results"
    results.mkdir()
    (results / "strategy_performance_analytics.json").write_text(
        json.dumps({"strategies": [{"strategy_id": "DIVIDEND-001", "win_rate_pct": 63.5}]}),
        encoding="utf-8",
    )

    report = build_dividend_strategy_kpi_evidence(
        tmp_path,
        generated_at_utc="2026-08-06T12:00:00Z",
    )

    assert report["strategy_id"] == "DIVIDEND-001"
    assert report["watchlist_count"] == 4
    assert report["opportunity_quality"] == 88.0
    assert report["win_rate_percent"] == 63.5
    assert report["missing_metrics"] == []
    assert report["evidence_status"] == "AVAILABLE"
    assert report["calculation_methods"]["opportunity_quality"] == "BEST_DIVIDEND_RANKING_OVERALL_SCORE"


def test_watchlist_can_be_counted_from_candidate_flags(tmp_path: Path) -> None:
    (tmp_path / "candidate_discovery.json").write_text(
        json.dumps({
            "candidates": [
                {"symbol": "AAA", "on_watchlist": True},
                {"symbol": "BBB", "on_watchlist": False},
                {"symbol": "CCC", "on_watchlist": True},
            ]
        }),
        encoding="utf-8",
    )

    report = build_dividend_strategy_kpi_evidence(tmp_path)

    assert report["watchlist_count"] == 2
    assert report["calculation_methods"]["watchlist_count"] == "CANDIDATE_WATCHLIST_FLAG_COUNT"


def test_opportunity_pairing_is_supported_without_arbitrary_recursive_alias(tmp_path: Path) -> None:
    (tmp_path / "opportunity_pairing_report.json").write_text(
        json.dumps({"opportunities": [{"combined_score": 61}, {"combined_score": 79.25}]}),
        encoding="utf-8",
    )

    report = build_dividend_strategy_kpi_evidence(tmp_path)

    assert report["opportunity_quality"] == 79.25
    assert report["calculation_methods"]["opportunity_quality"] == "BEST_OPPORTUNITY_PAIRING_COMBINED_SCORE"


def test_win_rate_is_not_fabricated_from_return_or_profit(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    (results / "strategy_performance_analytics.json").write_text(
        json.dumps({"return_percent": 25.0, "net_profit": 1000.0}),
        encoding="utf-8",
    )

    report = build_dividend_strategy_kpi_evidence(tmp_path)

    assert report["win_rate_percent"] is None
    assert "win_rate_percent" in report["missing_metrics"]


def test_missing_sources_remain_not_reported_instead_of_zero(tmp_path: Path) -> None:
    report = build_dividend_strategy_kpi_evidence(tmp_path)

    assert report["watchlist_count"] is None
    assert report["opportunity_quality"] is None
    assert report["win_rate_percent"] is None
    assert report["evidence_status"] == "NOT_REPORTED"


def test_governance_and_execution_flags_remain_locked(tmp_path: Path) -> None:
    report = build_dividend_strategy_kpi_evidence(tmp_path)

    assert report["paper_trade_mode"] is True
    assert report["reporting_only"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["order_placement_enabled"] is False
    assert report["capital_movement_enabled"] is False
    assert report["automatic_activation_allowed"] is False
    assert report["investor_governance_required"] is True


def test_writer_publishes_canonical_json(tmp_path: Path) -> None:
    target = write_dividend_strategy_kpi_evidence(tmp_path)

    assert target == tmp_path / "results" / "dividend_strategy_kpi_evidence.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["strategy_id"] == "DIVIDEND-001"


def test_writer_publishes_decision_journal_to_canonical_kpi_file(tmp_path: Path) -> None:
    (tmp_path / "paper_state.json").write_text(json.dumps({
        "pairs": {
            "AMDW / AMDL": {
                "a_shares": 2.0,
                "b_shares": 1.0,
                "last_prices": {"A": 20.0, "B": 30.0},
                "strategy_owner": "STRATEGY_A",
                "a_strategy_owner": "STRATEGY_A",
            }
        }
    }), encoding="utf-8")
    (tmp_path / "entry_score_report.json").write_text(json.dumps({
        "generated_at_utc": "2026-08-11T16:00:00Z",
        "entries": [],
    }), encoding="utf-8")

    target = write_dividend_strategy_kpi_evidence(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))

    assert payload["decision_journal_status"] == "AVAILABLE"
    assert payload["decision_count"] == 2
    assert payload["decision_journal"]["strategy_id"] == "DIVIDEND-001"
    assert all(
        decision["decision_type"] == "HOLD"
        for decision in payload["decision_journal"]["decisions"]
    )
    assert payload["paper_trade_mode"] is True
    assert payload["broker_execution_enabled"] is False
