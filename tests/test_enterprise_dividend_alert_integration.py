from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.dividend_bot.enterprise_dividend_alert_integration import (
    ADVISORY_ONLY,
    BROKER_EXECUTION_ENABLED,
    LIVE_TRADING_ENABLED,
    PAPER_TRADE_MODE,
    build_enterprise_dividend_alerts,
    render_enterprise_dividend_alerts_markdown,
    write_enterprise_dividend_alerts,
)

FIXED_TIME = "2026-07-25T12:00:00Z"


def _build(**kwargs):
    return build_enterprise_dividend_alerts(generated_at_utc=FIXED_TIME, **kwargs)


def test_safety_constants_are_locked():
    assert PAPER_TRADE_MODE is True
    assert LIVE_TRADING_ENABLED is False
    assert BROKER_EXECUTION_ENABLED is False
    assert ADVISORY_ONLY is True


def test_empty_inputs_return_warnings_not_failure():
    report = _build()
    assert report["summary"]["total_alerts"] == 0
    assert report["summary"]["warning_count"] == 2
    assert report["paper_trade_mode"] is True


@pytest.mark.parametrize(
    ("code", "expected_type", "severity"),
    [
        ("DIVIDEND_CUT", "DIVIDEND_CUT", "HIGH"),
        ("DIVIDEND_SUSPENSION", "DIVIDEND_SUSPENSION", "CRITICAL"),
        ("MISSED_DIVIDEND_PAYMENT", "MISSED_PAYMENT", "HIGH"),
        ("LOW_CONFIDENCE", "LOW_CONFIDENCE", "LOW"),
        ("NEGATIVE_INCOME_GROWTH", "NEGATIVE_INCOME_GROWTH", "MEDIUM"),
        ("REDUCED_PROJECTED_INCOME", "REDUCED_PROJECTED_INCOME", "MEDIUM"),
        ("EVIDENCE_GAP", "EVIDENCE_GAP", "LOW"),
        ("REVIEW_REQUIRED", "REVIEW_REQUIRED", "INFO"),
    ],
)
def test_supported_findings_generate_governed_alerts(code, expected_type, severity):
    report = _build(
        dividend_dashboard={
            "risk_flags": [{"symbol": "ABC", "code": code, "message": "Review finding"}]
        },
        investor_dashboard={},
    )
    alert = report["alerts"][0]
    assert alert["alert_type"] == expected_type
    assert alert["severity"] == severity
    assert alert["status"] == "OPEN"
    assert alert["symbol"] == "ABC"
    assert alert["paper_trade_mode"] is True
    assert alert["advisory_only"] is True


def test_unknown_findings_are_ignored():
    report = _build(
        dividend_dashboard={"risk_flags": [{"code": "UNKNOWN_THING"}]},
        investor_dashboard={},
    )
    assert report["alerts"] == []


def test_low_confidence_threshold_alert():
    report = _build(dividend_dashboard={"summary": {"confidence_score": 49}}, investor_dashboard={})
    assert any(item["alert_type"] == "LOW_CONFIDENCE" for item in report["alerts"])


def test_confidence_at_threshold_does_not_alert():
    report = _build(dividend_dashboard={"summary": {"confidence_score": 50}}, investor_dashboard={})
    assert not any(item["alert_type"] == "LOW_CONFIDENCE" for item in report["alerts"])


def test_negative_income_growth_threshold_alert():
    report = _build(dividend_dashboard={"summary": {"income_growth_percent": -1.25}}, investor_dashboard={})
    assert any(item["alert_type"] == "NEGATIVE_INCOME_GROWTH" for item in report["alerts"])


def test_reduced_projected_income_threshold_alert():
    report = _build(
        dividend_dashboard={"summary": {"projected_annual_income": 900, "prior_projected_annual_income": 1000}},
        investor_dashboard={},
    )
    alert = next(item for item in report["alerts"] if item["alert_type"] == "REDUCED_PROJECTED_INCOME")
    assert "100.00" in alert["message"]


def test_evidence_gap_threshold_alert():
    report = _build(
        dividend_dashboard={"summary": {"evidence_complete": False, "missing_evidence": ["declaration"]}},
        investor_dashboard={},
    )
    alert = next(item for item in report["alerts"] if item["alert_type"] == "EVIDENCE_GAP")
    assert alert["evidence_links"] == ["declaration"]


def test_duplicate_findings_create_one_alert():
    finding = {"symbol": "ABC", "code": "DIVIDEND_CUT"}
    report = _build(
        dividend_dashboard={"risk_flags": [finding, finding]},
        investor_dashboard={},
        reporting_period="2026-07",
    )
    assert report["summary"]["total_alerts"] == 1


def test_same_finding_in_different_periods_has_different_key():
    source = {"risk_flags": [{"symbol": "ABC", "code": "DIVIDEND_CUT"}]}
    first = _build(dividend_dashboard=source, investor_dashboard={}, reporting_period="2026-06")
    second = _build(dividend_dashboard=source, investor_dashboard={}, reporting_period="2026-07")
    assert first["alerts"][0]["deduplication_key"] != second["alerts"][0]["deduplication_key"]


