from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.dividend_bot.enterprise_dividend_cio_advisory_integration import (
    ADVISORY_ONLY,
    BROKER_EXECUTION_ENABLED,
    CAPITAL_MOVEMENT_ENABLED,
    HUMAN_APPROVAL_REQUIRED,
    LIVE_TRADING_ENABLED,
    PAPER_TRADE_MODE,
    POLICY_CHANGE_ENABLED,
    RECOMMENDATION_TYPES,
    build_and_write_enterprise_dividend_cio_advisory,
    build_enterprise_dividend_cio_advisory,
    render_enterprise_dividend_cio_advisory_markdown,
    write_enterprise_dividend_cio_advisory,
)


def _alert(symbol: str, alert_type: str, severity: str = "HIGH", status: str = "OPEN") -> dict:
    return {
        "alert_id": f"A-{symbol}-{alert_type}",
        "symbol": symbol,
        "alert_type": alert_type,
        "severity": severity,
        "status": status,
    }


def _review(symbol: str, status: str) -> dict:
    return {"review_id": f"R-{symbol}-{status}", "symbol": symbol, "status": status}


def _learning(symbol: str, learning_type: str) -> dict:
    return {
        "learning_record_id": f"L-{symbol}-{learning_type}",
        "symbol": symbol,
        "learning_type": learning_type,
    }


def test_safety_constants_are_locked() -> None:
    assert PAPER_TRADE_MODE is True
    assert ADVISORY_ONLY is True
    assert HUMAN_APPROVAL_REQUIRED is True
    assert LIVE_TRADING_ENABLED is False
    assert BROKER_EXECUTION_ENABLED is False
    assert POLICY_CHANGE_ENABLED is False
    assert CAPITAL_MOVEMENT_ENABLED is False


def test_supported_recommendations_are_locked() -> None:
    assert RECOMMENDATION_TYPES == {"HOLD", "REVIEW", "REDUCE", "EXIT_REVIEW", "REPLACEMENT_REVIEW"}


def test_empty_inputs_return_partial_report() -> None:
    report = build_enterprise_dividend_cio_advisory(generated_at_utc="2026-07-25T00:00:00Z")
    assert report["advisory_status"] == "PARTIAL"
    assert report["recommendations"] == []
    assert report["summary"]["recommendation_count"] == 0
    assert len(report["warnings"]) == 6


def test_portfolio_input_without_symbol_creates_portfolio_hold() -> None:
    report = build_enterprise_dividend_cio_advisory(
        analytics_report={"summary": {"income_growth_percent": 5, "forecast_accuracy_percent": 95, "confidence_score": 90}},
        generated_at_utc="2026-07-25T00:00:00Z",
    )
    item = report["recommendations"][0]
    assert item["symbol"] == "PORTFOLIO"
    assert item["recommendation"] == "HOLD"


def test_suspension_generates_exit_review() -> None:
    report = build_enterprise_dividend_cio_advisory(
        alert_report={"alerts": [_alert("ABC", "DIVIDEND_SUSPENSION", "CRITICAL")]},
        generated_at_utc="2026-07-25T00:00:00Z",
    )
    item = report["recommendations"][0]
    assert item["recommendation"] == "EXIT_REVIEW"
    assert item["priority"] == "CRITICAL"


def test_escalated_missed_payment_generates_exit_review() -> None:
    report = build_enterprise_dividend_cio_advisory(
        alert_report={"alerts": [_alert("ABC", "MISSED_PAYMENT", "HIGH")]},
        review_report={"reviews": [_review("ABC", "ESCALATED")]},
    )
    assert report["recommendations"][0]["recommendation"] == "EXIT_REVIEW"


def test_dividend_cut_and_negative_growth_generates_replacement_review() -> None:
    report = build_enterprise_dividend_cio_advisory(
        analytics_report={"summary": {"income_growth_percent": -2, "forecast_accuracy_percent": 90, "confidence_score": 80}},
        alert_report={"alerts": [_alert("ABC", "DIVIDEND_CUT", "HIGH")]},
    )
    assert report["recommendations"][0]["recommendation"] == "REPLACEMENT_REVIEW"


def test_dividend_cut_and_low_confidence_generates_replacement_review() -> None:
    report = build_enterprise_dividend_cio_advisory(
        analytics_report={"summary": {"income_growth_percent": 1, "forecast_accuracy_percent": 90, "confidence_score": 40}},
        alert_report={"alerts": [_alert("ABC", "DIVIDEND_CUT", "HIGH")]},
    )
    assert report["recommendations"][0]["recommendation"] == "REPLACEMENT_REVIEW"


