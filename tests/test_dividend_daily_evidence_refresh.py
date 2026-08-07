from __future__ import annotations

from pathlib import Path

import candidate_discovery_engine
import run_daily_dividend_cycle
from src.dividend_bot import dividend_strategy_kpi_evidence
from src.dividend_bot.dividend_daily_evidence_refresh import (
    refresh_dividend_daily_evidence,
)


def test_refresh_runs_intelligence_candidate_and_kpi_evidence(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_cycle(*, root_path: str):
        calls.append(f"cycle:{root_path}")
        return {"run_status": "COMPLETE", "warnings": [], "errors": []}

    def fake_candidate(*, root_path: str):
        calls.append(f"candidate:{root_path}")
        return {"candidate_count": 8, "watchlist_count": 3}

    def fake_evidence(*, root_dir: str | Path, output_path=dividend_strategy_kpi_evidence.DEFAULT_OUTPUT):
        calls.append(f"evidence:{root_dir}")
        return Path(root_dir) / output_path

    monkeypatch.setattr(run_daily_dividend_cycle, "run_daily_dividend_cycle", fake_cycle)
    monkeypatch.setattr(candidate_discovery_engine, "write_candidate_discovery", fake_candidate)
    monkeypatch.setattr(dividend_strategy_kpi_evidence, "write_dividend_strategy_kpi_evidence", fake_evidence)

    report = refresh_dividend_daily_evidence(tmp_path)

    assert calls == [
        f"cycle:{tmp_path}",
        f"candidate:{tmp_path}",
        f"evidence:{tmp_path}",
    ]
    assert report["status"] == "COMPLETE"
    assert report["daily_dividend_cycle_status"] == "COMPLETE"
    assert report["candidate_count"] == 8
    assert report["watchlist_count"] == 3
    assert report["kpi_evidence_path"].endswith("results/dividend_strategy_kpi_evidence.json")


def test_refresh_preserves_governance_and_execution_locks(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        run_daily_dividend_cycle,
        "run_daily_dividend_cycle",
        lambda **_: {"run_status": "PARTIAL", "warnings": ["evidence incomplete"], "errors": ["stage failed"]},
    )
    monkeypatch.setattr(
        candidate_discovery_engine,
        "write_candidate_discovery",
        lambda **_: {"candidate_count": 0, "watchlist_count": 0},
    )
    monkeypatch.setattr(
        dividend_strategy_kpi_evidence,
        "write_dividend_strategy_kpi_evidence",
        lambda **_: tmp_path / "results/dividend_strategy_kpi_evidence.json",
    )

    report = refresh_dividend_daily_evidence(tmp_path)

    assert report["status"] == "PARTIAL"
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["order_placement_enabled"] is False
    assert report["capital_movement_enabled"] is False
    assert report["automatic_activation_allowed"] is False
    assert report["reporting_only"] is True
