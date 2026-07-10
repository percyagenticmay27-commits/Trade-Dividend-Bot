"""Tests for decision_review_engine.py."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

import decision_review_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine, "DecisionRecord")
    assert hasattr(engine, "DecisionReview")
    assert hasattr(engine, "DecisionReviewReport")


def test_public_functions_exist():
    for name in [
        "calculate_realized_return_pct",
        "calculate_decision_score",
        "classify_grade",
        "classify_review_status",
        "review_decision",
        "build_decision_review_report",
        "validate_decision_review_report",
        "write_decision_review_report_json",
        "read_decision_review_report_json",
        "write_decision_review_report_csv",
        "format_decision_review_report_markdown",
        "write_decision_review_report_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_empty_report_valid():
    payload = engine.build_decision_review_report()
    assert engine.validate_decision_review_report(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["reporting_only"] is True
    assert payload["review_count"] == 0


def test_realized_return_calculation():
    assert engine.calculate_realized_return_pct(100, 125) == 25.0
    assert engine.calculate_realized_return_pct(100, 80) == -20.0
    assert engine.calculate_realized_return_pct(0, 100) == 0.0


def test_grade_thresholds():
    assert engine.classify_grade(95) == "A+"
    assert engine.classify_grade(90) == "A"
    assert engine.classify_grade(85) == "B+"
    assert engine.classify_grade(75) == "B"
    assert engine.classify_grade(65) == "C"
    assert engine.classify_grade(50) == "D"
    assert engine.classify_grade(49.99) == "F"


def test_review_status_thresholds():
    assert engine.classify_review_status(85) == "SUCCESSFUL"
    assert engine.classify_review_status(70) == "ACCEPTABLE"
    assert engine.classify_review_status(50) == "REVIEW"
    assert engine.classify_review_status(49.99) == "POOR"


def test_successful_buy_review():
    review = engine.review_decision({
        "decision_id": "D1",
        "symbol": "AMD",
        "decision_type": "BUY",
        "decision_date": "2026-01-01",
        "decision_price": 100,
        "review_price": 130,
        "benchmark_return_pct": 10,
        "best_alternative_return_pct": 25,
        "confidence": 0.9,
        "expected_direction": "UP",
        "strategy_name": "Strategy A",
    })
    assert review["symbol"] == "AMD"
    assert review["realized_return_pct"] == 30.0
    assert review["alpha_pct"] == 20.0
    assert review["confidence_was_accurate"] is True
    assert review["review_status"] == "SUCCESSFUL"


def test_opportunity_cost_creates_lesson():
    review = engine.review_decision({
        "decision_id": "D2",
        "symbol": "PLTR",
        "decision_type": "SELL",
        "decision_date": "2026-01-01",
        "decision_price": 100,
        "review_price": 105,
        "benchmark_return_pct": 8,
        "best_alternative_return_pct": 30,
        "confidence": 0.8,
    })
    assert review["opportunity_cost_pct"] == 25.0
    assert any("Opportunity cost" in lesson for lesson in review["lessons"])


def test_high_confidence_inaccuracy_creates_lesson():
    review = engine.review_decision({
        "decision_id": "D3",
        "symbol": "XYZ",
        "decision_type": "BUY",
        "decision_date": "2026-01-01",
        "decision_price": 100,
        "review_price": 80,
        "benchmark_return_pct": 5,
        "best_alternative_return_pct": 10,
        "confidence": 0.9,
        "expected_direction": "UP",
    })
    assert review["confidence_was_accurate"] is False
    assert any("confidence calibration" in lesson.lower() for lesson in review["lessons"])


def test_all_supported_decision_types():
    for decision_type in engine.SUPPORTED_DECISION_TYPES:
        review = engine.review_decision({
            "decision_id": decision_type,
            "symbol": "AAA",
            "decision_type": decision_type,
            "decision_date": "2026-01-01",
            "decision_price": 100,
            "review_price": 110,
        })
        assert review["decision_type"] == decision_type


def test_unsupported_decision_type_fails():
    with pytest.raises(ValueError):
        engine.review_decision({"decision_type": "BAD"})


def test_report_summary_counts():
    payload = engine.build_decision_review_report([
        {"decision_id": "1", "symbol": "A", "decision_type": "BUY", "decision_date": "2026-01-01", "decision_price": 100, "review_price": 140, "benchmark_return_pct": 5},
        {"decision_id": "2", "symbol": "B", "decision_type": "BUY", "decision_date": "2026-01-01", "decision_price": 100, "review_price": 70, "benchmark_return_pct": 5, "best_alternative_return_pct": 20},
    ])
    assert payload["review_count"] == 2
    assert payload["successful_count"] >= 1
    assert payload["review_required_count"] >= 1
    assert payload["learning_lessons"]


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_decision_review_report(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_decision_review_report()
    for field in engine.REQUIRED_REPORT_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_decision_review_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_decision_review_report()
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_decision_review_report(bad)


def test_json_csv_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.write_decision_review_report_json()
    assert engine.read_decision_review_report_json() == payload
    engine.write_decision_review_report_csv()
    engine.write_decision_review_report_markdown()
    assert Path("decision_review_report.json").exists()
    assert Path("decision_review_report.csv").exists()
    assert Path("decision_review_report.md").exists()
    markdown = engine.format_decision_review_report_markdown(payload)
    assert "# Decision Review Report" in markdown
    assert "## Decision Grades" in markdown
    assert "## Learning Lessons" in markdown
    assert "## Safety Guarantees" in markdown


def test_standard_library_imports_only():
    source_path = Path(engine.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    allowed_roots = {"__future__", "csv", "json", "dataclasses", "datetime", "pathlib", "typing"}
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    assert imported_roots <= allowed_roots


def test_module_safety_constants_are_locked():
    assert engine.PAPER_TRADE_MODE is True
    assert engine.LIVE_TRADING_ENABLED is False
    assert engine.BROKER_EXECUTION_ENABLED is False
    assert engine.REPORTING_ONLY is True
