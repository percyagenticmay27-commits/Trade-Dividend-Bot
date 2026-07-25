from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.dividend_bot import enterprise_dividend_strategy_health_integration as module


def test_safety_constants_are_locked():
    assert module.PAPER_TRADE_MODE is True
    assert module.LIVE_TRADING_ENABLED is False
    assert module.BROKER_EXECUTION_ENABLED is False
    assert module.REPORTING_ONLY is True
    assert module.ADVISORY_ONLY is True
    assert module.POLICY_CHANGE_ENABLED is False


def test_supported_health_statuses_are_locked():
    assert module.HEALTH_STATUSES == {"HEALTHY", "WATCH", "DEGRADED", "CRITICAL"}


def test_empty_inputs_produce_valid_partial_report_and_warnings():
    report = module.build_enterprise_dividend_strategy_health(generated_at_utc="2026-07-25T00:00:00Z")
    assert report["health_status"] in module.HEALTH_STATUSES
    assert report["summary"]["metric_count"] == 10
    assert len(report["warnings"]) == 10
    assert report["governance"]["may_execute_trades"] is False


def test_healthy_strategy_classification():
    report = module.build_enterprise_dividend_strategy_health(
        alerts_report={"alerts": []},
        reviews_report={"reviews": [{"status": "RESOLVED"}]},
        learning_report={"summary": {"forecast_accuracy_percent": 95}, "learning_records": []},
        cio_advisory_report={"recommendations": [{"recommendation": "HOLD"}]},
        replacement_report={"comparisons": [{"recommendation": "HOLD"}]},
        confidence_report={"summary": {"confidence_score": 92, "evidence_completeness_percent": 98}},
        forecast_report={"summary": {"forecast_accuracy_percent": 95}},
        analytics_report={"summary": {"income_growth_percent": 5, "evidence_completeness_percent": 98}},
        investor_dashboard={"summary": {"largest_position_percent": 15, "largest_sector_percent": 30}},
    )
    assert report["health_status"] == "HEALTHY"
    assert report["health_score"] >= 80


def test_critical_alert_ratio_forces_critical():
    report = module.build_enterprise_dividend_strategy_health(
        alerts_report={"alerts": [{"severity": "CRITICAL"}, {"severity": "HIGH"}]},
        confidence_report={"summary": {"confidence_score": 90, "evidence_completeness_percent": 100}},
        forecast_report={"summary": {"forecast_accuracy_percent": 95}},
        analytics_report={"summary": {"income_growth_percent": 4, "evidence_completeness_percent": 100}},
    )
    assert report["health_status"] == "CRITICAL"
    assert any(item["code"] == "CRITICAL_ALERTS_PRESENT" for item in report["risk_flags"])


def test_evidence_below_40_forces_critical():
    report = module.build_enterprise_dividend_strategy_health(
        confidence_report={"summary": {"confidence_score": 90, "evidence_completeness_percent": 30}},
        forecast_report={"summary": {"forecast_accuracy_percent": 95}},
        analytics_report={"summary": {"income_growth_percent": 5, "evidence_completeness_percent": 30}},
    )
    assert report["health_status"] == "CRITICAL"
    assert any(item["code"] == "EVIDENCE_INCOMPLETE" for item in report["risk_flags"])


def test_forecast_accuracy_metric_uses_forecast_report():
    report = module.build_enterprise_dividend_strategy_health(
        forecast_report={"summary": {"forecast_accuracy_percent": 88}}
    )
    metric = next(item for item in report["metrics"] if item["metric"] == "forecast_accuracy")
    assert metric["value"] == 88
    assert metric["score"] == 88


def test_learning_forecast_accuracy_is_fallback():
    report = module.build_enterprise_dividend_strategy_health(
        learning_report={"summary": {"average_forecast_accuracy_percent": 83}}
    )
    assert report["summary"]["forecast_accuracy_percent"] == 83


def test_negative_income_growth_generates_flag():
    report = module.build_enterprise_dividend_strategy_health(
        analytics_report={"summary": {"income_growth_percent": -4}}
    )
    assert any(item["code"] == "NEGATIVE_INCOME_GROWTH" for item in report["risk_flags"])


def test_review_completion_and_escalation_rates():
    report = module.build_enterprise_dividend_strategy_health(
        reviews_report={"reviews": [
            {"status": "RESOLVED"}, {"status": "RESOLVED"},
            {"status": "ESCALATED"}, {"status": "OPEN"},
        ]}
    )
    assert report["summary"]["review_completion_percent"] == 50
    assert report["summary"]["escalation_rate_percent"] == 25
    assert any(item["code"] == "LOW_REVIEW_COMPLETION" for item in report["risk_flags"])


def test_no_reviews_defaults_completion_to_100():
    report = module.build_enterprise_dividend_strategy_health(reviews_report={"reviews": []})
    assert report["summary"]["review_completion_percent"] == 100


def test_false_alert_rate_is_calculated():
    report = module.build_enterprise_dividend_strategy_health(
        learning_report={"learning_records": [
            {"alert_id": "A1", "false_alert": True},
            {"alert_id": "A2", "false_alert": False},
            {"alert_id": "A3", "classification": "FALSE_ALERT"},
            {"record_id": "NO_ALERT"},
        ]}
    )
    assert report["summary"]["false_alert_rate_percent"] == pytest.approx(66.67, abs=0.01)
    assert any(item["code"] == "HIGH_FALSE_ALERT_RATE" for item in report["risk_flags"])


def test_position_concentration_flag():
    report = module.build_enterprise_dividend_strategy_health(
        investor_dashboard={"summary": {"largest_position_percent": 31}}
    )
    assert any(item["code"] == "POSITION_CONCENTRATION" for item in report["risk_flags"])


