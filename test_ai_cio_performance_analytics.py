import json
from pathlib import Path

import ai_cio_performance_analytics as module


def sample_inputs():
    decisions = [
        {"action": "KEEP", "decision_stability_score": 84, "evidence_confidence": 94, "portfolio_changed": False},
        {"action": "REPLACE", "decision_stability_score": 80, "evidence_confidence": 90, "portfolio_changed": True},
        {"action": "PARK IN SGOV", "decision_stability_score": 88, "evidence_confidence": 96, "portfolio_changed": True},
        {"action": "KEEP", "decision_stability_score": 82, "evidence_confidence": 92, "portfolio_changed": False},
    ]
    replacements = [
        {"status": "COMPLETED", "score_difference": 10, "replacement_value": 5, "turnover_cost": 1},
        {"status": "COMPLETED", "score_difference": 8, "replacement_value": -2, "turnover_cost": 1},
        {"status": "PENDING", "score_difference": 12},
    ]
    protection = [{"estimated_protection_value": 4, "parking_days": 5}]
    lifecycle = [{"days_held": 30}, {"days_held": 60, "sgov_parking_days": 3}]
    return decisions, replacements, protection, lifecycle


def build():
    return module.build_ai_cio_performance_analytics(*sample_inputs())


def test_public_functions_exist():
    for name in (
        "build_ai_cio_performance_analytics",
        "format_ai_cio_performance_analytics_markdown",
        "format_ai_cio_performance_analytics_html",
        "write_ai_cio_performance_analytics",
        "build_and_write_ai_cio_performance_analytics",
    ):
        assert callable(getattr(module, name))


def test_paper_only_flags():
    report = build()
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False


def test_decision_counts_and_change_rate():
    metrics = build()["metrics"]
    assert metrics["total_decisions"] == 4
    assert metrics["portfolio_changes"] == 2
    assert metrics["portfolio_change_rate"] == 50.0


def test_replacement_success_and_false_positive_rates():
    metrics = build()["metrics"]
    assert metrics["completed_replacements"] == 2
    assert metrics["pending_replacements"] == 1
    assert metrics["replacement_success_rate"] == 50.0
    assert metrics["false_positive_replacement_rate"] == 50.0


def test_average_scores_and_holding_period():
    metrics = build()["metrics"]
    assert metrics["average_capital_efficiency_improvement"] == 9.0
    assert metrics["average_decision_stability_score"] == 83.5
    assert metrics["average_evidence_confidence"] == 93.0
    assert metrics["average_holding_period_days"] == 45.0


def test_sgov_duration_is_measured():
    assert build()["metrics"]["average_sgov_parking_days"] == 4.0


def test_value_attribution_math():
    metrics = build()["metrics"]
    assert metrics["estimated_protection_value"] == 4.0
    assert metrics["replacement_value_created"] == 3.0
    assert metrics["portfolio_turnover_cost"] == 2.0
    assert metrics["net_decision_value"] == 5.0


def test_self_assessment_is_bounded_and_graded():
    metrics = build()["metrics"]
    assert 0 <= metrics["self_assessment_score"] <= 100
    assert metrics["self_assessment_grade"] in {"A", "B", "C", "D", "F"}


def test_improvement_findings_never_auto_apply():
    findings = build()["improvement_findings"]
    assert findings
    assert all(item["automatic_change_allowed"] is False for item in findings)
    assert all(item["requires_human_review"] is True for item in findings)


def test_low_sample_warns_against_threshold_changes():
    report = module.build_ai_cio_performance_analytics(
        decisions=[{"action": "KEEP"}],
        replacements=[],
    )
    text = json.dumps(report)
    assert "More replacement history is needed" in text
    assert report["automatic_policy_changes_allowed"] is False


def test_empty_inputs_are_valid_with_warnings():
    report = module.build_ai_cio_performance_analytics()
    assert report["metrics"]["total_decisions"] == 0
    assert report["warnings"]
    assert report["errors"] == []


def test_nonfinite_numbers_are_ignored():
    report = module.build_ai_cio_performance_analytics(
        decisions=[{"decision_stability_score": float("inf"), "evidence_confidence": float("nan")}],
        lifecycle_records=[{"days_held": float("inf")}],
    )
    metrics = report["metrics"]
    assert metrics["average_decision_stability_score"] is None
    assert metrics["average_evidence_confidence"] is None
    assert metrics["average_holding_period_days"] is None


def test_metric_details_cover_investor_facing_metrics():
    report = build()
    for key in (
        "portfolio_change_rate",
        "replacement_success_rate",
        "false_positive_replacement_rate",
        "average_decision_stability_score",
        "average_evidence_confidence",
        "estimated_protection_value",
        "replacement_value_created",
        "portfolio_turnover_cost",
        "net_decision_value",
        "self_assessment_score",
    ):
        detail = report["metric_details"][key]
        assert detail["definition"]
        assert detail["calculation"]
        assert detail["why_it_matters"]


def test_markdown_uses_full_names_and_more_links():
    markdown = module.format_ai_cio_performance_analytics_markdown(build())
    assert "AI CIO Self-Assessment Score" in markdown
    assert "Replacement Success Rate" in markdown
    assert "False-Positive Replacement Rate" in markdown
    assert "Decision Stability Score" in markdown
    assert "Evidence Confidence" in markdown
    assert "More..." in markdown


def test_html_contains_report_and_safety_language():
    output = module.format_ai_cio_performance_analytics_html(build())
    assert "AI CIO Performance Analytics" in output
    assert "does not place orders" in output


def test_write_outputs(tmp_path):
    report = build()
    paths = module.write_ai_cio_performance_analytics(
        report,
        tmp_path / "report.json",
        tmp_path / "report.md",
        tmp_path / "report.html",
    )
    assert set(paths) == {"json", "markdown", "html"}
    assert all(Path(path).exists() for path in paths.values())
    loaded = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert loaded["module_name"] == module.MODULE_NAME


def test_build_and_write_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report = module.build_and_write_ai_cio_performance_analytics()
    assert "output_files" in report
    assert Path("ai_cio_performance_analytics.json").exists()
    assert Path("ai_cio_performance_analytics.md").exists()
    assert Path("ai_cio_performance_analytics.html").exists()


def test_source_contains_no_restricted_execution_calls():
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = ("robin_stocks", "place_order(", "execute_trade(", "subprocess", "os.system", "requests.")
    assert not any(term in source for term in forbidden)
