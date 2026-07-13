from pathlib import Path

import ai_cio_missed_opportunity_review as module


def workflow_deficiency_record():
    return {
        "symbol": "AMDW + PLTU",
        "underlying_stock": "PLTR",
        "sector": "Technology",
        "subsequent_return_percent": 38.0,
        "selected_return_percent": 12.0,
        "eligible_capital": 10000,
        "qualified_after_block": True,
        "later_opportunity_score": 95,
        "selected_opportunity_score": 86,
        "decision_path": [
            {"stage": "DISCOVERY", "status": "PASS", "score": 84, "reason": "Discovered."},
            {"stage": "WATCHLIST", "status": "PASS", "score": 86, "reason": "Promoted."},
            {"stage": "RANKING", "status": "PASS", "score": 91, "reason": "Rank improved."},
            {"stage": "EARNINGS_REVIEW", "status": "BLOCKED", "reason": "PLTR earnings event."},
            {"stage": "REQUALIFICATION", "status": "MISSING", "reason": "Not performed."},
        ],
    }


def justified_record():
    return {
        "symbol": "XYZI",
        "underlying_stock": "XYZ",
        "subsequent_return_percent": 25.0,
        "selected_return_percent": 10.0,
        "eligible_capital": 5000,
        "decision_path": [
            {"stage": "DISCOVERY", "status": "PASS", "score": 70, "reason": "Discovered."},
            {"stage": "DECISION_STABILITY", "status": "FAIL", "score": 55, "reason": "Evidence confidence was below threshold."},
        ],
    }


def test_public_functions_exist():
    assert callable(module.build_ai_cio_missed_opportunity_review)
    assert callable(module.format_ai_cio_missed_opportunity_review_markdown)
    assert callable(module.format_ai_cio_missed_opportunity_review_html)
    assert callable(module.write_ai_cio_missed_opportunity_review)
    assert callable(module.build_and_write_ai_cio_missed_opportunity_review)


def test_paper_only_flags():
    report = module.build_ai_cio_missed_opportunity_review(opportunities=[])
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["reporting_only"] is True


def test_earnings_requalification_gap_is_workflow_deficiency():
    report = module.build_ai_cio_missed_opportunity_review(opportunities=[workflow_deficiency_record()])
    review = report["reviews"][0]
    assert review["classification"] == "WORKFLOW_DEFICIENCY"
    assert review["first_exit_stage"] == "EARNINGS_REVIEW"
    assert "post-earnings requalification" in review["findings"][0].lower()


def test_later_qualified_candidate_without_replacement_review_is_deficiency():
    record = workflow_deficiency_record()
    record["decision_path"] = [
        {"stage": "DISCOVERY", "status": "PASS", "reason": "Discovered."},
        {"stage": "WATCHLIST", "status": "PASS", "reason": "Promoted."},
        {"stage": "REQUALIFICATION", "status": "PASS", "reason": "Qualified again."},
    ]
    report = module.build_ai_cio_missed_opportunity_review(opportunities=[record])
    assert report["reviews"][0]["classification"] == "WORKFLOW_DEFICIENCY"
    assert "replacement review" in report["reviews"][0]["findings"][0].lower()


def test_documented_failed_gate_can_be_justified_rejection():
    report = module.build_ai_cio_missed_opportunity_review(opportunities=[justified_record()])
    review = report["reviews"][0]
    assert review["classification"] == "JUSTIFIED_REJECTION"
    assert review["first_exit_stage"] == "DECISION_STABILITY"


def test_small_relative_advantage_is_not_significant():
    record = justified_record()
    record["subsequent_return_percent"] = 22.0
    record["selected_return_percent"] = 19.0
    report = module.build_ai_cio_missed_opportunity_review(opportunities=[record])
    assert report["significant_missed_opportunity_count"] == 0
    assert report["reviews"][0]["classification"] == "NOT_SIGNIFICANT"


def test_meaningful_threshold_is_configurable():
    record = justified_record()
    record["subsequent_return_percent"] = 12.0
    record["selected_return_percent"] = 2.0
    report = module.build_ai_cio_missed_opportunity_review(
        opportunities=[record], meaningful_return_threshold_percent=10.0
    )
    assert report["significant_missed_opportunity_count"] == 1


