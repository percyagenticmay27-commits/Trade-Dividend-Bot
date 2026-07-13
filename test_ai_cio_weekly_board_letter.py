from pathlib import Path

import ai_cio_weekly_board_letter as module


def sample_payload():
    return {
        "week_start": "2026-07-06",
        "week_end": "2026-07-12",
        "portfolio_summary": {"portfolio_value": 500.0},
        "wealth_attribution": {
            "net_total_wealth_contribution": 39.2,
            "net_total_wealth_percent": 7.84,
            "primary_driver": "Capital Growth",
            "largest_drag": "Portfolio Turnover Cost",
        },
        "decision_journal": {
            "entries": [
                {"capital_action": "KEEP", "reason": "Small challenger advantage.", "applied_to_paper_portfolio": False},
                {"capital_action": "PARK IN SGOV", "reason": "Earnings protection.", "applied_to_paper_portfolio": True},
            ]
        },
        "portfolio_lifecycle": {
            "allocations": [
                {"allocation_id": "QQQI + TQQQ", "lifecycle_status": "ACTIVE"},
                {"allocation_id": "AMDW + PLTU", "lifecycle_status": "PROTECTED"},
            ]
        },
        "opportunity_replacement": {"recommendation": "KEEP_CURRENT", "reason": "No meaningful improvement."},
        "earnings_events": {"actions": [{"allocation_id": "AMDW + PLTU", "recommendation": "PARK_IN_SGOV"}]},
        "market_intelligence": {"overall_market_intelligence_label": "SUPPORTIVE", "overall_market_intelligence_score": 73.5, "market_regime": "BULL"},
        "portfolio_risk": {"overall_portfolio_risk_label": "LOW", "overall_portfolio_risk_score": 24.8, "risk_momentum": {"direction": "STABLE"}},
        "performance_analytics": {"ai_cio_self_assessment_score": 95.7, "grade": "A", "improvement_findings": ["Collect more replacement outcomes."]},
        "upcoming_items": [{"event": "Post-earnings requalification", "date": "2026-07-14", "importance": "High"}],
    }


def build(**overrides):
    payload = sample_payload()
    payload.update(overrides)
    return module.build_ai_cio_weekly_board_letter(**payload)


def test_public_functions_exist():
    assert callable(module.build_ai_cio_weekly_board_letter)
    assert callable(module.format_ai_cio_weekly_board_letter_markdown)
    assert callable(module.format_ai_cio_weekly_board_letter_html)
    assert callable(module.write_ai_cio_weekly_board_letter)
    assert callable(module.build_and_write_ai_cio_weekly_board_letter)


def test_paper_only_flags():
    report = build()
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["reporting_only"] is True


def test_weekly_scorecard_values():
    score = build()["weekly_scorecard"]
    assert score["net_total_wealth_amount"] == 39.2
    assert score["net_total_wealth_percent"] == 7.84
    assert score["primary_driver"] == "Capital Growth"


def test_market_and_risk_context():
    score = build()["weekly_scorecard"]
    assert score["market_environment_label"] == "Supportive"
    assert score["market_regime"] == "Bull"
    assert score["portfolio_risk_label"] == "Low"
    assert score["risk_momentum"] == "Stable"


def test_decision_counts():
    review = build()["decision_review"]
    assert review["decisions_reviewed"] == 2
    assert review["paper_changes"] == 1
    assert review["holds_or_no_change"] == 1


def test_portfolio_state_counts():
    state = build()["portfolio_state"]
    assert state["active_allocations"] == 1
    assert state["sgov_or_protected_allocations"] == 1
    assert state["earnings_reviews"] == 1
    assert state["earnings_protections"] == 1


def test_learning_findings_preserved():
    report = build()
    assert report["what_the_ai_cio_learned"] == ["Collect more replacement outcomes."]


def test_missing_learning_has_safe_fallback():
    report = build(performance_analytics={})
    assert "Insufficient completed history" in report["what_the_ai_cio_learned"][0]


def test_upcoming_items_preserved():
    report = build()
    assert report["next_week_watchlist"][0]["event"] == "Post-earnings requalification"
    assert report["next_week_watchlist"][0]["importance"] == "High"


def test_governance_rules_are_locked():
    governance = build()["governance"]
    assert governance["automatic_policy_changes_allowed"] is False
    assert governance["investor_approval_required_for_policy_changes"] is True
    assert governance["sector_allocation_entitlement"] is False
    assert governance["html_ui_modernization_deferred"] is True


def test_every_metric_has_more_reference():
    report = build()
    for key in ("total_wealth", "portfolio_risk", "market_environment", "decision_quality", "sgov_activity"):
        assert key in report["details"]
        detail = report["details"][key]
        assert detail["definition"]
        assert detail["calculation"]
        assert detail["why_it_matters"]


def test_markdown_contains_investor_sections():
    markdown = module.format_ai_cio_weekly_board_letter_markdown(build())
    assert "Dear Investor" in markdown
    assert "Weekly Scorecard" in markdown
    assert "What Happened This Week" in markdown
    assert "What I Learned This Week" in markdown
    assert "Next Week" in markdown
    assert "AI Chief Investment Officer" in markdown


def test_markdown_contains_more_links():
    markdown = module.format_ai_cio_weekly_board_letter_markdown(build())
    assert markdown.count("More...") >= 5
    assert "Total Wealth" in markdown
    assert "Decision Quality" in markdown


def test_empty_optional_inputs_create_warnings_not_errors():
    report = module.build_ai_cio_weekly_board_letter()
    assert report["warnings"]
    assert report["errors"] == []
    assert report["paper_trade_mode"] is True


def test_nonfinite_values_are_sanitized():
    report = build(
        portfolio_summary={"portfolio_value": float("inf")},
        wealth_attribution={"net_total_wealth_contribution": float("nan"), "net_total_wealth_percent": float("inf")},
    )
    assert report["portfolio_value"] == 0.0
    assert report["weekly_scorecard"]["net_total_wealth_amount"] == 0.0
    assert report["weekly_scorecard"]["net_total_wealth_percent"] == 0.0


def test_write_outputs(tmp_path):
    report = module.write_ai_cio_weekly_board_letter(sample_payload(), root_path=str(tmp_path))
    assert report["module_name"] == module.MODULE_NAME
    assert (tmp_path / "ai_cio_weekly_board_letter.json").exists()
    assert (tmp_path / "ai_cio_weekly_board_letter.md").exists()
    html_path = tmp_path / "ai_cio_weekly_board_letter.html"
    assert html_path.exists()
    assert "AI CIO Weekly Board Letter" in html_path.read_text(encoding="utf-8")


def test_invalid_payload_rejected(tmp_path):
    try:
        module.write_ai_cio_weekly_board_letter("invalid", root_path=str(tmp_path))
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_no_broker_or_order_execution_imports():
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = ["import robin_stocks", "import alpaca", "submit_order(", "place_order(", "broker.login"]
    assert not any(item in source for item in forbidden)
