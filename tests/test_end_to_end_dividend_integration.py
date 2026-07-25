from __future__ import annotations

from src.dividend_bot.enterprise_dividend_alert_integration import (
    build_enterprise_dividend_alerts,
)
from src.dividend_bot.enterprise_dividend_cio_advisory_integration import (
    build_enterprise_dividend_cio_advisory,
)
from src.dividend_bot.enterprise_dividend_daily_cycle_integration import (
    STEP_ORDER,
    build_enterprise_dividend_daily_cycle,
)
from src.dividend_bot.enterprise_dividend_learning_integration import (
    build_enterprise_dividend_learning,
)
from src.dividend_bot.enterprise_dividend_review_workflow import (
    build_enterprise_dividend_reviews,
    transition_review,
)
from src.dividend_bot.enterprise_dividend_service_registry_event_wiring import (
    SERVICE_ORDER,
    build_service_registry,
    route_dividend_event,
)

FIXED_TIME = "2026-07-25T16:00:00Z"
REPORTING_PERIOD = "2026-07"
SYMBOL = "ACME"


def _governed_scenario() -> dict:
    dividend_dashboard = {
        "module_name": "enterprise_dividend_dashboard_integration",
        "summary": {
            "symbol": SYMBOL,
            "projected_annual_income": 840.0,
            "prior_projected_annual_income": 1_000.0,
            "income_growth_percent": -16.0,
            "confidence_score": 42.0,
            "evidence_complete": True,
        },
        "risk_flags": [
            {
                "symbol": SYMBOL,
                "alert_type": "DIVIDEND_CUT",
                "severity": "HIGH",
                "message": "Declared dividend fell from $0.50 to $0.42 per share.",
                "recommended_action": "Open a governed dividend review.",
                "evidence_links": ["announcement://ACME/2026-07-15"],
            }
        ],
    }
    investor_dashboard = {
        "module_name": "enterprise_investor_dashboard_integration",
        "summary": {"symbol": SYMBOL, "confidence_score": 42.0},
    }

    alert_report = build_enterprise_dividend_alerts(
        dividend_dashboard=dividend_dashboard,
        investor_dashboard=investor_dashboard,
        reporting_period=REPORTING_PERIOD,
        generated_at_utc=FIXED_TIME,
    )
    review_report = build_enterprise_dividend_reviews(
        alert_report=alert_report,
        generated_at_utc=FIXED_TIME,
    )
    review = transition_review(
        review_report["reviews"][0],
        to_status="UNDER_REVIEW",
        actor="DIVIDEND_REVIEWER",
        reason="Validate the announced cut and projected income decline.",
        assigned_reviewer="DIVIDEND_REVIEWER",
        generated_at_utc="2026-07-25T16:05:00Z",
    )
    review = transition_review(
        review,
        to_status="ESCALATED",
        actor="DIVIDEND_REVIEWER",
        reason="Confirmed material dividend deterioration.",
        escalation_reason="Dividend cut and negative projected income growth require CIO review.",
        decision_reference="decision://ACME/2026-07",
        generated_at_utc="2026-07-25T16:10:00Z",
    )
    review_report = {**review_report, "reviews": [review]}

    forecasts = [
        {
            "symbol": SYMBOL,
            "period": REPORTING_PERIOD,
            "forecast_income": 84.0,
            "source_report": "dividend_forecast.json",
        }
    ]
    actual_income = [
        {
            "symbol": SYMBOL,
            "period": REPORTING_PERIOD,
            "actual_income": 70.0,
            "source_report": "paper_income_actuals.json",
        }
    ]
    learning_report = build_enterprise_dividend_learning(
        forecasts=forecasts,
        actual_income=actual_income,
        alerts=alert_report["alerts"],
        reviews=review_report["reviews"],
        generated_at_utc="2026-07-25T16:15:00Z",
    )

    cio_report = build_enterprise_dividend_cio_advisory(
        income_report={"summary": {"income_growth_percent": -16.0}},
        forecast_report={"summary": {"forecast_accuracy_percent": 83.3333}},
        analytics_report={
            "summary": {
                "income_growth_percent": -16.0,
                "confidence_score": 42.0,
                "forecast_accuracy_percent": 83.3333,
            },
            "holdings": [{"symbol": SYMBOL}],
        },
        alert_report=alert_report,
        review_report=review_report,
        learning_report=learning_report,
        reporting_period=REPORTING_PERIOD,
        generated_at_utc="2026-07-25T16:20:00Z",
    )

    step_results = {name: {"status": "COMPLETED"} for name in STEP_ORDER}
    daily_cycle = build_enterprise_dividend_daily_cycle(
        step_results=step_results,
        reporting_period=REPORTING_PERIOD,
        generated_at_utc="2026-07-25T16:25:00Z",
    )

    registry = build_service_registry(generated_at_utc="2026-07-25T16:30:00Z")
    event = route_dividend_event(
        registry=registry,
        event_type="DIVIDEND_ALERTS_UPDATED",
        source_service="ALERTS",
        payload={"alert_ids": [item["alert_id"] for item in alert_report["alerts"]]},
        correlation_id=daily_cycle["cycle_id"],
        occurred_at_utc="2026-07-25T16:31:00Z",
    )
    duplicate_event = route_dividend_event(
        registry=registry,
        event_type="DIVIDEND_ALERTS_UPDATED",
        source_service="ALERTS",
        payload={"alert_ids": [item["alert_id"] for item in alert_report["alerts"]]},
        correlation_id=daily_cycle["cycle_id"],
        occurred_at_utc="2026-07-25T16:32:00Z",
        processed_event_ids=[event["event_id"]],
    )

    return {
        "alert_report": alert_report,
        "review_report": review_report,
        "learning_report": learning_report,
        "cio_report": cio_report,
        "daily_cycle": daily_cycle,
        "registry": registry,
        "event": event,
        "duplicate_event": duplicate_event,
    }


