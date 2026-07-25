from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.dividend_bot import enterprise_dividend_learning_integration as module


def test_safety_constants_are_locked():
    assert module.PAPER_TRADE_MODE is True
    assert module.LIVE_TRADING_ENABLED is False
    assert module.BROKER_EXECUTION_ENABLED is False
    assert module.ADVISORY_ONLY is True
    assert module.APPEND_ONLY is True
    assert module.POLICY_AUTO_CHANGE_ENABLED is False


def test_empty_inputs_produce_partial_report_and_warnings():
    report = module.build_enterprise_dividend_learning(generated_at_utc="2026-07-25T00:00:00Z")
    assert report["status"] == "PARTIAL"
    assert len(report["warnings"]) == 4
    assert report["summary"]["total_learning_record_count"] == 1


def test_forecast_accuracy_is_calculated():
    report = module.build_enterprise_dividend_learning(
        forecasts=[{"symbol": "ABC", "period": "2026-07", "forecast_income": 100}],
        actual_income=[{"symbol": "ABC", "period": "2026-07", "actual_income": 90}],
        generated_at_utc="2026-07-25T00:00:00Z",
    )
    metric = report["forecast_metrics"][0]
    assert metric["forecast_error"] == -10.0
    assert metric["absolute_percentage_error"] == 10.0
    assert metric["accuracy_percent"] == 90.0


def test_zero_forecast_avoids_division_error():
    report = module.build_enterprise_dividend_learning(
        forecasts=[{"symbol": "ABC", "period": "P1", "forecast_income": 0}],
        actual_income=[{"symbol": "ABC", "period": "P1", "actual_income": 10}],
    )
    assert report["forecast_metrics"][0]["absolute_percentage_error"] == 0.0


def test_unmatched_forecast_is_not_compared():
    report = module.build_enterprise_dividend_learning(
        forecasts=[{"symbol": "ABC", "period": "P1", "forecast_income": 10}],
        actual_income=[{"symbol": "ABC", "period": "P2", "actual_income": 10}],
    )
    assert report["forecast_metrics"] == []


def test_low_accuracy_generates_high_priority_recommendation():
    report = module.build_enterprise_dividend_learning(
        forecasts=[{"symbol": "ABC", "period": "P1", "forecast_income": 100}],
        actual_income=[{"symbol": "ABC", "period": "P1", "actual_income": 50}],
    )
    recommendation = report["recommendations"][0]
    assert recommendation["priority"] == "HIGH"
    assert recommendation["category"] == "FORECAST_METHOD"
    assert recommendation["automatic_policy_change"] is False


def test_moderate_accuracy_generates_calibration_recommendation():
    report = module.build_enterprise_dividend_learning(
        forecasts=[{"symbol": "ABC", "period": "P1", "forecast_income": 100}],
        actual_income=[{"symbol": "ABC", "period": "P1", "actual_income": 85}],
    )
    assert report["recommendations"][0]["category"] == "FORECAST_CALIBRATION"


def test_good_accuracy_defaults_to_monitoring_recommendation():
    report = module.build_enterprise_dividend_learning(
        forecasts=[{"symbol": "ABC", "period": "P1", "forecast_income": 100}],
        actual_income=[{"symbol": "ABC", "period": "P1", "actual_income": 100}],
    )
    assert report["recommendations"][0]["category"] == "MONITORING"


def test_alert_is_joined_to_review():
    report = module.build_enterprise_dividend_learning(
        alerts=[{"alert_id": "A1", "symbol": "ABC", "alert_type": "DIVIDEND_CUT", "severity": "HIGH"}],
        reviews=[{"review_id": "R1", "alert_id": "A1", "status": "RESOLVED", "outcome": "CONFIRMED"}],
    )
    metric = report["alert_metrics"][0]
    assert metric["review_id"] == "R1"
    assert metric["confirmed_alert"] is True