def test_combined_high_signals_generate_reduce() -> None:
    report = build_enterprise_dividend_cio_advisory(
        alert_report={"alerts": [_alert("ABC", "LOW_CONFIDENCE", "HIGH")]},
        review_report={"reviews": [_review("ABC", "ESCALATED")]},
        analytics_report={"summary": {"income_growth_percent": 2, "forecast_accuracy_percent": 90, "confidence_score": 80}},
    )
    assert report["recommendations"][0]["recommendation"] == "REDUCE"


def test_negative_growth_alone_generates_review() -> None:
    report = build_enterprise_dividend_cio_advisory(
        analytics_report={"summary": {"income_growth_percent": -0.1, "forecast_accuracy_percent": 100, "confidence_score": 100}},
    )
    assert report["recommendations"][0]["recommendation"] == "REVIEW"


def test_low_forecast_accuracy_generates_review() -> None:
    report = build_enterprise_dividend_cio_advisory(
        forecast_report={"summary": {"forecast_accuracy_percent": 69}},
    )
    assert report["recommendations"][0]["recommendation"] == "REVIEW"


def test_low_confidence_generates_review() -> None:
    report = build_enterprise_dividend_cio_advisory(
        analytics_report={"summary": {"confidence_score": 59}},
    )
    assert report["recommendations"][0]["recommendation"] == "REVIEW"


def test_learning_signal_generates_review() -> None:
    report = build_enterprise_dividend_cio_advisory(
        learning_report={"learning_records": [_learning("ABC", "FORECAST_BIAS"), _learning("ABC", "POLICY_REVIEW")]},
    )
    assert report["recommendations"][0]["recommendation"] == "REVIEW"
    assert report["recommendations"][0]["learning_score"] == 4


def test_resolved_alert_is_ignored() -> None:
    report = build_enterprise_dividend_cio_advisory(
        alert_report={"alerts": [_alert("ABC", "DIVIDEND_SUSPENSION", "CRITICAL", "RESOLVED")]},
    )
    assert report["recommendations"][0]["recommendation"] == "HOLD"
    assert report["recommendations"][0]["alert_score"] == 0


def test_deferred_alert_is_ignored() -> None:
    report = build_enterprise_dividend_cio_advisory(
        alert_report={"alerts": [_alert("ABC", "DIVIDEND_CUT", "HIGH", "DEFERRED")]},
    )
    assert report["recommendations"][0]["recommendation"] == "HOLD"


def test_multiple_symbols_receive_separate_recommendations() -> None:
    report = build_enterprise_dividend_cio_advisory(
        alert_report={"alerts": [_alert("AAA", "DIVIDEND_SUSPENSION", "CRITICAL"), _alert("BBB", "LOW_CONFIDENCE", "LOW")]},
    )
    assert {item["symbol"] for item in report["recommendations"]} == {"AAA", "BBB"}


def test_recommendations_sort_by_governed_priority() -> None:
    report = build_enterprise_dividend_cio_advisory(
        alert_report={"alerts": [_alert("AAA", "LOW_CONFIDENCE", "LOW"), _alert("BBB", "DIVIDEND_SUSPENSION", "CRITICAL")]},
    )
    assert report["recommendations"][0]["symbol"] == "BBB"
    assert report["recommendations"][0]["recommendation"] == "EXIT_REVIEW"


def test_recommendation_id_is_deterministic() -> None:
    kwargs = {
        "alert_report": {"alerts": [_alert("ABC", "DIVIDEND_CUT", "HIGH")]},
        "analytics_report": {"summary": {"income_growth_percent": -1}},
        "reporting_period": "2026-Q3",
        "generated_at_utc": "2026-07-25T00:00:00Z",
    }
    first = build_enterprise_dividend_cio_advisory(**kwargs)
    second = build_enterprise_dividend_cio_advisory(**kwargs)
    assert first["recommendations"][0]["recommendation_id"] == second["recommendations"][0]["recommendation_id"]


def test_recommendation_id_changes_with_period() -> None:
    first = build_enterprise_dividend_cio_advisory(
        alert_report={"alerts": [_alert("ABC", "DIVIDEND_SUSPENSION", "CRITICAL")]},
        reporting_period="2026-Q2",
    )
    second = build_enterprise_dividend_cio_advisory(
        alert_report={"alerts": [_alert("ABC", "DIVIDEND_SUSPENSION", "CRITICAL")]},
        reporting_period="2026-Q3",
    )
    assert first["recommendations"][0]["recommendation_id"] != second["recommendations"][0]["recommendation_id"]