def test_sector_concentration_flag():
    report = module.build_enterprise_dividend_strategy_health(
        investor_dashboard={"summary": {"largest_sector_percent": 51}}
    )
    assert any(item["code"] == "SECTOR_CONCENTRATION" for item in report["risk_flags"])


def test_custom_concentration_thresholds_are_used():
    report = module.build_enterprise_dividend_strategy_health(
        investor_dashboard={"summary": {"largest_position_percent": 21}},
        thresholds={"max_position_concentration": 20},
    )
    assert any(item["code"] == "POSITION_CONCENTRATION" for item in report["risk_flags"])


def test_cio_distribution_counts_supported_actions():
    report = module.build_enterprise_dividend_strategy_health(
        cio_advisory_report={"recommendations": [
            {"recommendation": "HOLD"},
            {"recommendation": "REVIEW"},
            {"recommendation": "EXIT_REVIEW"},
        ]}
    )
    assert report["cio_recommendation_distribution"]["HOLD"] == 1
    assert report["cio_recommendation_distribution"]["EXIT_REVIEW"] == 1


def test_replacement_review_rate_is_calculated():
    report = module.build_enterprise_dividend_strategy_health(
        replacement_report={"comparisons": [
            {"recommendation": "REPLACEMENT_REVIEW"},
            {"recommendation": "HOLD"},
        ]}
    )
    assert report["summary"]["replacement_review_rate_percent"] == 50


def test_metrics_weights_sum_to_one():
    report = module.build_enterprise_dividend_strategy_health()
    assert sum(item["weight"] for item in report["metrics"]) == pytest.approx(1.0)


def test_health_score_matches_weighted_metrics():
    report = module.build_enterprise_dividend_strategy_health()
    assert report["health_score"] == round(sum(item["weighted_score"] for item in report["metrics"]), 2)


def test_nonfinite_values_are_safely_normalized():
    report = module.build_enterprise_dividend_strategy_health(
        forecast_report={"summary": {"forecast_accuracy_percent": float("nan")}},
        analytics_report={"summary": {"income_growth_percent": float("inf")}},
    )
    assert math_is_finite(report["health_score"])
    assert math_is_finite(report["summary"]["forecast_accuracy_percent"])


def math_is_finite(value):
    import math
    return math.isfinite(float(value))


def test_threshold_overrides_only_known_keys():
    report = module.build_enterprise_dividend_strategy_health(
        thresholds={"healthy_min_score": 90, "unknown": 123}
    )
    assert report["thresholds"]["healthy_min_score"] == 90
    assert "unknown" not in report["thresholds"]


def test_risk_flags_are_sorted_by_severity():
    report = module.build_enterprise_dividend_strategy_health(
        alerts_report={"alerts": [{"severity": "CRITICAL"}]},
        forecast_report={"summary": {"forecast_accuracy_percent": 20}},
        analytics_report={"summary": {"income_growth_percent": -5, "evidence_completeness_percent": 50}},
        investor_dashboard={"summary": {"largest_position_percent": 50}},
    )
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    severities = [order[item["severity"]] for item in report["risk_flags"]]
    assert severities == sorted(severities)


def test_healthy_report_has_monitoring_action():
    report = module.build_enterprise_dividend_strategy_health(
        alerts_report={"alerts": []},
        forecast_report={"summary": {"forecast_accuracy_percent": 95}},
        confidence_report={"summary": {"confidence_score": 95, "evidence_completeness_percent": 100}},
        analytics_report={"summary": {"income_growth_percent": 5, "evidence_completeness_percent": 100}},
    )
    assert report["suggested_actions"][-1]["priority"] == "INFO"


def test_markdown_contains_required_sections():
    report = module.build_enterprise_dividend_strategy_health()
    text = module.render_enterprise_dividend_strategy_health_markdown(report)
    for heading in (
        "# Enterprise Dividend Strategy Health",
        "## Executive Summary",
        "## Metric Breakdown",
        "## Risk Flags",
        "## Suggested Actions",
        "## Warnings",
        "## Governance Notes",
    ):
        assert heading in text


def test_write_outputs_json_and_markdown(tmp_path: Path):
    report = module.build_enterprise_dividend_strategy_health(generated_at_utc="2026-07-25T00:00:00Z")
    paths = module.write_enterprise_dividend_strategy_health(report, tmp_path)
    assert Path(paths["json"]).exists()
    assert Path(paths["markdown"]).exists()
    loaded = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert loaded["module_name"] == module.MODULE_NAME


def test_build_and_write_adds_output_paths(tmp_path: Path):
    report = module.build_and_write_enterprise_dividend_strategy_health(output_dir=tmp_path)
    assert set(report["output_files"]) == {"json", "markdown"}


def test_output_metadata_is_complete():
    report = module.build_enterprise_dividend_strategy_health()
    assert report["module_name"] == module.MODULE_NAME
    assert report["module_version"] == "1.0.0"
    assert report["schema_version"] == "1.0"
    assert report["paper_trade_mode"] is True
    assert report["advisory_only"] is True


def test_governance_denies_all_execution_authority():
    report = module.build_enterprise_dividend_strategy_health()
    assert report["governance"] == {
        "human_approval_required": True,
        "may_execute_trades": False,
        "may_move_capital": False,
        "may_change_strategy": False,
        "may_change_policy": False,
    }


def test_identical_inputs_are_deterministic_with_fixed_timestamp():
    kwargs = {
        "alerts_report": {"alerts": [{"severity": "HIGH"}]},
        "generated_at_utc": "2026-07-25T00:00:00Z",
    }
    assert module.build_enterprise_dividend_strategy_health(**kwargs) == module.build_enterprise_dividend_strategy_health(**kwargs)
