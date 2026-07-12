import json
from pathlib import Path

import pytest

import ai_cio_executive_dashboard as module


def sample_payload():
    return {
        "portfolio_summary": {
            "portfolio_value": 1000,
            "capital_appreciation": 125,
            "projected_annual_income": 80,
            "market_regime": "BULL",
            "portfolio_health": "GOOD",
        },
        "allocations": [
            {
                "strategy": "AMDW + PLTU",
                "allocation_percent": 50,
                "capital_efficiency_score": 84.3,
                "decision_stability_score": 82.7,
                "evidence_confidence_score": 94,
                "status": "STRONG",
                "ai_cio_verdict": "Continue Holding",
            },
            {
                "strategy": "QQQI + TQQQ",
                "allocation_percent": 30,
                "capital_efficiency_score": 78,
                "decision_stability_score": 75,
                "evidence_confidence_score": 90,
                "status": "STABLE",
                "ai_cio_verdict": "Monitor",
            },
            {
                "strategy": "SGOV",
                "allocation_percent": 20,
                "capital_efficiency_score": 50,
                "status": "RESERVE",
                "ai_cio_verdict": "Reserve",
            },
        ],
        "ai_cio_decision": {
            "final_capital_action": "KEEP",
            "current_candidate_id": "AMDW + PLTU",
            "challenger_candidate_id": "AMDW + GGLL",
            "ai_cio_verdict": "Continue holding AMDW + PLTU.",
            "decision_stability_score": 82.7,
            "decision_stability_label": "STABLE",
            "evidence_confidence_score": 94,
            "evidence_confidence_label": "VERY_HIGH",
            "market_regime": "BULL",
            "autonomy_level": "LEVEL_1_ADVISOR",
        },
        "sgov_notifications": [
            {
                "source_strategy": "PLTU",
                "allocation_percent": 10,
                "reason": "Earnings protection",
                "status": "Parked",
                "next_review": "After earnings",
            }
        ],
        "analysis_confidence": {"summary": "Analysis confidence is very high."},
        "decision_history": [{"date": "2026-07-12", "summary": "Held current allocation."}],
        "upcoming_events": [{"event": "PLTR Earnings", "when": "In 4 days"}],
        "watchlist": [{"symbol": "AMDW + GGLL", "status": "Challenger", "reason": "Improving score"}],
    }


def test_public_functions_exist():
    assert callable(module.rank_allocations)
    assert callable(module.build_ai_cio_executive_dashboard)
    assert callable(module.format_dashboard_markdown)
    assert callable(module.format_dashboard_html)
    assert callable(module.write_ai_cio_executive_dashboard)


def test_paper_only_constants():
    assert module.PAPER_TRADE_MODE is True
    assert module.LIVE_TRADING_ENABLED is False
    assert module.BROKER_EXECUTION_ENABLED is False
    assert module.REPORTING_ONLY is True


def test_rank_allocations_orders_strong_to_weak_and_sgov_last():
    ranked = module.rank_allocations(sample_payload()["allocations"])
    assert ranked[0]["strategy"] == "AMDW + PLTU"
    assert ranked[-1]["strategy"] == "SGOV"
    assert [item["rank"] for item in ranked] == [1, 2, 3]


def test_dashboard_summary_values():
    report = module.build_ai_cio_executive_dashboard(**sample_payload())
    summary = report["portfolio_summary"]
    assert summary["portfolio_value"] == 1000
    assert summary["capital_appreciation"] == 125
    assert summary["projected_annual_income"] == 80
    assert summary["sgov_reserve_percent"] == 20
    assert summary["active_allocation_count"] == 2


def test_dashboard_contains_required_sections():
    report = module.build_ai_cio_executive_dashboard(**sample_payload())
    assert "capital_allocation_rankings" in report
    assert "ai_cio_verdict" in report
    assert "sgov_notifications" in report
    assert "analysis_confidence" in report
    assert "decision_history" in report
    assert "upcoming_events" in report
    assert "watchlist" in report


def test_markdown_uses_full_investor_facing_names():
    report = module.build_ai_cio_executive_dashboard(**sample_payload())
    markdown = module.format_dashboard_markdown(report)
    assert "Capital Allocation Rankings" in markdown
    assert "AI CIO Verdict" in markdown
    assert "SGOV Notifications" in markdown
    assert "Analysis Confidence" in markdown
    assert "Decision Stability" in json.dumps(report)
    assert "Capital Efficiency" not in markdown or "Capital Efficiency Score" in markdown


def test_markdown_lists_ranked_allocations():
    report = module.build_ai_cio_executive_dashboard(**sample_payload())
    markdown = module.format_dashboard_markdown(report)
    assert "AMDW + PLTU" in markdown
    assert "QQQI + TQQQ" in markdown
    assert "SGOV" in markdown


def test_sgov_notification_is_explained():
    report = module.build_ai_cio_executive_dashboard(**sample_payload())
    markdown = module.format_dashboard_markdown(report)
    assert "PLTU" in markdown
    assert "Earnings protection" in markdown
    assert "After earnings" in markdown


def test_missing_optional_inputs_create_warnings_not_errors():
    report = module.build_ai_cio_executive_dashboard()
    assert report["warnings"]
    assert report["errors"] == []
    assert report["paper_trade_mode"] is True


def test_html_output_is_standalone():
    report = module.build_ai_cio_executive_dashboard(**sample_payload())
    output = module.format_dashboard_html(report)
    assert "<!doctype html>" in output.lower()
    assert "AI CIO Executive Dashboard" in output
    assert "Paper-only portfolio intelligence" in output


def test_write_outputs(tmp_path: Path):
    report = module.write_ai_cio_executive_dashboard(sample_payload(), root_path=str(tmp_path))
    assert report["module_name"] == module.MODULE_NAME
    for name in module.DEFAULT_OUTPUT_FILES.values():
        assert (tmp_path / name).exists()
    loaded = json.loads((tmp_path / module.DEFAULT_OUTPUT_FILES["json"]).read_text(encoding="utf-8"))
    assert loaded["paper_trade_mode"] is True


def test_invalid_payload_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        module.write_ai_cio_executive_dashboard([], root_path=str(tmp_path))


def test_source_has_no_restricted_execution_calls():
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = ["subprocess", "os.system(", "place_order(", "submit_order(", "robin_stocks"]
    assert not any(term in source for term in forbidden)
