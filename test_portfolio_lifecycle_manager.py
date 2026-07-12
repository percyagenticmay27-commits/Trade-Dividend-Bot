import json
from pathlib import Path

import pytest

import portfolio_lifecycle_manager as module


def sample_allocations():
    return [
        {
            "allocation_id": "A1",
            "strategy_name": "AMDW + PLTU",
            "component_symbols": ["AMDW", "PLTU"],
            "strategy_type": "GROWTH_INCOME_PAIR",
            "sector_context": "Technology",
            "current_rank": 1,
            "lifecycle_state": "ACTIVE",
            "current_allocation_percentage": 60,
            "current_paper_value": 300,
            "opened_date": "2026-07-01",
            "capital_efficiency_score": 84.3,
            "decision_stability_score": 82.7,
            "evidence_confidence_score": 94,
            "current_recommendation": "KEEP",
        },
        {
            "allocation_id": "A2",
            "strategy_name": "SGOV Reserve",
            "component_symbols": ["SGOV"],
            "strategy_type": "RESERVE",
            "current_rank": 2,
            "lifecycle_state": "ACTIVE",
            "current_allocation_percentage": 40,
            "current_paper_value": 200,
            "opened_date": "2026-07-01",
        },
    ]


def test_public_functions_exist():
    names = [
        "build_portfolio_lifecycle",
        "apply_lifecycle_event",
        "apply_decision_journal_entry",
        "get_allocation_state",
        "list_active_allocations",
        "list_sgov_allocations",
        "list_pending_allocations",
        "format_portfolio_lifecycle_markdown",
        "write_portfolio_lifecycle",
        "build_and_write_portfolio_lifecycle",
    ]
    for name in names:
        assert callable(getattr(module, name))


def test_paper_only_flags():
    report = module.build_portfolio_lifecycle([])
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["execution_enabled"] is False
    assert report["reporting_only"] is True


def test_builds_active_state_and_summary():
    report = module.build_portfolio_lifecycle(sample_allocations(), as_of_date="2026-07-12")
    assert report["portfolio_summary"]["allocation_count"] == 2
    assert report["portfolio_summary"]["active_count"] == 2
    assert report["portfolio_summary"]["active_allocation_percentage"] == 100
    assert report["active_allocations"][0]["allocation_id"] == "A1"


def test_maturity_classification():
    assert module.classify_allocation_maturity(0) == "NEW"
    assert module.classify_allocation_maturity(5) == "NEW"
    assert module.classify_allocation_maturity(6) == "DEVELOPING"
    assert module.classify_allocation_maturity(21) == "ESTABLISHED"
    assert module.classify_allocation_maturity(90) == "LONG_TERM_LEADER"


def test_sgov_parking_tracks_reason_and_release_condition():
    report = module.build_portfolio_lifecycle(sample_allocations())
    updated = module.apply_lifecycle_event(
        report,
        "A1",
        {
            "event_type": "CAPITAL_PARKED_IN_SGOV",
            "percentage": 60,
            "reason": "Underlying earnings protection",
            "release_condition": "Earnings complete and requalification passed",
            "authorization": "AUTOMATIC_PAPER_PROTECTION",
        },
    )
    state = module.get_allocation_state(updated, "A1")
    assert state["lifecycle_state"] == "PARKED_IN_SGOV"
    assert state["current_allocation_percentage"] == 0
    assert state["sgov_linked_percentage"] == 60
    assert state["sgov_reason"] == "Underlying earnings protection"
    assert state["sgov_release_condition"] == "Earnings complete and requalification passed"
    assert state["sgov_parking_event_count"] == 1
    assert len(module.list_sgov_allocations(updated)) == 1


def test_protection_clear_moves_to_reentry_pending():
    report = module.build_portfolio_lifecycle([
        {
            "allocation_id": "A1",
            "strategy_name": "AMDW + PLTU",
            "lifecycle_state": "PARKED_IN_SGOV",
            "sgov_linked_percentage": 50,
            "earnings_lock_active": True,
        }
    ])
    updated = module.apply_lifecycle_event(
        report,
        "A1",
        {"event_type": "PROTECTION_CLEARED", "reentry_eligible": False},
    )
    state = module.get_allocation_state(updated, "A1")
    assert state["lifecycle_state"] == "REENTRY_PENDING"
    assert state["earnings_lock_active"] is False
    assert state["reentry_eligible"] is False
    assert len(module.list_pending_allocations(updated)) == 1


def test_reentry_approved_restores_active_allocation():
    report = module.build_portfolio_lifecycle([
        {
            "allocation_id": "A1",
            "strategy_name": "AMDW + PLTU",
            "lifecycle_state": "REENTRY_PENDING",
            "sgov_linked_percentage": 35,
        }
    ])
    updated = module.apply_lifecycle_event(
        report,
        "A1",
        {"event_type": "REENTRY_APPROVED", "allocation_percentage": 35},
    )
    state = module.get_allocation_state(updated, "A1")
    assert state["lifecycle_state"] == "ACTIVE"
    assert state["current_allocation_percentage"] == 35
    assert state["sgov_linked_percentage"] == 0
    assert state["reentry_eligible"] is True


