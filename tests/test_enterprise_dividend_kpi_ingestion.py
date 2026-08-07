from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.enterprise_strategy_kpi_adapter import build_strategy_kpis


def _dividend_plugin() -> dict:
    return {
        "strategy_id": "DIVIDEND-001",
        "display_name": "Dividend Income Strategy",
        "strategy_type": "DIVIDEND_ETF",
        "lifecycle_status": "PRODUCTION",
        "runtime_status": "ONLINE",
        "health_status": "HEALTHY",
        "readiness": "READY",
        "enabled": True,
        "paper_trade_mode": True,
        "paper_compatible": True,
        "advisory_only": True,
        "reporting_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
        "capabilities": ["portfolio", "watchlist"],
        "dashboard_artifacts": [],
    }


def test_dividend_host_evidence_populates_dashboard_kpis(tmp_path: Path) -> None:
    (tmp_path / "candidate_discovery.json").write_text(
        json.dumps({"watchlist_count": 5}),
        encoding="utf-8",
    )
    (tmp_path / "dividend_rankings.json").write_text(
        json.dumps({"rankings": [{"overall_score": 71}, {"overall_score": 86.25}]}),
        encoding="utf-8",
    )
    results = tmp_path / "results"
    results.mkdir()
    (results / "strategy_performance_analytics.json").write_text(
        json.dumps({"strategy_id": "DIVIDEND-001", "win_rate_pct": 62.5}),
        encoding="utf-8",
    )

    rows, warnings = build_strategy_kpis(
        registry={"strategy_plugins": [_dividend_plugin()]},
        strategy_allocations={"DIVIDEND-001": 5000},
        root_dir=tmp_path,
    )

    assert warnings == []
    assert len(rows) == 1
    row = rows[0]
    assert row["allocated_capital"] == 5000.0
    assert row["watchlist_count"] == 5
    assert row["opportunity_quality"] == 86.25
    assert row["win_rate_percent"] == 62.5
    assert row["evidence_status"] == "AVAILABLE"
    assert any(path.endswith("candidate_discovery.json") for path in row["evidence_paths"])
    assert any(path.endswith("dividend_rankings.json") for path in row["evidence_paths"])
    assert any(path.endswith("strategy_performance_analytics.json") for path in row["evidence_paths"])


def test_dividend_host_evidence_does_not_enable_execution(tmp_path: Path) -> None:
    rows, _ = build_strategy_kpis(
        registry={"strategy_plugins": [_dividend_plugin()]},
        root_dir=tmp_path,
    )

    row = rows[0]
    assert row["paper_trade_mode"] is True
    assert row["advisory_only"] is True
    assert row["reporting_only"] is True
