from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.dividend_bot import enterprise_dividend_replacement_integration as mod


def holding(**overrides):
    row = {
        "symbol": "OLD",
        "projected_annual_income": 100.0,
        "yield_percent": 4.0,
        "confidence_score": 45.0,
        "quality_score": 45.0,
        "risk_score": 70.0,
        "income_growth_percent": -5.0,
    }
    row.update(overrides)
    return row


def candidate(**overrides):
    row = {
        "symbol": "NEW",
        "projected_annual_income": 130.0,
        "yield_percent": 5.0,
        "confidence_score": 90.0,
        "quality_score": 90.0,
        "risk_score": 20.0,
        "income_growth_percent": 8.0,
    }
    row.update(overrides)
    return row


def test_safety_constants_are_locked():
    assert mod.PAPER_TRADE_MODE is True
    assert mod.LIVE_TRADING_ENABLED is False
    assert mod.BROKER_EXECUTION_ENABLED is False
    assert mod.ADVISORY_ONLY is True
    assert mod.HUMAN_APPROVAL_REQUIRED is True


def test_supported_recommendations_are_limited():
    assert mod.RECOMMENDATION_TYPES == {"HOLD", "REVIEW", "REPLACEMENT_REVIEW"}


def test_empty_inputs_return_partial_and_warnings():
    report = mod.build_enterprise_dividend_replacement_analysis(generated_at_utc="2026-01-01T00:00:00Z")
    assert report["status"] == "PARTIAL"
    assert report["summary"]["comparison_count"] == 0
    assert len(report["warnings"]) == 2


def test_strong_candidate_replaces_weak_holding_for_review():
    report = mod.build_enterprise_dividend_replacement_analysis(
        governed_holdings=[holding()],
        replacement_candidates=[candidate()],
        alerts=[{"alert_id": "A1", "symbol": "OLD", "alert_type": "DIVIDEND_CUT"}],
        cio_recommendations=[{"symbol": "OLD", "recommendation": "REPLACEMENT_REVIEW"}],
        generated_at_utc="2026-01-01T00:00:00Z",
    )
    row = report["comparisons"][0]
    assert row["recommendation"] == "REPLACEMENT_REVIEW"
    assert row["candidate_symbol"] == "NEW"
    assert row["approval_status"] == "PENDING_INVESTOR_APPROVAL"


def test_hold_when_current_holding_has_no_weakness():
    report = mod.build_enterprise_dividend_replacement_analysis(
        governed_holdings=[holding(confidence_score=90, income_growth_percent=5, risk_score=20)],
        replacement_candidates=[candidate()],
        generated_at_utc="2026-01-01T00:00:00Z",
    )
    assert report["comparisons"][0]["recommendation"] == "HOLD"


def test_review_when_weakness_exists_but_candidate_not_superior():
    report = mod.build_enterprise_dividend_replacement_analysis(
        governed_holdings=[holding(confidence_score=40, income_growth_percent=1)],
        replacement_candidates=[candidate(quality_score=10, confidence_score=10, risk_score=90, income_growth_percent=-10)],
        generated_at_utc="2026-01-01T00:00:00Z",
    )
    assert report["comparisons"][0]["recommendation"] == "REVIEW"


def test_suspension_creates_high_weakness():
    report = mod.build_enterprise_dividend_replacement_analysis(
        governed_holdings=[holding(confidence_score=90, income_growth_percent=5)],
        replacement_candidates=[candidate()],
        alerts=[{"symbol": "OLD", "alert_type": "DIVIDEND_SUSPENSION"}],
        generated_at_utc="2026-01-01T00:00:00Z",
    )
    assert report["comparisons"][0]["weakness_score"] >= 100


