from __future__ import annotations

import json
from pathlib import Path

import validate_enterprise_unified_dashboard_cycle as launcher
from src.dividend_bot.enterprise_unified_dashboard_cycle_acceptance import (
    REQUIRED_CYCLE_ARTIFACTS,
    run_and_accept_unified_dashboard_cycle,
    snapshot_directory,
    validate_cycle_artifacts,
)


def _write_required(results: Path) -> None:
    results.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_CYCLE_ARTIFACTS:
        content = "{}" if name.endswith(".json") else "# report\n"
        (results / name).write_text(content, encoding="utf-8")


def _passing_cycle(results: Path):
    def run(**kwargs):
        _write_required(results)
        return _cycle_payload()
    return run


def _cycle_payload() -> dict:
    return {
        "cycle_status": "PASSED",
        "warnings": ["safe empty Swing journal"],
        "errors": [],
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
    }


def test_real_cycle_artifacts_and_unchanged_state_pass(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    (state / "paper_cash_account.json").write_text('{"cash": 1000}', encoding="utf-8")
    report = run_and_accept_unified_dashboard_cycle(
        root_dir=tmp_path, cycle_runner=_passing_cycle(tmp_path / "results")
    )
    assert report["acceptance_status"] == "PASSED"
    assert report["protected_state_unchanged"] is True
    assert report["required_artifact_count"] == len(REQUIRED_CYCLE_ARTIFACTS)


def test_snapshot_directory_uses_relative_sha256_manifest(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "state.json").write_text("value", encoding="utf-8")
    snapshot = snapshot_directory(tmp_path)
    assert list(snapshot) == ["nested/state.json"]
    assert len(snapshot["nested/state.json"]) == 64


def test_missing_required_artifact_fails_acceptance(tmp_path: Path) -> None:
    results = tmp_path / "results"
    def run(**kwargs):
        _write_required(results)
        (results / "enterprise_strategy_kpis.json").unlink()
        return _cycle_payload()
    report = run_and_accept_unified_dashboard_cycle(root_dir=tmp_path, cycle_runner=run)
    assert report["acceptance_status"] == "FAILED"
    assert any("artifact is missing" in item for item in report["errors"])


def test_malformed_json_artifact_is_rejected(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write_required(results)
    (results / "ai_cio_executive_dashboard.json").write_text("{bad", encoding="utf-8")
    _, errors = validate_cycle_artifacts(results_dir=results)
    assert any("artifact is unreadable" in item for item in errors)


def test_cycle_failure_fails_acceptance(tmp_path: Path) -> None:
    results = tmp_path / "results"
    def run(**kwargs):
        _write_required(results)
        payload = _cycle_payload()
        payload["cycle_status"] = "FAILED"
        payload["errors"] = ["validation rejected"]
        return payload
    report = run_and_accept_unified_dashboard_cycle(root_dir=tmp_path, cycle_runner=run)
    assert report["acceptance_status"] == "FAILED"
    assert "validation rejected" in report["errors"]


def test_unsafe_cycle_flag_is_rejected(tmp_path: Path) -> None:
    results = tmp_path / "results"
    def run(**kwargs):
        _write_required(results)
        payload = _cycle_payload()
        payload["live_trading_enabled"] = True
        return payload
    report = run_and_accept_unified_dashboard_cycle(root_dir=tmp_path, cycle_runner=run)
    assert report["acceptance_status"] == "FAILED"
    assert any("live_trading_enabled must be False" in item for item in report["errors"])


def test_protected_state_mutation_is_rejected(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    protected = state / "paper_cash_account.json"
    protected.write_text('{"cash": 1000}', encoding="utf-8")
    results = tmp_path / "results"
    def run(**kwargs):
        _write_required(results)
        protected.write_text('{"cash": 0}', encoding="utf-8")
        return _cycle_payload()
    report = run_and_accept_unified_dashboard_cycle(root_dir=tmp_path, cycle_runner=run)
    assert report["acceptance_status"] == "FAILED"
    assert report["protected_state_unchanged"] is False


def test_acceptance_writes_json_and_markdown(tmp_path: Path) -> None:
    report = run_and_accept_unified_dashboard_cycle(
        root_dir=tmp_path, cycle_runner=_passing_cycle(tmp_path / "results")
    )
    saved = json.loads(Path(report["output_paths"]["json"]).read_text(encoding="utf-8"))
    markdown = Path(report["output_paths"]["markdown"]).read_text(encoding="utf-8")
    assert saved["acceptance_status"] == "PASSED"
    assert "# Enterprise Unified Dashboard Cycle Acceptance" in markdown


def test_launcher_exit_codes(monkeypatch, capsys) -> None:
    base = {
        "cycle_status": "PASSED",
        "required_artifact_count": 10,
        "protected_state_unchanged": True,
        "errors": [],
        "warnings": [],
    }
    monkeypatch.setattr(
        launcher,
        "run_and_accept_unified_dashboard_cycle",
        lambda **kwargs: {**base, "acceptance_status": "PASSED"},
    )
    assert launcher.main([]) == 0
    assert "Acceptance status: PASSED" in capsys.readouterr().out
    monkeypatch.setattr(
        launcher,
        "run_and_accept_unified_dashboard_cycle",
        lambda **kwargs: {**base, "acceptance_status": "FAILED", "errors": ["failed"]},
    )
    assert launcher.main([]) == 1