def test_false_alert_is_detected_from_outcome():
    report = module.build_enterprise_dividend_learning(
        alerts=[{"alert_id": "A1", "symbol": "ABC", "alert_type": "LOW_CONFIDENCE", "severity": "LOW"}],
        reviews=[{"review_id": "R1", "alert_id": "A1", "status": "RESOLVED", "outcome": "FALSE_ALERT"}],
    )
    assert report["alert_metrics"][0]["false_alert"] is True
    assert report["summary"]["false_alert_count"] == 1


def test_false_alert_rate_generates_threshold_recommendation():
    alerts = [
        {"alert_id": "A1", "symbol": "A", "alert_type": "LOW_CONFIDENCE", "severity": "LOW"},
        {"alert_id": "A2", "symbol": "B", "alert_type": "LOW_CONFIDENCE", "severity": "LOW"},
        {"alert_id": "A3", "symbol": "C", "alert_type": "LOW_CONFIDENCE", "severity": "LOW"},
        {"alert_id": "A4", "symbol": "D", "alert_type": "LOW_CONFIDENCE", "severity": "LOW"},
    ]
    reviews = [
        {"review_id": f"R{i}", "alert_id": f"A{i}", "status": "RESOLVED", "outcome": "FALSE_ALERT" if i == 1 else "CONFIRMED"}
        for i in range(1, 5)
    ]
    report = module.build_enterprise_dividend_learning(alerts=alerts, reviews=reviews)
    assert any(item["category"] == "ALERT_THRESHOLD" for item in report["recommendations"])


def test_only_terminal_review_outcomes_create_learning_records():
    alerts = [{"alert_id": "A1", "alert_type": "REVIEW_REQUIRED"}, {"alert_id": "A2", "alert_type": "REVIEW_REQUIRED"}]
    reviews = [
        {"review_id": "R1", "alert_id": "A1", "status": "OPEN"},
        {"review_id": "R2", "alert_id": "A2", "status": "ESCALATED", "outcome": "ACTION_REQUIRED"},
    ]
    report = module.build_enterprise_dividend_learning(alerts=alerts, reviews=reviews)
    outcome_records = [row for row in report["appended_learning_records"] if row["record_type"] == "ALERT_REVIEW_OUTCOME"]
    assert len(outcome_records) == 1
    assert outcome_records[0]["subject"] == "A2"


def test_learning_ids_are_deterministic():
    kwargs = dict(
        forecasts=[{"symbol": "ABC", "period": "P1", "forecast_income": 100}],
        actual_income=[{"symbol": "ABC", "period": "P1", "actual_income": 90}],
        generated_at_utc="2026-07-25T00:00:00Z",
    )
    first = module.build_enterprise_dividend_learning(**kwargs)
    second = module.build_enterprise_dividend_learning(**kwargs)
    assert [row["learning_record_id"] for row in first["learning_records"]] == [row["learning_record_id"] for row in second["learning_records"]]


def test_existing_records_are_preserved_and_not_duplicated():
    first = module.build_enterprise_dividend_learning(
        forecasts=[{"symbol": "ABC", "period": "P1", "forecast_income": 100}],
        actual_income=[{"symbol": "ABC", "period": "P1", "actual_income": 90}],
        generated_at_utc="2026-07-25T00:00:00Z",
    )
    second = module.build_enterprise_dividend_learning(
        forecasts=[{"symbol": "ABC", "period": "P1", "forecast_income": 100}],
        actual_income=[{"symbol": "ABC", "period": "P1", "actual_income": 90}],
        existing_learning_records=first["learning_records"],
        generated_at_utc="2026-07-26T00:00:00Z",
    )
    assert second["summary"]["appended_learning_record_count"] == 0
    assert second["learning_records"] == first["learning_records"]


def test_existing_record_order_is_preserved():
    existing = [
        {"learning_record_id": "L1", "record_key": "K1"},
        {"learning_record_id": "L2", "record_key": "K2"},
    ]
    report = module.build_enterprise_dividend_learning(existing_learning_records=existing)
    assert report["learning_records"][:2] == existing