def test_missed_payment_and_cut_are_cumulative():
    report = mod.build_enterprise_dividend_replacement_analysis(
        governed_holdings=[holding(confidence_score=90, income_growth_percent=5)],
        replacement_candidates=[candidate()],
        alerts=[
            {"symbol": "OLD", "alert_type": "MISSED_PAYMENT"},
            {"symbol": "OLD", "alert_type": "DIVIDEND_CUT"},
        ],
        generated_at_utc="2026-01-01T00:00:00Z",
    )
    assert report["comparisons"][0]["weakness_score"] == 100.0


def test_traceability_preserves_alert_and_review_ids():
    report = mod.build_enterprise_dividend_replacement_analysis(
        governed_holdings=[holding()],
        replacement_candidates=[candidate()],
        alerts=[{"alert_id": "A1", "symbol": "OLD", "alert_type": "DIVIDEND_CUT"}],
        reviews=[{"review_id": "R1", "symbol": "OLD"}],
        generated_at_utc="2026-01-01T00:00:00Z",
    )
    row = report["comparisons"][0]
    assert row["source_alert_ids"] == ["A1"]
    assert row["source_review_ids"] == ["R1"]


def test_deterministic_comparison_id():
    kwargs = dict(
        governed_holdings=[holding()],
        replacement_candidates=[candidate()],
        reporting_period="2026-Q3",
        generated_at_utc="2026-01-01T00:00:00Z",
    )
    first = mod.build_enterprise_dividend_replacement_analysis(**kwargs)
    second = mod.build_enterprise_dividend_replacement_analysis(**kwargs)
    assert first["comparisons"][0]["comparison_id"] == second["comparisons"][0]["comparison_id"]


def test_candidate_cannot_match_current_symbol():
    report = mod.build_enterprise_dividend_replacement_analysis(
        governed_holdings=[holding(symbol="SAME")],
        replacement_candidates=[candidate(symbol="SAME")],
        generated_at_utc="2026-01-01T00:00:00Z",
    )
    assert report["comparisons"][0]["candidate_symbol"] is None


def test_best_candidate_is_selected():
    report = mod.build_enterprise_dividend_replacement_analysis(
        governed_holdings=[holding()],
        replacement_candidates=[candidate(symbol="LOW", quality_score=40), candidate(symbol="HIGH", quality_score=95)],
        generated_at_utc="2026-01-01T00:00:00Z",
    )
    assert report["comparisons"][0]["candidate_symbol"] == "HIGH"


def test_boolean_values_do_not_become_numbers():
    row = mod._normalized_holding({"symbol": "X", "quality_score": True})
    assert row["quality_score"] == 0.0


def test_nonfinite_values_are_normalized():
    row = mod._normalized_holding({"symbol": "X", "quality_score": float("inf")})
    assert row["quality_score"] == 0.0


def test_summary_counts_match_comparisons():
    report = mod.build_enterprise_dividend_replacement_analysis(
        governed_holdings=[holding(symbol="A"), holding(symbol="B", confidence_score=90, income_growth_percent=5)],
        replacement_candidates=[candidate(symbol="C")],
        generated_at_utc="2026-01-01T00:00:00Z",
    )
    summary = report["summary"]
    assert summary["comparison_count"] == 2
    assert summary["hold"] + summary["review"] + summary["replacement_review"] == 2


def test_comparisons_are_priority_sorted():
    report = mod.build_enterprise_dividend_replacement_analysis(
        governed_holdings=[holding(symbol="GOOD", confidence_score=90, income_growth_percent=5), holding(symbol="BAD")],
        replacement_candidates=[candidate(symbol="NEW")],
        alerts=[{"symbol": "BAD", "alert_type": "DIVIDEND_CUT"}],
        generated_at_utc="2026-01-01T00:00:00Z",
    )
    assert report["comparisons"][0]["current_symbol"] == "BAD"


def test_markdown_contains_governance_boundary():
    report = mod.build_enterprise_dividend_replacement_analysis(
        governed_holdings=[holding()], replacement_candidates=[candidate()], generated_at_utc="2026-01-01T00:00:00Z"
    )
    markdown = mod.render_enterprise_dividend_replacement_markdown(report)
    assert "No sale, purchase, allocation change, or capital movement" in markdown
    assert "PENDING_INVESTOR_APPROVAL" in markdown