def test_potential_wealth_missed_calculation():
    report = module.build_ai_cio_missed_opportunity_review(opportunities=[workflow_deficiency_record()])
    assert report["reviews"][0]["potential_wealth_missed"] == 2600.0
    assert report["estimated_total_potential_wealth_missed"] == 2600.0


def test_exit_stage_summary_counts_significant_records():
    report = module.build_ai_cio_missed_opportunity_review(
        opportunities=[workflow_deficiency_record(), justified_record()]
    )
    assert report["exit_stage_summary"]["EARNINGS_REVIEW"] == 1
    assert report["exit_stage_summary"]["DECISION_STABILITY"] == 1


def test_improvement_recommendation_created_for_earnings_gap():
    report = module.build_ai_cio_missed_opportunity_review(opportunities=[workflow_deficiency_record()])
    recommendation = report["improvement_recommendations"][0]
    assert "post-earnings" in recommendation["title"].lower()
    assert recommendation["status"] == "AWAITING_INVESTOR_REVIEW"


def test_historical_outperformance_does_not_auto_prove_error():
    governance = module.build_ai_cio_missed_opportunity_review(opportunities=[])["governance"]
    assert governance["historical_outperformance_alone_proves_error"] is False
    assert governance["automatic_policy_changes_allowed"] is False
    assert governance["automatic_workflow_changes_allowed"] is False
    assert governance["investor_approval_required"] is True


def test_pipeline_order_is_preserved():
    report = module.build_ai_cio_missed_opportunity_review(opportunities=[workflow_deficiency_record()])
    stages = [row["stage"] for row in report["reviews"][0]["decision_path"]]
    assert stages == ["DISCOVERY", "WATCHLIST", "RANKING", "EARNINGS_REVIEW", "REQUALIFICATION"]


def test_non_mapping_records_create_warning():
    report = module.build_ai_cio_missed_opportunity_review(opportunities=["bad record"])
    assert report["opportunities_reviewed"] == 0
    assert report["warnings"]
    assert report["errors"] == []


def test_invalid_opportunities_rejected():
    try:
        module.build_ai_cio_missed_opportunity_review(opportunities="invalid")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_nonfinite_values_are_sanitized():
    record = workflow_deficiency_record()
    record["subsequent_return_percent"] = float("inf")
    record["eligible_capital"] = float("nan")
    report = module.build_ai_cio_missed_opportunity_review(opportunities=[record])
    review = report["reviews"][0]
    assert review["subsequent_return_percent"] == 0.0
    assert review["eligible_capital"] == 0.0
    assert review["potential_wealth_missed"] == 0.0


def test_every_metric_has_reference_details():
    report = module.build_ai_cio_missed_opportunity_review(opportunities=[])
    for key in (
        "significant_missed_opportunity",
        "decision_path",
        "workflow_deficiency",
        "justified_rejection",
        "potential_wealth_missed",
    ):
        assert key in report["details"]
        assert report["details"][key]["definition"]
        assert report["details"][key]["calculation"]
        assert report["details"][key]["why_it_matters"]


def test_markdown_contains_decision_path_and_governance():
    report = module.build_ai_cio_missed_opportunity_review(opportunities=[workflow_deficiency_record()])
    markdown = module.format_ai_cio_missed_opportunity_review_markdown(report)
    assert "AI CIO Missed Opportunity Review" in markdown
    assert "Decision Path" in markdown
    assert "PLTR" in markdown
    assert "Governance and Paper-Only Safety" in markdown


def test_write_outputs(tmp_path):
    report = module.write_ai_cio_missed_opportunity_review(
        {"opportunities": [workflow_deficiency_record()]}, root_path=str(tmp_path)
    )
    assert report["module_name"] == module.MODULE_NAME
    assert (tmp_path / "ai_cio_missed_opportunity_review.json").exists()
    assert (tmp_path / "ai_cio_missed_opportunity_review.md").exists()
    html_path = tmp_path / "ai_cio_missed_opportunity_review.html"
    assert html_path.exists()
    assert "AI CIO Missed Opportunity Review" in html_path.read_text(encoding="utf-8")


def test_invalid_write_payload_rejected(tmp_path):
    try:
        module.write_ai_cio_missed_opportunity_review("invalid", root_path=str(tmp_path))
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_no_broker_or_order_execution_imports():
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = [
        "import robin_stocks",
        "import alpaca",
        "submit_order(",
        "place_order(",
        "broker.login",
    ]
    assert not any(item in source for item in forbidden)
