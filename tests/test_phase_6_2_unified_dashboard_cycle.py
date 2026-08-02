from __future__ import annotations

import json
from pathlib import Path

import run_enterprise_unified_dashboard_cycle as launcher
from src.dividend_bot.enterprise_unified_dashboard_cycle import (
    run_unified_dashboard_cycle,
)


def _successful_dependencies(calls: list[str]):
    def generate(**kwargs):
        calls.append("generate")
        return {"paths": {"dividend": "d.json", "swing": "s.json"}, "decision_count": 2, "warnings": [], "errors": []}

    def refresh(**kwargs):
        calls.append("refresh")
        return {"paths": {"executive_json": "e.json"}, "registered_strategy_count": 2, "warnings": ["refresh warning"], "errors": []}

    def validate(**kwargs):
        calls.append("validate")
        return {"validation_status": "PASSED", "output_paths": {"json": "v.json"}, "warnings": [], "errors": []}

    return generate, refresh, validate


def test_cycle_runs_generate_refresh_validate_in_order(tmp_path: Path) -> None:
    calls: list[str] = []
    generate, refresh, validate = _successful_dependencies(calls)
    summary = run_unified_dashboard_cycle(root_dir=tmp_path, journal_generator=generate, dashboard_refresher=refresh, dashboard_validator=validate)
    assert calls == ["generate", "refresh", "validate"]
    assert summary["cycle_status"] == "PASSED"
    assert all(step["status"] == "PASSED" for step in summary["steps"].values())


def test_cycle_normalizes_results_and_state_under_root(tmp_path: Path) -> None:
    observed = {}
    generate, _, validate = _successful_dependencies([])
    def refresh(**kwargs):
        observed.update(kwargs)
        return {"paths": {}, "registered_strategy_count": 2, "warnings": [], "errors": []}
    run_unified_dashboard_cycle(root_dir=tmp_path, results_dir="out", state_dir="paper-state", journal_generator=generate, dashboard_refresher=refresh, dashboard_validator=validate)
    assert observed["results_dir"] == tmp_path / "out"
    assert observed["state_dir"] == tmp_path / "paper-state"


def test_generation_exception_fails_closed_and_skips_later_steps(tmp_path: Path) -> None:
    calls: list[str] = []
    def generate(**kwargs):
        raise RuntimeError("source unavailable")
    def forbidden(**kwargs):
        calls.append("called")
        return {}
    summary = run_unified_dashboard_cycle(root_dir=tmp_path, journal_generator=generate, dashboard_refresher=forbidden, dashboard_validator=forbidden)
    assert summary["cycle_status"] == "FAILED"
    assert calls == []
    assert summary["steps"]["dashboard_refresh"]["status"] == "NOT_RUN"
    assert summary["steps"]["unified_validation"]["status"] == "NOT_RUN"


def test_refresh_errors_prevent_stale_artifact_validation(tmp_path: Path) -> None:
    calls: list[str] = []
    generate, _, _ = _successful_dependencies(calls)
    def refresh(**kwargs):
        calls.append("refresh")
        return {"warnings": [], "errors": ["refresh rejected"]}
    def validate(**kwargs):
        calls.append("validate")
        return {}
    summary = run_unified_dashboard_cycle(root_dir=tmp_path, journal_generator=generate, dashboard_refresher=refresh, dashboard_validator=validate)
    assert calls == ["generate", "refresh"]
    assert summary["steps"]["dashboard_refresh"]["status"] == "FAILED"
    assert summary["steps"]["unified_validation"]["status"] == "NOT_RUN"


def test_failed_validation_fails_entire_cycle(tmp_path: Path) -> None:
    calls: list[str] = []
    generate, refresh, _ = _successful_dependencies(calls)
    def validate(**kwargs):
        return {"validation_status": "FAILED", "warnings": [], "errors": ["unsafe state"]}
    summary = run_unified_dashboard_cycle(root_dir=tmp_path, journal_generator=generate, dashboard_refresher=refresh, dashboard_validator=validate)
    assert summary["cycle_status"] == "FAILED"
    assert "unsafe state" in summary["errors"]


def test_cycle_writes_json_and_markdown_summaries(tmp_path: Path) -> None:
    calls: list[str] = []
    generate, refresh, validate = _successful_dependencies(calls)
    summary = run_unified_dashboard_cycle(root_dir=tmp_path, journal_generator=generate, dashboard_refresher=refresh, dashboard_validator=validate)
    json_path = Path(summary["output_paths"]["json"])
    markdown_path = Path(summary["output_paths"]["markdown"])
    assert json.loads(json_path.read_text(encoding="utf-8"))["cycle_status"] == "PASSED"
    assert "# Enterprise Unified Dashboard Cycle" in markdown_path.read_text(encoding="utf-8")


def test_cycle_summary_enforces_paper_only_safety(tmp_path: Path) -> None:
    calls: list[str] = []
    generate, refresh, validate = _successful_dependencies(calls)
    summary = run_unified_dashboard_cycle(root_dir=tmp_path, journal_generator=generate, dashboard_refresher=refresh, dashboard_validator=validate)
    assert summary["paper_trade_mode"] is True
    assert summary["live_trading_enabled"] is False
    assert summary["broker_execution_enabled"] is False
    assert summary["capital_movement_enabled"] is False
    assert summary["reporting_only"] is True


def test_launcher_returns_zero_for_passing_cycle(monkeypatch, capsys) -> None:
    monkeypatch.setattr(launcher, "run_unified_dashboard_cycle", lambda **kwargs: {"cycle_status": "PASSED", "steps": {"unified_validation": {"status": "PASSED"}}, "errors": [], "warnings": []})
    assert launcher.main([]) == 0
    assert "Cycle status: PASSED" in capsys.readouterr().out


def test_launcher_returns_one_for_failed_cycle(monkeypatch) -> None:
    monkeypatch.setattr(launcher, "run_unified_dashboard_cycle", lambda **kwargs: {"cycle_status": "FAILED", "steps": {"decision_journals": {"status": "FAILED"}}, "errors": ["failed"], "warnings": []})
    assert launcher.main([]) == 1