def test_evidence_links_are_preserved() -> None:
    report = build_enterprise_dividend_cio_advisory(
        alert_report={"alerts": [_alert("ABC", "LOW_CONFIDENCE", "LOW")]},
        review_report={"reviews": [_review("ABC", "OPEN")]},
        learning_report={"learning_records": [_learning("ABC", "FALSE_ALERT")]},
    )
    item = report["recommendations"][0]
    assert item["originating_alert_ids"] == ["A-ABC-LOW_CONFIDENCE"]
    assert item["originating_review_ids"] == ["R-ABC-OPEN"]
    assert item["originating_learning_record_ids"] == ["L-ABC-FALSE_ALERT"]


def test_every_recommendation_requires_investor_approval() -> None:
    report = build_enterprise_dividend_cio_advisory(analytics_report={"summary": {}})
    item = report["recommendations"][0]
    assert item["status"] == "PENDING_INVESTOR_APPROVAL"
    assert item["human_approval_required"] is True
    assert item["capital_movement_authorized"] is False


def test_summary_counts_match_recommendations() -> None:
    report = build_enterprise_dividend_cio_advisory(
        alert_report={"alerts": [_alert("AAA", "DIVIDEND_SUSPENSION", "CRITICAL"), _alert("BBB", "DIVIDEND_CUT", "HIGH")]},
        analytics_report={"summary": {"income_growth_percent": -1}},
    )
    summary = report["summary"]
    assert summary["recommendation_count"] == 2
    assert sum(summary[name.lower()] for name in RECOMMENDATION_TYPES) == 2


def test_nonfinite_values_are_normalized() -> None:
    report = build_enterprise_dividend_cio_advisory(
        analytics_report={"summary": {"income_growth_percent": float("nan"), "confidence_score": float("inf")}},
        forecast_report={"summary": {"forecast_accuracy_percent": float("nan")}},
    )
    item = report["recommendations"][0]
    assert item["income_growth_percent"] == 0.0
    assert item["forecast_accuracy_percent"] == 100.0
    assert item["confidence_score"] == 100.0


def test_markdown_contains_governance_and_recommendation() -> None:
    report = build_enterprise_dividend_cio_advisory(
        alert_report={"alerts": [_alert("ABC", "DIVIDEND_SUSPENSION", "CRITICAL")]},
        generated_at_utc="2026-07-25T00:00:00Z",
    )
    markdown = render_enterprise_dividend_cio_advisory_markdown(report)
    assert "# Enterprise Dividend CIO Advisory" in markdown
    assert "ABC — EXIT_REVIEW" in markdown
    assert "Human approval required: True" in markdown
    assert "No orders, capital movement, or automatic policy changes" in markdown


def test_write_outputs_json_and_markdown(tmp_path: Path) -> None:
    report = build_enterprise_dividend_cio_advisory(analytics_report={"summary": {}})
    paths = write_enterprise_dividend_cio_advisory(report, tmp_path)
    assert Path(paths["json"]).exists()
    assert Path(paths["markdown"]).exists()
    loaded = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert loaded["module_name"] == "enterprise_dividend_cio_advisory_integration"


def test_build_and_write_returns_report_and_paths(tmp_path: Path) -> None:
    result = build_and_write_enterprise_dividend_cio_advisory(
        output_dir=tmp_path,
        analytics_report={"summary": {}},
    )
    assert "report" in result
    assert "output_files" in result
    assert Path(result["output_files"]["json"]).exists()


def test_output_metadata_is_complete() -> None:
    report = build_enterprise_dividend_cio_advisory(analytics_report={"summary": {}})
    assert report["module_name"] == "enterprise_dividend_cio_advisory_integration"
    assert report["module_version"] == "1.0.0"
    assert report["schema_version"] == "1.0"
    assert report["paper_trade_mode"] is True
    assert report["advisory_only"] is True
    assert report["human_approval_required"] is True
    assert report["policy_change_enabled"] is False
    assert report["capital_movement_enabled"] is False


def test_governance_block_denies_execution_authority() -> None:
    report = build_enterprise_dividend_cio_advisory(analytics_report={"summary": {}})
    governance = report["governance"]
    assert governance["decision_authority"] == "INVESTOR"
    assert governance["recommendations_are_non_executing"] is True
    assert governance["automatic_policy_changes_prohibited"] is True
    assert governance["automatic_capital_movement_prohibited"] is True
