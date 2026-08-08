from __future__ import annotations

import json
from pathlib import Path

from dividend_watchlist_engine import build_dividend_watchlist, write_dividend_watchlist


def _rank(symbol: str, score: float, rating: str, momentum: float = 60.0) -> dict:
    return {
        "symbol": symbol,
        "overall_score": score,
        "overall_rating": rating,
        "quality_score": score,
        "momentum_score": momentum,
        "growth_score": 70.0,
        "safety_score": 75.0,
        "valuation_score": 65.0,
        "confidence": 0.8,
        "recommendation": "HOLD",
        "trend_direction": "UP",
    }


def test_promotes_ranked_nonheld_candidates_and_orders_by_score() -> None:
    report = build_dividend_watchlist(
        {"rankings": [_rank("AAA", 82, "BUY"), _rank("BBB", 68, "HOLD"), _rank("CCC", 55, "WATCHLIST")]},
        paper_state={"pairs": {}},
        market_snapshot={"records": [
            {"symbol": "AAA", "is_stale": False},
            {"symbol": "BBB", "is_stale": False},
            {"symbol": "CCC", "is_stale": False},
        ]},
    )
    assert [row["symbol"] for row in report["watchlist"]] == ["AAA", "BBB", "CCC"]
    assert [row["rank"] for row in report["watchlist"]] == [1, 2, 3]
    assert [row["status"] for row in report["watchlist"]] == ["READY", "MONITOR", "WATCH"]
    assert all(row["on_watchlist"] is True for row in report["watchlist"])


def test_excludes_current_holdings_stale_market_data_and_low_scores() -> None:
    report = build_dividend_watchlist(
        {"rankings": [_rank("HELD", 90, "STRONG_BUY"), _rank("STALE", 90, "STRONG_BUY"), _rank("LOW", 49, "AVOID"), _rank("GOOD", 75, "HOLD")]},
        paper_state={"pairs": {"HELD / OTHER": {"a_shares": 1.0, "b_shares": 0.0}}},
        market_snapshot={"records": [
            {"symbol": "HELD", "is_stale": False},
            {"symbol": "STALE", "is_stale": True},
            {"symbol": "LOW", "is_stale": False},
            {"symbol": "GOOD", "is_stale": False},
        ]},
    )
    assert [row["symbol"] for row in report["watchlist"]] == ["GOOD"]


def test_excludes_sgov_when_it_is_the_strategy_reserve_asset() -> None:
    report = build_dividend_watchlist(
        {"rankings": [_rank("SGOV", 72, "HOLD"), _rank("NUGT", 61, "WATCHLIST")]},
        paper_state={
            "pairs": {
                "AAA / BBB": {
                    "a_shares": 0.0,
                    "b_shares": 0.0,
                    "sgov_balance": 500.0,
                }
            }
        },
        market_snapshot={"records": [
            {"symbol": "SGOV", "is_stale": False},
            {"symbol": "NUGT", "is_stale": False},
        ]},
    )
    assert [row["symbol"] for row in report["watchlist"]] == ["NUGT"]
    assert report["promotion_policy"]["exclude_reserve_assets"] is True


def test_preserves_rank_components_and_market_detail_without_fabrication() -> None:
    report = build_dividend_watchlist(
        {"rankings": [_rank("AAA", 76, "HOLD", momentum=71)]},
        market_snapshot={"records": [{
            "symbol": "AAA",
            "is_stale": False,
            "name": "Alpha ETF",
            "daily_change_percent": 1.25,
        }]},
    )
    row = report["watchlist"][0]
    assert row["name"] == "Alpha ETF"
    assert row["opportunity_score"] == 76.0
    assert row["momentum_score"] == 71.0
    assert row["daily_change_percent"] == 1.25
    assert row["conviction_score"] == 0.8
    assert row["currently_held"] is False
    assert row["market_data_stale"] is False


def test_empty_rankings_produce_valid_empty_watchlist() -> None:
    report = build_dividend_watchlist({"rankings": []})
    assert report["watchlist_count"] == 0
    assert report["watchlist"] == []
    assert report["paper_trade_mode"] is True
    assert report["broker_execution_enabled"] is False
    assert report["automatic_activation_allowed"] is False


def test_writer_publishes_json_markdown_and_csv(tmp_path: Path) -> None:
    (tmp_path / "dividend_rankings.json").write_text(json.dumps({"rankings": [_rank("AAA", 80, "BUY")]}), encoding="utf-8")
    (tmp_path / "paper_state.json").write_text(json.dumps({"pairs": {}}), encoding="utf-8")
    (tmp_path / "market_data_snapshot.json").write_text(json.dumps({"records": [{"symbol": "AAA", "is_stale": False}]}), encoding="utf-8")
    report = write_dividend_watchlist(tmp_path)
    assert report["watchlist_count"] == 1
    assert (tmp_path / "watchlist_report.json").is_file()
    assert (tmp_path / "watchlist_report.md").is_file()
    assert (tmp_path / "watchlist_report.csv").is_file()
