import json
from pathlib import Path

import pytest

from src.dividend_bot import strategy_performance_analytics as analytics

FIXED_TIME = "2026-07-30T05:00:00Z"


def sample_performance():
    return {
        "strategies": [
            {
                "strategy_id": "DIVIDEND",
                "strategy_name": "Dividend Bot",
                "total_return_pct": 12.0,
                "win_rate_pct": 72.0,
                "max_drawdown_pct": 6.0,
                "trade_count": 40,
                "consistency_score": 85.0,
            },
            {
                "strategy_id": "SWING",
                "strategy_name": "Swing Bot",
                "total_return_pct": -4.0,
                "win_rate_pct": 42.0,
                "max_drawdown_pct": 24.0,
                "trade_count": 8,
                "consistency_score": 35.0,
            },
        ]
    }


def test_safety_constants_are_locked():
    assert analytics.PAPER_TRADE_MODE is True
    assert analytics.LIVE_TRADING_ENABLED is False
    assert analytics.BROKER_EXECUTION_ENABLED is False
    assert analytics.CAPITAL_MOVEMENT_ENABLED is False


def test_build_metric_calculates_score_and_classification():
    metric = analytics.build_strategy_metric(sample_performance()["strategies"][0])
    assert metric["strategy_id"] == "DIVIDEND"
    assert 0 <= metric["performance_score"] <= 100
    assert metric["classification"] in {"STRONG", "STABLE", "WATCH", "WEAK"}


def test_negative_return_and_drawdown_create_warnings():
    metric = analytics.build_strategy_metric(sample_performance()["strategies"][1])
    assert "negative return" in metric["warnings"]
    assert "elevated drawdown" in metric["warnings"]
    assert "limited sample size" in metric["warnings"]


def test_report_is_sorted_by_performance_score():
    report = analytics.build_strategy_performance_analytics(sample_performance(), generated_at_utc=FIXED_TIME)
    assert report["strategies"][0]["performance_score"] >= report["strategies"][1]["performance_score"]
    assert report["summary"]["best_strategy_id"] == report["strategies"][0]["strategy_id"]


def test_portfolio_manager_weights_are_merged():
    portfolio = {"recommendations": [{"strategy_id": "DIVIDEND", "recommended_weight_pct": 60}]}
    report = analytics.build_strategy_performance_analytics(sample_performance(), portfolio_manager=portfolio)
    dividend = next(item for item in report["strategies"] if item["strategy_id"] == "DIVIDEND")
    assert dividend["recommended_weight_pct"] == 60.0


def test_empty_performance_is_supported():
    report = analytics.build_strategy_performance_analytics({"strategies": []})
    assert report["summary"]["strategy_count"] == 0
    assert report["summary"]["average_performance_score"] == 0.0


def test_schema_and_governance_are_present():
    report = analytics.build_strategy_performance_analytics(sample_performance())
    assert report["module_name"] == analytics.MODULE_NAME
    assert report["schema_version"] == analytics.SCHEMA_VERSION
    assert report["governance"]["advisory_only"] is True
    assert report["governance"]["automatic_allocation_change_allowed"] is False


def test_json_and_markdown_outputs(tmp_path):
    report = analytics.build_strategy_performance_analytics(sample_performance(), generated_at_utc=FIXED_TIME)
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"
    analytics.write_json(report, json_path)
    analytics.write_markdown(report, md_path)
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded["generated_at_utc"] == FIXED_TIME
    assert "Enterprise Strategy Performance Analytics" in md_path.read_text(encoding="utf-8")


def test_required_input_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        analytics.build_and_write_strategy_performance_analytics(tmp_path / "missing.json", tmp_path)


def test_invalid_required_input_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(ValueError):
        analytics.build_and_write_strategy_performance_analytics(path, tmp_path)


def test_missing_optional_portfolio_creates_warning(tmp_path):
    performance = tmp_path / "performance.json"
    performance.write_text(json.dumps(sample_performance()), encoding="utf-8")
    outputs = analytics.build_and_write_strategy_performance_analytics(
        performance,
        tmp_path / "results",
        portfolio_manager_path=tmp_path / "missing_portfolio.json",
    )
    loaded = json.loads(Path(outputs["json"]).read_text(encoding="utf-8"))
    assert loaded["warnings"]


def test_standard_output_names(tmp_path):
    performance = tmp_path / "performance.json"
    performance.write_text(json.dumps(sample_performance()), encoding="utf-8")
    outputs = analytics.build_and_write_strategy_performance_analytics(performance, tmp_path / "results")
    assert Path(outputs["json"]).name == "strategy_performance_analytics.json"
    assert Path(outputs["markdown"]).name == "strategy_performance_analytics.md"
