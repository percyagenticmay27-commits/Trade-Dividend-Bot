from __future__ import annotations

import json
from pathlib import Path

import candidate_discovery_engine
import dividend_ranking_engine
import dividend_watchlist_engine
import run_daily_dividend_cycle
from src.dividend_bot import dividend_paper_trade_performance
from src.dividend_bot import dividend_income_payment_evidence
from src.dividend_bot import dividend_strategy_kpi_evidence
from src.dividend_bot import market_momentum_evidence
from src.dividend_bot.dividend_daily_evidence_refresh import (
    refresh_dividend_daily_evidence,
)


def test_refresh_runs_intelligence_momentum_ranking_watchlist_candidate_performance_and_kpi_evidence(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    (tmp_path / "market_data_snapshot.json").write_text(json.dumps({"records": []}), encoding="utf-8")

    def fake_cycle(*, root_path: str):
        calls.append(f"cycle:{root_path}")
        return {"run_status": "COMPLETE", "warnings": [], "errors": []}

    def fake_momentum(snapshot, *, root_dir: str | Path, output_path):
        calls.append(f"momentum:{root_dir}")
        path = Path(root_dir) / output_path
        path.write_text(json.dumps({"entries": [{"symbol": "AAA", "momentum_score": 75.0}]}), encoding="utf-8")
        return path

    def fake_ranking(*, root_path: str):
        calls.append(f"ranking:{root_path}")
        return {"ranking_count": 1, "rankings": [{"symbol": "AAA", "overall_score": 70.0}]}

    def fake_watchlist(*, root_path: str | Path):
        calls.append(f"watchlist:{root_path}")
        return {"watchlist_count": 3, "warnings": [], "errors": []}

    def fake_candidate(*, root_path: str):
        calls.append(f"candidate:{root_path}")
        return {"candidate_count": 8, "watchlist_count": 3}

    def fake_performance(*, root_dir: str | Path, log_path=dividend_paper_trade_performance.DEFAULT_LOG_PATH, output_path=dividend_paper_trade_performance.DEFAULT_OUTPUT_PATH):
        calls.append(f"performance:{root_dir}")
        return Path(root_dir) / output_path

    def fake_income(root_dir: str | Path, **_):
        calls.append(f"income:{root_dir}")
        return {
            "payment_history_path": str(Path(root_dir) / "results/payment_history.json"),
            "upcoming_payments_path": str(Path(root_dir) / "results/upcoming_payments.json"),
            "payment_record_count": 2,
            "upcoming_record_count": 1,
            "payment_evidence_status": "AVAILABLE",
            "upcoming_evidence_status": "AVAILABLE",
        }

    def fake_evidence(*, root_dir: str | Path, output_path=dividend_strategy_kpi_evidence.DEFAULT_OUTPUT):
        calls.append(f"evidence:{root_dir}")
        return Path(root_dir) / output_path

    monkeypatch.setattr(run_daily_dividend_cycle, "run_daily_dividend_cycle", fake_cycle)
    monkeypatch.setattr(market_momentum_evidence, "write_market_momentum_report", fake_momentum)
    monkeypatch.setattr(dividend_ranking_engine, "build_dividend_ranking_report", fake_ranking)
    monkeypatch.setattr(dividend_watchlist_engine, "write_dividend_watchlist", fake_watchlist)
    monkeypatch.setattr(candidate_discovery_engine, "write_candidate_discovery", fake_candidate)
    monkeypatch.setattr(dividend_paper_trade_performance, "write_dividend_paper_trade_performance", fake_performance)
    monkeypatch.setattr(dividend_income_payment_evidence, "write_income_payment_evidence", fake_income)
    monkeypatch.setattr(dividend_strategy_kpi_evidence, "write_dividend_strategy_kpi_evidence", fake_evidence)

    report = refresh_dividend_daily_evidence(tmp_path)

    assert calls == [
        f"cycle:{tmp_path}",
        f"momentum:{tmp_path}",
        f"ranking:{tmp_path}",
        f"watchlist:{tmp_path}",
        f"candidate:{tmp_path}",
        f"performance:{tmp_path}",
        f"income:{tmp_path}",
        f"evidence:{tmp_path}",
    ]
    assert report["status"] == "COMPLETE"
    assert report["daily_dividend_cycle_status"] == "COMPLETE"
    assert report["candidate_count"] == 8
    assert report["watchlist_count"] == 3
    assert report["watchlist_evidence_path"].endswith("watchlist_report.json")
    assert report["momentum_symbol_count"] == 1
    assert report["ranking_count"] == 1
    assert report["momentum_evidence_path"].endswith("momentum_score_report.json")
    assert report["performance_evidence_path"].endswith("results/strategy_performance_analytics.json")
    assert report["payment_history_path"].endswith("results/payment_history.json")
    assert report["upcoming_payments_path"].endswith("results/upcoming_payments.json")
    assert report["payment_record_count"] == 2
    assert report["upcoming_payment_record_count"] == 1
    assert report["kpi_evidence_path"].endswith("results/dividend_strategy_kpi_evidence.json")


def test_refresh_preserves_governance_and_execution_locks(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "market_data_snapshot.json").write_text(json.dumps({"records": []}), encoding="utf-8")
    monkeypatch.setattr(
        run_daily_dividend_cycle,
        "run_daily_dividend_cycle",
        lambda **_: {"run_status": "PARTIAL", "warnings": ["evidence incomplete"], "errors": ["stage failed"]},
    )
    monkeypatch.setattr(
        market_momentum_evidence,
        "write_market_momentum_report",
        lambda snapshot, **_: (tmp_path / "momentum_score_report.json"),
    )
    (tmp_path / "momentum_score_report.json").write_text(json.dumps({"entries": []}), encoding="utf-8")
    monkeypatch.setattr(
        dividend_ranking_engine,
        "build_dividend_ranking_report",
        lambda **_: {"ranking_count": 0, "rankings": []},
    )
    monkeypatch.setattr(
        dividend_watchlist_engine,
        "write_dividend_watchlist",
        lambda **_: {"watchlist_count": 0, "warnings": [], "errors": []},
    )
    monkeypatch.setattr(
        candidate_discovery_engine,
        "write_candidate_discovery",
        lambda **_: {"candidate_count": 0, "watchlist_count": 0},
    )
    monkeypatch.setattr(
        dividend_paper_trade_performance,
        "write_dividend_paper_trade_performance",
        lambda **_: tmp_path / "results/strategy_performance_analytics.json",
    )
    monkeypatch.setattr(
        dividend_income_payment_evidence,
        "write_income_payment_evidence",
        lambda *_args, **_kwargs: {
            "payment_history_path": str(tmp_path / "results/payment_history.json"),
            "upcoming_payments_path": str(tmp_path / "results/upcoming_payments.json"),
            "payment_record_count": 0,
            "upcoming_record_count": 0,
            "payment_evidence_status": "AVAILABLE_EMPTY",
            "upcoming_evidence_status": "NOT_REPORTED",
        },
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
