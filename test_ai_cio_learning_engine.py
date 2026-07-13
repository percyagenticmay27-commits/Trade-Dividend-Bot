from pathlib import Path

import ai_cio_learning_engine as module


def mature_payload():
    return {
        "history_days": 220,
        "completed_decisions": [{"net_total_wealth_effect": 1.0}] * 520,
        "completed_replacements": [{"successful": True, "net_total_wealth_effect": 0.8}] * 104,
        "earnings_outcomes": [{"protection_value": 2.0}, {"protection_value": 1.0}],
        "evidence_source_outcomes": [
            {"source": "Market Intelligence", "uses": 100, "successful_outcomes": 70, "average_total_wealth_effect": 0.6},
            {"source": "Momentum", "uses": 100, "successful_outcomes": 60, "average_total_wealth_effect": 0.4},
        ],
        "threshold_trials": [
            {"current_rule": "Threshold 8.0", "candidate_rule": "Threshold 7.5", "current_total_wealth": 100.0, "candidate_total_wealth": 101.5}
        ],
        "observed_market_regimes": ["BULL", "BEAR", "SIDEWAYS"],
        "evidence_confidence": 94.0,
    }


def build(**overrides):
    payload = mature_payload()
    payload.update(overrides)
    return module.build_ai_cio_learning_engine(**payload)


def test_public_functions_exist():
    assert callable(module.build_ai_cio_learning_engine)
    assert callable(module.format_ai_cio_learning_engine_markdown)
    assert callable(module.format_ai_cio_learning_engine_html)
    assert callable(module.write_ai_cio_learning_engine)
    assert callable(module.build_and_write_ai_cio_learning_engine)


def test_paper_only_flags():
    report = build()
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["reporting_only"] is True


def test_learning_stage_with_insufficient_history():
    report = build(history_days=30, completed_decisions=[], completed_replacements=[], earnings_outcomes=[])
    assert report["maturity"]["stage"] == "LEARNING"
    assert report["maturity"]["policy_recommendations_allowed"] is False


def test_observation_stage_when_confidence_is_low():
    report = build(evidence_confidence=75.0)
    assert report["maturity"]["stage"] == "OBSERVATION"
    assert report["maturity"]["policy_recommendations_allowed"] is False


def test_recommendation_eligible_stage():
    report = build()
    assert report["maturity"]["stage"] == "RECOMMENDATION_ELIGIBLE"
    assert report["maturity"]["policy_recommendations_allowed"] is True


def test_replacement_metrics():
    report = build()
    metrics = report["learning_metrics"]
    assert metrics["replacement_success_rate"] == 100.0
    assert metrics["false_positive_replacement_rate"] == 0.0
    assert metrics["average_replacement_total_wealth_effect"] == 0.8


def test_false_positive_rate_detected():
    rows = [{"successful": True}] * 80 + [{"false_positive": True}] * 20
    report = build(completed_replacements=rows)
    assert report["learning_metrics"]["false_positive_replacement_rate"] == 20.0
    assert any("False-positive" in item["finding"] for item in report["learning_findings"])


def test_evidence_sources_ranked():
    analysis = build()["evidence_source_analysis"]
    assert analysis[0]["source"] == "Market Intelligence"
    assert analysis[0]["success_rate"] == 70.0


def test_shadow_trial_difference():
    trial = build()["shadow_trial_analysis"][0]
    assert trial["difference"] == 1.5
    assert trial["status"] == "SHADOW_ONLY"


def test_positive_shadow_trial_creates_review_recommendation():
    recommendation = build()["recommendations"][0]
    assert recommendation["status"] == "AWAITING_INVESTOR_APPROVAL"
    assert recommendation["automatic_change_allowed"] is False


def test_immature_history_recommends_no_change():
    report = build(history_days=10, completed_decisions=[], completed_replacements=[], earnings_outcomes=[])
    assert report["recommendations"][0]["status"] == "NO_CHANGE_RECOMMENDED"


def test_governance_is_locked():
    governance = build()["governance"]
    assert governance["automatic_policy_changes_allowed"] is False
    assert governance["investor_approval_required"] is True
    assert governance["shadow_validation_required"] is True
    assert governance["production_policy_modified"] is False


def test_empty_history_creates_warning_not_error():
    report = module.build_ai_cio_learning_engine()
    assert report["warnings"]
    assert report["errors"] == []
    assert report["maturity"]["stage"] == "LEARNING"


def test_nonfinite_values_are_sanitized():
    report = build(evidence_confidence=float("inf"), completed_decisions=[{"net_total_wealth_effect": float("nan")}])
    assert report["maturity"]["evidence_confidence"] == 0.0
    assert report["learning_metrics"]["average_decision_total_wealth_effect"] == 0.0


def test_markdown_contains_learning_sections():
    markdown = module.format_ai_cio_learning_engine_markdown(build())
    assert "Executive Learning Status" in markdown
    assert "Learning Metrics" in markdown
    assert "What the AI CIO Learned" in markdown
    assert "Recommendations" in markdown
    assert "Governance" in markdown


def test_html_contains_title():
    html = module.format_ai_cio_learning_engine_html(build())
    assert "<!doctype html>" in html.lower()
    assert "AI CIO Learning Engine" in html


def test_write_outputs(tmp_path):
    report = module.write_ai_cio_learning_engine(mature_payload(), root_path=str(tmp_path))
    assert report["module_name"] == module.MODULE_NAME
    assert (tmp_path / "ai_cio_learning_engine.json").exists()
    assert (tmp_path / "ai_cio_learning_engine.md").exists()
    assert (tmp_path / "ai_cio_learning_engine.html").exists()


def test_invalid_payload_rejected(tmp_path):
    try:
        module.write_ai_cio_learning_engine("invalid", root_path=str(tmp_path))
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_no_broker_or_order_execution_imports():
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = ["import robin_stocks", "import alpaca", "submit_order(", "place_order(", "broker.login"]
    assert not any(item in source for item in forbidden)
