"""Semantic integration tests for the Dividend Bot daily cycle."""
from __future__ import annotations

from pathlib import Path

import run_daily_dividend_cycle as runner
from master_portfolio_orchestrator import STAGE_ORDER


def test_execute_all_stages_generates_every_stage_file(tmp_path):
    payloads, warnings, errors = runner.execute_all_stages(root_path=str(tmp_path))
    assert errors == []
    assert warnings == []
    assert set(payloads) == set(STAGE_ORDER)
    for stage_name, filename in runner.DEFAULT_INPUT_FILES.items():
        assert (tmp_path / filename).exists(), stage_name


def test_daily_command_center_receives_real_upstream_payloads(tmp_path):
    payloads, _, errors = runner.execute_all_stages(root_path=str(tmp_path))
    assert errors == []
    command = payloads["daily_command_center"]
    expected_inputs = {
        "portfolio_lifecycle",
        "income_reinvestment",
        "portfolio_rebalance",
        "portfolio_construction",
        "capital_allocation",
        "portfolio_decision",
        "conviction",
        "entry_score",
        "opportunity_pairing",
        "dividend_ranking",
    }
    assert expected_inputs.issubset(set(command.get("available_inputs", [])))
    assert command.get("missing_inputs", []) == []


def test_portfolio_decision_records_upstream_file_availability(tmp_path):
    payloads, _, errors = runner.execute_all_stages(root_path=str(tmp_path))
    assert errors == []
    decision = payloads["portfolio_decision"]
    assert decision["available_input_files"]
    assert decision["missing_input_files"] == []


def test_full_cycle_remains_complete_after_semantic_wiring(tmp_path):
    payload = runner.run_daily_dividend_cycle(root_path=str(tmp_path))
    assert payload["run_status"] == "COMPLETE"
    assert payload["available_stage_count"] == len(STAGE_ORDER)
    assert payload["missing_stage_count"] == 0
    assert payload["invalid_stage_count"] == 0
    assert payload["errors"] == []


def test_runner_uses_stage_input_adapter():
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert "prepare_stage_kwargs" in source
    assert "payload = builder(**kwargs)" in source