def test_end_to_end_cut_creates_governed_alert():
    scenario = _governed_scenario()
    alert_types = {item["alert_type"] for item in scenario["alert_report"]["alerts"]}
    assert "DIVIDEND_CUT" in alert_types
    assert scenario["alert_report"]["paper_trade_mode"] is True


def test_end_to_end_income_decline_is_detected():
    scenario = _governed_scenario()
    alert_types = {item["alert_type"] for item in scenario["alert_report"]["alerts"]}
    assert "NEGATIVE_INCOME_GROWTH" in alert_types
    assert "REDUCED_PROJECTED_INCOME" in alert_types


def test_end_to_end_review_preserves_originating_alert():
    scenario = _governed_scenario()
    review = scenario["review_report"]["reviews"][0]
    assert review["alert_id"] in {item["alert_id"] for item in scenario["alert_report"]["alerts"]}
    assert review["status"] == "ESCALATED"
    assert len(review["status_history"]) == 3


def test_end_to_end_review_requires_human_governance():
    review = _governed_scenario()["review_report"]["reviews"][0]
    assert review["human_approval_required"] is True
    assert review["paper_trade_mode"] is True


def test_end_to_end_learning_compares_forecast_with_actual():
    learning = _governed_scenario()["learning_report"]
    assert learning["summary"]["forecast_comparison_count"] == 1
    assert learning["forecast_metrics"][0]["forecast_income"] == 84.0
    assert learning["forecast_metrics"][0]["actual_income"] == 70.0


def test_end_to_end_learning_records_are_append_only():
    learning = _governed_scenario()["learning_report"]
    assert learning["append_only"] is True
    assert learning["policy_auto_change_enabled"] is False
    assert all(item["append_only"] is True for item in learning["learning_records"])


def test_end_to_end_cio_recommends_governed_review():
    cio = _governed_scenario()["cio_report"]
    recommendation = cio["recommendations"][0]
    assert recommendation["symbol"] == SYMBOL
    assert recommendation["recommendation"] in {"REDUCE", "REPLACEMENT_REVIEW", "EXIT_REVIEW"}
    assert recommendation["status"] == "PENDING_INVESTOR_APPROVAL"


def test_end_to_end_cio_preserves_alert_and_review_evidence():
    scenario = _governed_scenario()
    recommendation = scenario["cio_report"]["recommendations"][0]
    assert recommendation["originating_alert_ids"]
    assert recommendation["originating_review_ids"]
    assert set(recommendation["originating_alert_ids"]).issubset(
        {item["alert_id"] for item in scenario["alert_report"]["alerts"]}
    )


def test_end_to_end_daily_cycle_completes_in_dependency_order():
    cycle = _governed_scenario()["daily_cycle"]
    assert cycle["cycle_status"] == "COMPLETED"
    assert [item["step_name"] for item in cycle["steps"]] == list(STEP_ORDER)
    assert cycle["summary"]["completed_steps"] == len(STEP_ORDER)


def test_end_to_end_registry_contains_every_platform_service():
    registry = _governed_scenario()["registry"]
    assert [item["service_name"] for item in registry["services"]] == list(SERVICE_ORDER)
    assert registry["summary"]["service_count"] == len(SERVICE_ORDER)


def test_end_to_end_event_routes_to_review_service():
    event = _governed_scenario()["event"]
    assert event["routing_status"] == "ROUTED"
    assert event["subscriber_services"] == ["REVIEWS"]
    assert event["immutable"] is True


def test_end_to_end_duplicate_event_is_ignored():
    scenario = _governed_scenario()
    duplicate = scenario["duplicate_event"]
    assert duplicate["event_id"] == scenario["event"]["event_id"]
    assert duplicate["duplicate"] is True
    assert duplicate["routing_status"] == "DUPLICATE_IGNORED"
    assert duplicate["subscriber_services"] == []


def test_end_to_end_safety_boundaries_remain_locked():
    scenario = _governed_scenario()
    assert scenario["alert_report"]["broker_execution_enabled"] is False
    assert scenario["learning_report"]["broker_execution_enabled"] is False
    assert scenario["cio_report"]["capital_movement_enabled"] is False
    assert scenario["daily_cycle"]["governance"]["order_execution_allowed"] is False
    assert scenario["registry"]["governance"]["service_invocation_allowed"] is False
