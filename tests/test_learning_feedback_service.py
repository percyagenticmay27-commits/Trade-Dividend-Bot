import json
from pathlib import Path

import pytest

from src.dividend_bot import learning_feedback_service as service


def recommendation():
    return {
        "paper_trade_mode": True,
        "recommendations": [
            {"strategy_id": "DIV", "recommended_weight_pct": 45},
            {"strategy_id": "SWING", "recommended_weight_pct": 35},
        ],
    }


def analytics():
    return {
        "strategies": [
            {"strategy_id": "DIV", "performance_score": 85, "classification": "STRONG", "sample_size": 50},
            {"strategy_id": "SWING", "performance_score": 45, "classification": "WATCH", "sample_size": 50},
        ]
    }


def test_safety_constants_are_locked():
    assert service.PAPER_TRADE_MODE is True
    assert service.LIVE_TRADING_ENABLED is False
    assert service.BROKER_EXECUTION_ENABLED is False
    assert service.AUTOMATIC_POLICY_CHANGES_ENABLED is False
    assert service.AUTOMATIC_WEIGHT_CHANGES_ENABLED is False


def test_outperformance_suggests_modest_increase():
    report = service.build_learning_feedback(recommendation(), analytics(), generated_at_utc="2026-01-01T00:00:00Z")
    item = next(x for x in report.feedback if x.strategy_id == "DIV")
    assert item.outcome == "OUTPERFORMED"
    assert item.suggested_action == "CONSIDER_MODEST_INCREASE"


def test_underperformance_suggests_modest_decrease():
    report = service.build_learning_feedback(recommendation(), analytics())
    item = next(x for x in report.feedback if x.strategy_id == "SWING")
    assert item.outcome == "UNDERPERFORMED"
    assert item.suggested_action == "CONSIDER_MODEST_DECREASE"


def test_small_sample_blocks_adjustment():
    data = analytics()
    data["strategies"][0]["sample_size"] = 5
    report = service.build_learning_feedback(recommendation(), data, min_sample_size=20)
    item = next(x for x in report.feedback if x.strategy_id == "DIV")
    assert item.outcome == "INSUFFICIENT_EVIDENCE"
    assert item.suggested_action == "NO_CHANGE"


def test_missing_performance_record_is_insufficient():
    report = service.build_learning_feedback(recommendation(), {"strategies": []})
    assert all(item.outcome == "INSUFFICIENT_EVIDENCE" for item in report.feedback)


def test_no_recommendations_adds_warning():
    report = service.build_learning_feedback({"recommendations": []}, analytics())
    assert "no prior strategy recommendations were available" in report.warnings


def test_feedback_is_sorted_by_strategy_id():
    report = service.build_learning_feedback(recommendation(), analytics())
    assert [item.strategy_id for item in report.feedback] == ["DIV", "SWING"]


def test_schema_and_governance_are_present():
    data = service.build_learning_feedback(recommendation(), analytics()).to_dict()
    assert data["module_name"] == "learning_feedback_service"
    assert data["schema_version"] == "1.0"
    assert data["governance"]["automatic_application_allowed"] is False
    assert data["governance"]["human_review_required"] is True


def test_missing_required_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        service.build_learning_feedback_from_files(tmp_path / "missing.json", tmp_path / "also-missing.json")


def test_invalid_json_raises(tmp_path: Path):
    bad = tmp_path / "bad.json"
    good = tmp_path / "good.json"
    bad.write_text("{", encoding="utf-8")
    good.write_text(json.dumps(analytics()), encoding="utf-8")
    with pytest.raises(ValueError):
        service.build_learning_feedback_from_files(bad, good)


def test_json_and_markdown_outputs(tmp_path: Path):
    report = service.build_learning_feedback(recommendation(), analytics(), generated_at_utc="2026-01-01T00:00:00Z")
    outputs = service.write_learning_feedback(report, tmp_path)
    assert Path(outputs["json"]).name == "learning_feedback.json"
    assert Path(outputs["markdown"]).name == "learning_feedback.md"
    assert "AI CIO Learning and Feedback" in Path(outputs["markdown"]).read_text(encoding="utf-8")


def test_build_and_write_standard_names(tmp_path: Path):
    rec = tmp_path / "recommendation.json"
    perf = tmp_path / "performance.json"
    rec.write_text(json.dumps(recommendation()), encoding="utf-8")
    perf.write_text(json.dumps(analytics()), encoding="utf-8")
    outputs = service.build_and_write_learning_feedback(rec, perf, tmp_path / "results")
    assert Path(outputs["json"]).exists()
    assert Path(outputs["markdown"]).exists()
