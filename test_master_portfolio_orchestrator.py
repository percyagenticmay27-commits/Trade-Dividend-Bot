"""Tests for master_portfolio_orchestrator.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import master_portfolio_orchestrator as engine


def test_dataclasses_exist():
    assert hasattr(engine, "OrchestrationStageResult")
    assert hasattr(engine, "MasterPortfolioOrchestrationReport")


def test_public_functions_exist():
    for name in [
        "build_master_portfolio_orchestration_report",
        "validate_master_portfolio_orchestration_report",
        "write_master_portfolio_orchestration_report_json",
        "read_master_portfolio_orchestration_report_json",
        "format_master_portfolio_orchestration_report_markdown",
        "write_master_portfolio_orchestration_report_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_stage_order_matches_approved_workflow():
    assert engine.STAGE_ORDER == [
        "market_regime",
        "market_intelligence",
        "momentum_score",
        "entry_score",
        "conviction",
        "dividend_ranking",
        "opportunity_pairing",
        "portfolio_decision",
        "capital_allocation",
        "portfolio_construction",
        "portfolio_rebalance",
        "income_reinvestment",
        "portfolio_lifecycle",
        "daily_command_center",
        "weekly_portfolio_review",
        "strategy_performance_analytics",
        "monthly_portfolio_review",
    ]


def test_default_missing_inputs_produce_partial_valid_report(tmp_path):
    payload = engine.build_master_portfolio_orchestration_report(root_path=str(tmp_path))
    assert engine.validate_master_portfolio_orchestration_report(payload) is True
    assert payload["run_status"] == "PARTIAL"
    assert payload["available_stage_count"] == 0
    assert payload["missing_stage_count"] == len(engine.STAGE_ORDER)
    assert payload["invalid_stage_count"] == 0
    assert len(payload["warnings"]) == len(engine.STAGE_ORDER)
    assert payload["errors"] == []


def test_all_supplied_stage_payloads_produce_complete_report():
    stage_payloads = {
        stage: {
            "module_name": f"{stage}_module",
            "module_version": "1.0.0",
            "paper_trade_mode": True,
        }
        for stage in engine.STAGE_ORDER
    }
    payload = engine.build_master_portfolio_orchestration_report(stage_payloads=stage_payloads)
    assert payload["run_status"] == "COMPLETE"
    assert payload["available_stage_count"] == len(engine.STAGE_ORDER)
    assert payload["missing_stage_count"] == 0
    assert payload["invalid_stage_count"] == 0
    assert payload["warnings"] == []
    assert payload["errors"] == []


def test_supplied_stage_metadata_is_recorded():
    payload = engine.build_master_portfolio_orchestration_report(
        stage_payloads={
            "market_regime": {
                "module_name": "market_regime_engine",
                "module_version": "1.0.0",
            }
        }
    )
    row = payload["stage_results"][0]
    assert row["stage_name"] == "market_regime"
    assert row["status"] == "AVAILABLE"
    assert row["module_name"] == "market_regime_engine"
    assert row["module_version"] == "1.0.0"


def test_invalid_supplied_stage_produces_error_status():
    payload = engine.build_master_portfolio_orchestration_report(
        stage_payloads={"market_regime": ["not", "a", "mapping"]}
    )
    assert payload["run_status"] == "ERROR"
    assert payload["invalid_stage_count"] == 1
    assert payload["errors"]
    row = payload["stage_results"][0]
    assert row["status"] == "INVALID"


def test_valid_json_file_is_loaded(tmp_path):
    path = tmp_path / engine.DEFAULT_INPUT_FILES["market_regime"]
    path.write_text(
        json.dumps({"module_name": "market_regime_engine", "module_version": "1.0.0"}),
        encoding="utf-8",
    )
    payload = engine.build_master_portfolio_orchestration_report(root_path=str(tmp_path))
    row = payload["stage_results"][0]
    assert row["status"] == "AVAILABLE"
    assert row["module_name"] == "market_regime_engine"


def test_malformed_json_file_is_invalid(tmp_path):
    path = tmp_path / engine.DEFAULT_INPUT_FILES["market_regime"]
    path.write_text("{bad json", encoding="utf-8")
    payload = engine.build_master_portfolio_orchestration_report(root_path=str(tmp_path))
    assert payload["run_status"] == "ERROR"
    assert payload["invalid_stage_count"] == 1
    assert payload["stage_results"][0]["status"] == "INVALID"


def test_non_object_json_file_is_invalid(tmp_path):
    path = tmp_path / engine.DEFAULT_INPUT_FILES["market_regime"]
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    payload = engine.build_master_portfolio_orchestration_report(root_path=str(tmp_path))
    assert payload["invalid_stage_count"] == 1
    assert payload["stage_results"][0]["status"] == "INVALID"


def test_custom_input_file_mapping_is_supported(tmp_path):
    custom = tmp_path / "custom_regime.json"
    custom.write_text(json.dumps({"module_name": "custom", "module_version": "2.0"}), encoding="utf-8")
    payload = engine.build_master_portfolio_orchestration_report(
        root_path=str(tmp_path),
        input_files={"market_regime": "custom_regime.json"},
    )
    row = payload["stage_results"][0]
    assert row["status"] == "AVAILABLE"
    assert row["source_path"] == "custom_regime.json"


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_master_portfolio_orchestration_report(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_master_portfolio_orchestration_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_master_portfolio_orchestration_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_master_portfolio_orchestration_report()
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_master_portfolio_orchestration_report(bad)


def test_validate_rejects_bad_stage_order():
    payload = engine.build_master_portfolio_orchestration_report()
    bad = dict(payload)
    bad["stage_order"] = list(reversed(engine.STAGE_ORDER))
    with pytest.raises(ValueError):
        engine.validate_master_portfolio_orchestration_report(bad)


def test_validate_rejects_bad_counts():
    payload = engine.build_master_portfolio_orchestration_report()
    bad = dict(payload)
    bad["missing_stage_count"] += 1
    with pytest.raises(ValueError):
        engine.validate_master_portfolio_orchestration_report(bad)


def test_json_and_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.write_master_portfolio_orchestration_report_json()
    assert engine.read_master_portfolio_orchestration_report_json() == payload
    engine.write_master_portfolio_orchestration_report_markdown()
    assert Path("master_portfolio_orchestration_report.json").exists()
    assert Path("master_portfolio_orchestration_report.md").exists()
    markdown = engine.format_master_portfolio_orchestration_report_markdown(payload)
    assert "# Master Portfolio Orchestration Report" in markdown
    assert "## Stage Results" in markdown
    assert "## Safety Guarantees" in markdown


def test_static_safety_no_restricted_execution_terms():
    source = Path(engine.__file__).read_text(encoding="utf-8").lower()
    restricted = [
        "import " + "robinhood",
        "from " + "robinhood",
        "import robin" + "_stocks",
        "from robin" + "_stocks",
        "place" + "_order(",
        "submit" + "_order(",
        "execute" + "_order(",
        "real" + "_order",
        "live" + "_order",
    ]
    for item in restricted:
        assert item not in source


def test_static_safety_no_process_or_network_terms():
    source = Path(engine.__file__).read_text(encoding="utf-8")
    restricted = [
        "import sub" + "process",
        "from sub" + "process",
        "sub" + "process.",
        "P" + "open(",
        "os." + "system(",
        "." + "system(",
        "requests.",
        "urllib." + "request",
        "http." + "client",
        "socket.",
    ]
    for item in restricted:
        assert item not in source