def test_summary_counts_match_records():
    report = module.build_enterprise_dividend_learning(
        forecasts=[{"symbol": "ABC", "period": "P1", "forecast_income": 100}],
        actual_income=[{"symbol": "ABC", "period": "P1", "actual_income": 100}],
    )
    assert report["summary"]["total_learning_record_count"] == len(report["learning_records"])
    assert report["summary"]["appended_learning_record_count"] == len(report["appended_learning_records"])


def test_output_metadata_is_complete():
    report = module.build_enterprise_dividend_learning()
    for key in (
        "module_name", "module_version", "schema_version", "generated_at_utc",
        "paper_trade_mode", "advisory_only", "append_only", "policy_auto_change_enabled",
    ):
        assert key in report


def test_governance_forbids_execution_and_policy_changes():
    governance = module.build_enterprise_dividend_learning()["governance"]
    assert governance["human_approval_required"] is True
    assert governance["recommendations_change_policy_automatically"] is False
    assert governance["capital_movement_allowed"] is False
    assert governance["brokerage_execution_allowed"] is False


def test_markdown_contains_governance_sections():
    markdown = module.render_enterprise_dividend_learning_markdown(module.build_enterprise_dividend_learning())
    assert "# Enterprise Dividend Learning" in markdown
    assert "## Recommendations" in markdown
    assert "## Governance" in markdown
    assert "Automatic policy changes: **False**" in markdown


def test_write_outputs_json_and_markdown(tmp_path: Path):
    report = module.build_enterprise_dividend_learning()
    paths = module.write_enterprise_dividend_learning(report, tmp_path)
    assert Path(paths["json"]).exists()
    assert Path(paths["markdown"]).exists()
    loaded = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert loaded["module_name"] == module.MODULE_NAME


def test_build_and_write_adds_output_files(tmp_path: Path):
    report = module.build_and_write_enterprise_dividend_learning(tmp_path)
    assert set(report["output_files"]) == {"json", "markdown"}


def test_nonfinite_values_are_safely_normalized():
    report = module.build_enterprise_dividend_learning(
        forecasts=[{"symbol": "ABC", "period": "P1", "forecast_income": float("inf")}],
        actual_income=[{"symbol": "ABC", "period": "P1", "actual_income": float("nan")}],
    )
    metric = report["forecast_metrics"][0]
    assert metric["forecast_income"] == 0.0
    assert metric["actual_income"] == 0.0


def test_input_mappings_are_not_mutated():
    forecast = {"symbol": "ABC", "period": "P1", "forecast_income": 100}
    actual = {"symbol": "ABC", "period": "P1", "actual_income": 90}
    module.build_enterprise_dividend_learning(forecasts=[forecast], actual_income=[actual])
    assert forecast == {"symbol": "ABC", "period": "P1", "forecast_income": 100}
    assert actual == {"symbol": "ABC", "period": "P1", "actual_income": 90}


def test_root_compatibility_import():
    import enterprise_dividend_learning_integration as compatibility
    assert compatibility.MODULE_NAME == module.MODULE_NAME


def test_record_payload_is_traceable():
    report = module.build_enterprise_dividend_learning(
        forecasts=[{"symbol": "ABC", "period": "P1", "forecast_income": 100, "source_report": "forecast.json"}],
        actual_income=[{"symbol": "ABC", "period": "P1", "actual_income": 90, "source_report": "actual.json"}],
    )
    record = next(row for row in report["learning_records"] if row["record_type"] == "FORECAST_OUTCOME")
    assert record["payload"]["forecast_source"] == "forecast.json"
    assert record["payload"]["actual_source"] == "actual.json"


def test_recommendations_require_human_approval():
    report = module.build_enterprise_dividend_learning()
    assert all(item["requires_human_approval"] is True for item in report["recommendations"])
    assert all(item["automatic_policy_change"] is False for item in report["recommendations"])
