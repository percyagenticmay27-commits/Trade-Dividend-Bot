from datetime import date, timedelta
from pathlib import Path

import pytest

import earnings_event_manager as module


TODAY = date(2026, 7, 12)


def allocations(in_sgov=False):
    return [
        {
            "allocation_id": "AMDW + PLTU",
            "symbols": ["AMD", "PLTR"],
            "allocation_percent": 40,
            "paper_value": 200,
            "lifecycle_state": "PARKED_IN_SGOV" if in_sgov else "ACTIVE",
            "currently_in_sgov": in_sgov,
            "leverage_multiplier": 1.5,
        }
    ]


def event(days=2, **overrides):
    payload = {
        "event_id": "PLTR_Q2",
        "symbol": "PLTR",
        "earnings_date": (TODAY + timedelta(days=days)).isoformat(),
        "confirmed": True,
        "event_risk": 85,
        "evidence_confidence": 98,
    }
    payload.update(overrides)
    return payload


def build(**overrides):
    payload = {
        "allocations": allocations(),
        "earnings_events": [event()],
        "evaluation_date": TODAY.isoformat(),
        "protection_window_days": 2,
        "prepare_window_days": 7,
        "post_event_cooling_days": 1,
    }
    payload.update(overrides)
    return module.build_earnings_event_manager(**payload)


def test_public_functions_exist():
    assert callable(module.build_earnings_event_manager)
    assert callable(module.format_earnings_event_markdown)
    assert callable(module.format_earnings_event_html)
    assert callable(module.write_earnings_event_manager)
    assert callable(module.build_and_write_earnings_event_manager)


def test_paper_only_flags():
    report = build()
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["reporting_only"] is True


def test_no_event_defaults_to_no_action():
    report = build(earnings_events=[])
    record = report["records"][0]
    assert record["earnings_status"] == "NO_EVENT"
    assert record["recommended_action"] == "NO_ACTION"


def test_prepare_window_prepares_sgov_without_parking():
    report = build(earnings_events=[event(days=5)])
    record = report["records"][0]
    assert record["earnings_status"] == "PREPARE_WINDOW"
    assert record["recommended_action"] == "PREPARE_SGOV"
    assert record["sgov_status"] == "NOT_PARKED"


def test_protection_window_parks_current_allocation():
    report = build(earnings_events=[event(days=2)])
    record = report["records"][0]
    assert record["earnings_status"] == "PROTECTION_WINDOW"
    assert record["recommended_action"] == "PARK_IN_SGOV"
    assert record["sgov_status"] == "PARK_RECOMMENDED"
    assert record["decision_journal_event"] == "EARNINGS_PROTECTION_STARTED"
    assert record["lifecycle_update"] == "PARKED_IN_SGOV"


def test_already_parked_capital_stays_in_sgov():
    report = build(allocations=allocations(in_sgov=True), earnings_events=[event(days=1)])
    record = report["records"][0]
    assert record["recommended_action"] == "HOLD_IN_SGOV"
    assert record["sgov_status"] == "PARKED"


def test_stale_event_data_does_not_trigger_automatic_parking():
    report = build(earnings_events=[event(days=1, data_stale=True)])
    record = report["records"][0]
    assert record["earnings_status"] == "DATA_REVIEW_REQUIRED"
    assert record["recommended_action"] == "MONITOR"


def test_unconfirmed_event_does_not_trigger_automatic_parking():
    report = build(earnings_events=[event(days=1, confirmed=False)])
    record = report["records"][0]
    assert record["recommended_action"] == "MONITOR"


def test_post_event_cooling_period_holds_sgov():
    report = build(
        allocations=allocations(in_sgov=True),
        earnings_events=[event(days=0, completed=True)],
        post_event_cooling_days=2,
    )
    record = report["records"][0]
    assert record["earnings_status"] == "POST_EVENT_REVIEW"
    assert record["recommended_action"] == "HOLD_IN_SGOV"


def test_invalid_post_event_data_holds_sgov():
    report = build(
        allocations=allocations(in_sgov=True),
        earnings_events=[event(days=-3, completed=True, post_event_data_valid=False)],
    )
    record = report["records"][0]
    assert record["recommended_action"] == "HOLD_IN_SGOV"


