from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.dividend_dashboard_evidence import build_dividend_dashboard_evidence


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_dashboard_prefers_explicit_strategy_watchlist_report(tmp_path: Path) -> None:
    _write(tmp_path / "paper_state.json", {"pairs": {}})
    _write(tmp_path / "candidate_discovery.json", {
        "candidates": [{"symbol": "LEGACY", "on_watchlist": True, "status": "READY_FOR_SCORING"}],
    })
    _write(tmp_path / "watchlist_report.json", {
        "strategy_id": "DIVIDEND-001",
        "watchlist_count": 1,
        "watchlist": [{
            "rank": 1,
            "symbol": "AAA",
            "name": "Alpha ETF",
            "status": "READY",
            "opportunity_score": 84.0,
            "momentum_score": 73.0,
            "market_data_stale": False,
            "currently_held": False,
            "sources": ["DIVIDEND_RANKING", "MARKET_SNAPSHOT"],
        }],
    })
    report = build_dividend_dashboard_evidence(tmp_path)
    assert report["watchlist_count"] == 1
    assert report["watchlist"][0]["symbol"] == "AAA"
    assert report["watchlist"][0]["opportunity_score"] == 84.0
    assert "watchlist_report.json" in report["evidence_sources"]


def test_dashboard_falls_back_to_candidate_discovery_when_watchlist_report_missing(tmp_path: Path) -> None:
    _write(tmp_path / "paper_state.json", {"pairs": {}})
    _write(tmp_path / "candidate_discovery.json", {
        "candidates": [{
            "symbol": "AAA",
            "on_watchlist": True,
            "status": "READY_FOR_SCORING",
            "currently_held": False,
            "market_data_stale": False,
            "sources": ["WATCHLIST"],
        }],
    })
    report = build_dividend_dashboard_evidence(tmp_path)
    assert report["watchlist_count"] == 1
    assert report["watchlist"][0]["symbol"] == "AAA"


def test_dashboard_does_not_promote_candidates_on_its_own(tmp_path: Path) -> None:
    _write(tmp_path / "paper_state.json", {"pairs": {}})
    _write(tmp_path / "candidate_discovery.json", {
        "candidates": [{"symbol": "AAA", "on_watchlist": False, "status": "READY_FOR_SCORING"}],
    })
    report = build_dividend_dashboard_evidence(tmp_path)
    assert report["watchlist_count"] == 0
    assert report["watchlist"] == []