def test_existing_active_alert_preserves_identity_and_status():
    source = {"risk_flags": [{"symbol": "ABC", "code": "DIVIDEND_CUT"}]}
    initial = _build(dividend_dashboard=source, investor_dashboard={}, reporting_period="2026-07")
    existing = dict(initial["alerts"][0])
    existing["status"] = "UNDER_REVIEW"
    existing["created_at_utc"] = "2026-07-24T12:00:00Z"
    updated = _build(
        dividend_dashboard=source,
        investor_dashboard={},
        existing_alerts=[existing],
        reporting_period="2026-07",
    )
    alert = updated["alerts"][0]
    assert alert["alert_id"] == existing["alert_id"]
    assert alert["status"] == "UNDER_REVIEW"
    assert alert["created_at_utc"] == "2026-07-24T12:00:00Z"


def test_summary_counts_match_alerts():
    report = _build(
        dividend_dashboard={
            "risk_flags": [
                {"symbol": "AAA", "code": "DIVIDEND_SUSPENSION"},
                {"symbol": "BBB", "code": "DIVIDEND_CUT"},
                {"symbol": "CCC", "code": "REVIEW_REQUIRED"},
            ]
        },
        investor_dashboard={},
    )
    assert report["summary"]["total_alerts"] == 3
    assert report["summary"]["critical"] == 1
    assert report["summary"]["high"] == 1
    assert report["summary"]["info"] == 1


def test_alerts_sorted_by_severity():
    report = _build(
        dividend_dashboard={
            "risk_flags": [
                {"symbol": "AAA", "code": "REVIEW_REQUIRED"},
                {"symbol": "BBB", "code": "DIVIDEND_SUSPENSION"},
                {"symbol": "CCC", "code": "DIVIDEND_CUT"},
            ]
        },
        investor_dashboard={},
    )
    assert [item["severity"] for item in report["alerts"]] == ["CRITICAL", "HIGH", "INFO"]


def test_additional_source_is_supported():
    report = _build(
        dividend_dashboard={},
        investor_dashboard={},
        additional_sources=[{
            "module_name": "income_forecast",
            "source_report": "income_forecast.json",
            "risk_flags": [{"symbol": "XYZ", "code": "REDUCED_PROJECTED_INCOME"}],
        }],
    )
    alert = report["alerts"][0]
    assert alert["source_module"] == "income_forecast"
    assert alert["source_report"] == "income_forecast.json"


def test_governance_prohibits_capital_movement_and_policy_changes():
    report = _build(dividend_dashboard={}, investor_dashboard={})
    assert report["governance"]["decision_authority"] == "NONE"
    assert report["governance"]["capital_movement_allowed"] is False
    assert report["governance"]["automatic_policy_changes_allowed"] is False


def test_markdown_contains_required_sections():
    report = _build(
        dividend_dashboard={"risk_flags": [{"symbol": "ABC", "code": "DIVIDEND_CUT"}]},
        investor_dashboard={},
    )
    markdown = render_enterprise_dividend_alerts_markdown(report)
    assert "# Enterprise Dividend Alerts" in markdown
    assert "## Alert Summary" in markdown
    assert "## Critical Alerts" in markdown
    assert "## Governance Notes" in markdown
    assert "DIVIDEND_CUT" in markdown


def test_write_outputs_json_and_markdown(tmp_path: Path):
    report = _build(dividend_dashboard={}, investor_dashboard={})
    paths = write_enterprise_dividend_alerts(report, tmp_path)
    json_path = Path(paths["json"])
    markdown_path = Path(paths["markdown"])
    assert json_path.exists()
    assert markdown_path.exists()
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded["module_name"] == "enterprise_dividend_alert_integration"
    assert "Enterprise Dividend Alerts" in markdown_path.read_text(encoding="utf-8")


def test_nonfinite_threshold_values_are_safe():
    report = _build(
        dividend_dashboard={
            "summary": {
                "confidence_score": float("nan"),
                "income_growth_percent": float("inf"),
                "projected_annual_income": float("nan"),
            }
        },
        investor_dashboard={},
    )
    json.dumps(report, allow_nan=False)


def test_alert_id_is_deterministic():
    source = {"risk_flags": [{"symbol": "ABC", "code": "DIVIDEND_CUT"}]}
    first = _build(dividend_dashboard=source, investor_dashboard={}, reporting_period="2026-07")
    second = _build(dividend_dashboard=source, investor_dashboard={}, reporting_period="2026-07")
    assert first["alerts"][0]["alert_id"] == second["alerts"][0]["alert_id"]


def test_output_metadata_is_complete():
    report = _build(dividend_dashboard={}, investor_dashboard={})
    assert report["module_name"] == "enterprise_dividend_alert_integration"
    assert report["module_version"] == "1.0.0"
    assert report["schema_version"] == "1.0"
    assert report["generated_at_utc"] == FIXED_TIME
    assert report["reporting_only"] is True
    assert report["advisory_only"] is True