def test_prior_allocation_can_reenter_only_after_requalification():
    candidates = {
        "AMDW + PLTU": [
            {
                "candidate_id": "AMDW + PLTU",
                "capital_efficiency_score": 88,
                "evidence_confidence": 95,
                "qualified": True,
                "is_prior_allocation": True,
            }
        ]
    }
    report = build(
        allocations=allocations(in_sgov=True),
        earnings_events=[event(days=-2, completed=True)],
        candidates_by_allocation=candidates,
    )
    record = report["records"][0]
    assert record["recommended_action"] == "REENTER_PRIOR"


def test_next_best_candidate_replaces_prior_after_event():
    candidates = {
        "AMDW + PLTU": [
            {
                "candidate_id": "AMDW + PLTU",
                "capital_efficiency_score": 82,
                "evidence_confidence": 94,
                "qualified": True,
                "is_prior_allocation": True,
            },
            {
                "candidate_id": "AMDW + GGLL",
                "capital_efficiency_score": 91,
                "evidence_confidence": 93,
                "qualified": True,
            },
        ]
    }
    report = build(
        allocations=allocations(in_sgov=True),
        earnings_events=[event(days=-2, completed=True)],
        candidates_by_allocation=candidates,
    )
    record = report["records"][0]
    assert record["recommended_action"] == "ALLOCATE_TO_BEST_CANDIDATE"
    assert record["best_candidate"]["candidate_id"] == "AMDW + GGLL"


def test_no_qualified_candidate_keeps_capital_under_review():
    candidates = {
        "AMDW + PLTU": [
            {
                "candidate_id": "AMDW + GGLL",
                "capital_efficiency_score": 95,
                "evidence_confidence": 40,
                "qualified": True,
            }
        ]
    }
    report = build(
        allocations=allocations(in_sgov=True),
        earnings_events=[event(days=-2, completed=True)],
        candidates_by_allocation=candidates,
    )
    assert report["records"][0]["recommended_action"] == "REENTRY_REVIEW"


def test_release_condition_does_not_auto_return_capital():
    report = build(allocations=allocations(in_sgov=True), earnings_events=[event(days=1)])
    condition = report["records"][0]["release_condition"].lower()
    assert "qualified opportunity" in condition
    assert "automatically return" not in condition


def test_event_risk_score_is_finite_and_bounded():
    report = build(earnings_events=[event(days=1, event_risk=float("inf"))])
    score = report["records"][0]["event_risk_score"]
    assert 0 <= score <= 100


def test_metric_details_are_complete():
    report = build()
    for key in ("earnings_status", "event_risk_score", "sgov_status", "release_condition", "reentry_status"):
        detail = report["details"][key]
        assert detail["definition"]
        assert detail["calculation"]
        assert detail["why_it_matters"]


def test_markdown_uses_full_names_and_explanations():
    markdown = module.format_earnings_event_markdown(build())
    assert "Earnings Event Manager" in markdown
    assert "Event Risk Score" in markdown
    assert "Release Condition" in markdown
    assert "Investor Control" in markdown
    assert "Paper-Only Safety" in markdown


def test_outputs_are_created(tmp_path):
    report = module.write_earnings_event_manager(
        {
            "allocations": allocations(),
            "earnings_events": [event()],
            "evaluation_date": TODAY.isoformat(),
        },
        root_path=str(tmp_path),
    )
    assert report["module_name"] == module.MODULE_NAME
    assert (tmp_path / "earnings_event_manager.json").exists()
    assert (tmp_path / "earnings_event_manager.md").exists()
    html_path = tmp_path / "earnings_event_manager.html"
    assert html_path.exists()
    assert "Earnings Event Manager" in html_path.read_text(encoding="utf-8")


def test_empty_inputs_are_valid_with_warnings():
    report = module.build_earnings_event_manager(allocations=[], earnings_events=[])
    assert report["allocation_count"] == 0
    assert report["event_count"] == 0
    assert len(report["warnings"]) == 2
    assert report["errors"] == []


def test_malformed_inputs_are_rejected():
    with pytest.raises(ValueError):
        module.build_earnings_event_manager(allocations="bad", earnings_events=[])
    with pytest.raises(ValueError):
        module.build_earnings_event_manager(allocations=[], earnings_events="bad")
    with pytest.raises(ValueError):
        module.build_earnings_event_manager(allocations=[], earnings_events=[], candidates_by_allocation=[])


def test_source_contains_no_broker_or_order_execution_calls():
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = ["import robin_stocks", "import alpaca", "submit_order(", "place_order(", "broker.login", "requests.post("]
    assert not any(item in source for item in forbidden)