def test_replacement_relationship_is_preserved():
    report = module.build_portfolio_lifecycle(sample_allocations())
    pending = module.apply_lifecycle_event(
        report,
        "A1",
        {"event_type": "REPLACEMENT_PREPARED", "replacement_allocation_id": "A3"},
    )
    replaced = module.apply_lifecycle_event(
        pending,
        "A1",
        {"event_type": "REPLACEMENT_APPLIED", "replacement_allocation_id": "A3"},
    )
    state = module.get_allocation_state(replaced, "A1")
    assert state["lifecycle_state"] == "REPLACED"
    assert state["replacement_allocation_id"] == "A3"
    assert state["replacement_count"] == 1
    assert state["current_allocation_percentage"] == 0
    assert len(state["event_history"]) == 2


def test_invalid_transition_is_rejected():
    report = module.build_portfolio_lifecycle([
        {"allocation_id": "A1", "strategy_name": "Closed", "lifecycle_state": "CLOSED"}
    ])
    with pytest.raises(ValueError):
        module.apply_lifecycle_event(report, "A1", {"event_type": "ALLOCATION_OPENED"})


def test_decision_journal_entry_updates_state_and_link():
    report = module.build_portfolio_lifecycle(sample_allocations())
    updated = module.apply_decision_journal_entry(
        report,
        {
            "journal_entry_id": "J-100",
            "current_candidate_id": "A1",
            "final_capital_action": "KEEP",
            "current_capital_efficiency_score": 86.1,
            "decision_stability_score": 88,
            "decision_stability_label": "STABLE",
            "evidence_confidence_score": 95,
            "evidence_confidence_label": "VERY_HIGH",
            "market_regime": "BULL",
            "challenger_candidate_id": "A3",
            "capital_efficiency_score_difference": 1.5,
            "ai_cio_verdict": "Continue holding because the challenger has not earned replacement.",
        },
    )
    state = module.get_allocation_state(updated, "A1")
    assert state["latest_decision_journal_entry_id"] == "J-100"
    assert state["review_count"] == 1
    assert state["capital_efficiency_score"] == 86.1
    assert state["strongest_challenger"] == "A3"


def test_rank_and_allocation_update():
    report = module.build_portfolio_lifecycle(sample_allocations())
    updated = module.apply_lifecycle_event(
        report,
        "A1",
        {
            "event_type": "ALLOCATION_REVIEWED",
            "updates": {"current_rank": 2, "current_allocation_percentage": 45},
        },
    )
    state = module.get_allocation_state(updated, "A1")
    assert state["current_rank"] == 2
    assert state["current_allocation_percentage"] == 45


def test_query_returns_copy_not_live_reference():
    report = module.build_portfolio_lifecycle(sample_allocations())
    state = module.get_allocation_state(report, "A1")
    state["strategy_name"] = "MUTATED"
    assert module.get_allocation_state(report, "A1")["strategy_name"] == "AMDW + PLTU"


def test_empty_portfolio_is_valid():
    report = module.build_portfolio_lifecycle([])
    assert report["portfolio_summary"]["allocation_count"] == 0
    assert report["allocations"] == []
    assert report["errors"] == []


def test_malformed_allocation_is_rejected():
    with pytest.raises(ValueError):
        module.build_portfolio_lifecycle([{"strategy_name": ""}])
    with pytest.raises(ValueError):
        module.build_portfolio_lifecycle(["bad"])


def test_nonfinite_numbers_are_safely_normalized():
    report = module.build_portfolio_lifecycle([
        {
            "allocation_id": "A1",
            "strategy_name": "Test",
            "lifecycle_state": "ACTIVE",
            "current_allocation_percentage": float("inf"),
            "capital_efficiency_score": float("nan"),
        }
    ])
    state = module.get_allocation_state(report, "A1")
    assert state["current_allocation_percentage"] == 0
    assert state["capital_efficiency_score"] == 0


def test_outputs_are_created(tmp_path):
    report = module.build_and_write_portfolio_lifecycle(sample_allocations(), root_path=str(tmp_path))
    assert report["portfolio_summary"]["allocation_count"] == 2
    for filename in module.DEFAULT_OUTPUT_FILES.values():
        assert (tmp_path / filename).exists()
    parsed = json.loads((tmp_path / "portfolio_lifecycle.json").read_text(encoding="utf-8"))
    assert parsed["module_name"] == "portfolio_lifecycle_manager"
    markdown = (tmp_path / "portfolio_lifecycle.md").read_text(encoding="utf-8")
    assert "Capital Efficiency Score" in markdown
    assert "Decision Stability Score" in markdown
    assert "SGOV and Protection Activity" in markdown
    html_text = (tmp_path / "portfolio_lifecycle.html").read_text(encoding="utf-8")
    assert "Portfolio Lifecycle Manager" in html_text


def test_static_safety_has_no_restricted_execution_calls():
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    restricted = ["subprocess.", "os.system(", "place_order(", "execute_trade("]
    assert not any(term in source for term in restricted)