def test_write_outputs_creates_json_and_markdown(tmp_path: Path):
    report = mod.build_enterprise_dividend_replacement_analysis(
        governed_holdings=[holding()], replacement_candidates=[candidate()], generated_at_utc="2026-01-01T00:00:00Z"
    )
    paths = mod.write_enterprise_dividend_replacement_outputs(report, tmp_path)
    assert Path(paths["json"]).exists()
    assert Path(paths["markdown"]).exists()
    loaded = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert loaded["module_name"] == mod.MODULE_NAME


def test_build_and_write_includes_output_files(tmp_path: Path):
    report = mod.build_and_write_enterprise_dividend_replacement_analysis(
        tmp_path,
        governed_holdings=[holding()],
        replacement_candidates=[candidate()],
        generated_at_utc="2026-01-01T00:00:00Z",
    )
    assert set(report["output_files"]) == {"json", "markdown"}


def test_metadata_is_complete():
    report = mod.build_enterprise_dividend_replacement_analysis(generated_at_utc="2026-01-01T00:00:00Z")
    assert report["module_name"] == mod.MODULE_NAME
    assert report["module_version"] == "1.0.0"
    assert report["schema_version"] == "1.0"
    assert report["paper_trade_mode"] is True
    assert report["advisory_only"] is True
    assert report["human_approval_required"] is True


def test_output_file_names_are_stable():
    assert mod.DEFAULT_OUTPUT_FILES["json"] == "enterprise_dividend_replacement_analysis.json"
    assert mod.DEFAULT_OUTPUT_FILES["markdown"] == "enterprise_dividend_replacement_analysis.md"


def test_invalid_rows_are_ignored():
    report = mod.build_enterprise_dividend_replacement_analysis(
        governed_holdings=[None, "bad", holding()],
        replacement_candidates=[42, candidate()],
        generated_at_utc="2026-01-01T00:00:00Z",
    )
    assert report["summary"]["holding_count"] == 1
    assert report["summary"]["candidate_count"] == 1


def test_no_execution_authority_in_report():
    report = mod.build_enterprise_dividend_replacement_analysis(
        governed_holdings=[holding()], replacement_candidates=[candidate()], generated_at_utc="2026-01-01T00:00:00Z"
    )
    text = json.dumps(report).lower()
    assert '"broker_execution_enabled": false' in text
    assert '"live_trading_enabled": false' in text


def test_candidate_score_is_bounded():
    assert 0 <= mod._candidate_score(candidate(quality_score=999, confidence_score=999, yield_percent=999)) <= 100
    assert 0 <= mod._candidate_score(candidate(quality_score=-999, confidence_score=-999, yield_percent=-999)) <= 100


def test_symbol_normalization_is_uppercase():
    report = mod.build_enterprise_dividend_replacement_analysis(
        governed_holdings=[holding(symbol="old")], replacement_candidates=[candidate(symbol="new")], generated_at_utc="2026-01-01T00:00:00Z"
    )
    assert report["comparisons"][0]["current_symbol"] == "OLD"
    assert report["comparisons"][0]["candidate_symbol"] == "NEW"


def test_reporting_period_changes_comparison_identity():
    first = mod.build_enterprise_dividend_replacement_analysis(
        governed_holdings=[holding()], replacement_candidates=[candidate()], reporting_period="P1", generated_at_utc="2026-01-01T00:00:00Z"
    )
    second = mod.build_enterprise_dividend_replacement_analysis(
        governed_holdings=[holding()], replacement_candidates=[candidate()], reporting_period="P2", generated_at_utc="2026-01-01T00:00:00Z"
    )
    assert first["comparisons"][0]["comparison_id"] != second["comparisons"][0]["comparison_id"]
