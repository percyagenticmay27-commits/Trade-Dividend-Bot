from __future__ import annotations

from datetime import datetime, timezone

from src.dividend_bot.dividend_strategy_history_alerts import (
    build_strategy_history_alerts,
)


def _performance(as_of: str = "2026-08-11", days: int = 1, observations: int = 1):
    start = "2026-08-11" if days == 1 else "2026-05-29"
    common = {
        "pair": "AMDW / AMDL",
        "evaluation_start": start,
        "evaluation_end": "2026-08-11",
        "max_drawdown_percent": 0.0,
        "observation_count": observations,
        "completed_trade_count": 1 if days > 1 else 0,
    }
    return {
        "as_of_date": as_of,
        "performance": [
            {**common, "strategy_id": "STRATEGY_A", "total_return_percent": 1.0},
            {**common, "strategy_id": "STRATEGY_B", "total_return_percent": 2.0},
        ],
    }


def _assignments():
    return {
        "AMDW / AMDL": {
            "primary_strategy": "STRATEGY_A",
            "previous_primary_strategy": "NONE",
            "assignment_source": "DEFAULT_PRODUCTION_BASELINE",
            "effective_at_utc": "2026-08-11T18:08:00Z",
        }
    }


def test_history_preserves_entry_strategy_and_current_management_separately():
    model = build_strategy_history_alerts(
        assignments={
            "AMDW / AMDL": {
                **_assignments()["AMDW / AMDL"],
                "primary_strategy": "STRATEGY_B",
                "previous_primary_strategy": "STRATEGY_A",
                "assignment_source": "PROMOTED_AFTER_OWNER_REVIEW",
            }
        },
        performance_report=_performance(),
        requests=[],
        journal_events=[{
            "pair": "AMDW / AMDL",
            "event_type": "STRATEGY_PROMOTION_ACTIVATED",
            "new_primary_strategy": "STRATEGY_B",
            "recorded_at_utc": "2026-08-11T18:08:00Z",
        }],
        paper_state={
            "pairs": {
                "AMDW / AMDL": {
                    "strategy_owner": "STRATEGY_A",
                    "a_in_sgov": False,
                    "b_in_sgov": False,
                }
            }
        },
        now=datetime(2026, 8, 11, 20, tzinfo=timezone.utc),
    )
    history = model["histories"][0]
    assert history["original_entry_strategy"] == "STRATEGY_A"
    assert history["current_management_strategy"] == "STRATEGY_B"
    assert history["previous_primary_strategy"] == "STRATEGY_A"
    assert history["position_status"] == "OPEN_ETF_POSITION"
    assert history["events"][0]["event_type"] == "STRATEGY_PROMOTION_ACTIVATED"
    assert model["broker_execution_enabled"] is False


def test_pending_review_and_near_deadline_create_owner_alerts():
    model = build_strategy_history_alerts(
        assignments=_assignments(),
        performance_report=_performance(),
        requests=[{
            "pair": "AMDW / AMDL",
            "status": "PENDING_OWNER_REVIEW",
            "proposed_primary_strategy": "STRATEGY_B",
            "veto_deadline": "2026-08-12T20:00:00Z",
        }],
        journal_events=[],
        paper_state={"pairs": {}},
        now=datetime(2026, 8, 11, 20, tzinfo=timezone.utc),
    )
    alert = model["alerts"][0]
    assert alert["alert_type"] == "VETO_DEADLINE_APPROACHING"
    assert alert["severity"] == "CRITICAL"
    assert "STRATEGY_B" in alert["message"]


def test_missing_and_stale_evidence_are_explicit():
    missing = build_strategy_history_alerts(
        assignments=_assignments(),
        performance_report={},
        requests=[],
        journal_events=[],
        paper_state={"pairs": {}},
        now=datetime(2026, 8, 11, 20, tzinfo=timezone.utc),
    )
    types = {row["alert_type"] for row in missing["alerts"]}
    assert "MISSING_STRATEGY_EVIDENCE" in types
    assert "MISSING_PAIR_COMPARISON" in types

    stale = build_strategy_history_alerts(
        assignments=_assignments(),
        performance_report=_performance(as_of="2026-08-01"),
        requests=[],
        journal_events=[],
        paper_state={"pairs": {}},
        now=datetime(2026, 8, 11, 20, tzinfo=timezone.utc),
    )
    assert "STALE_STRATEGY_EVIDENCE" in {
        row["alert_type"] for row in stale["alerts"]
    }


def test_candidate_nearing_qualification_is_informational():
    model = build_strategy_history_alerts(
        assignments=_assignments(),
        performance_report=_performance(days=75, observations=55),
        requests=[],
        journal_events=[],
        paper_state={"pairs": {}},
        now=datetime(2026, 8, 11, 20, tzinfo=timezone.utc),
    )
    alert = next(
        row for row in model["alerts"]
        if row["alert_type"] == "CANDIDATE_NEARING_QUALIFICATION"
    )
    assert alert["severity"] == "INFO"
    assert "75/90" in alert["message"]
