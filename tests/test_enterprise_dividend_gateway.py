from datetime import datetime, timezone
import json

from src.dividend_bot.enterprise_dividend_gateway import (
    apply_dividend_gateway_to_watchlist,
    evaluate_dividend_gateway,
)

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)


def _qualified_mapping(**updates):
    value = {
        "underlying_symbol": "NVDA",
        "income_symbol": "NVDW",
        "income_mechanism": "option_income_distribution",
        "distribution_frequency": "WEEKLY",
        "observed_income_monthly_percent": 1.25,
        "fund_age_days": 90,
        "vehicle_status": "ACTIVE",
        "mapping_status": "QUALIFIED",
        "evidence_as_of": "2026-09-05T10:00:00Z",
        "freshness_status": "FRESH",
    }
    value.update(updates)
    return value


def test_gateway_qualifies_only_current_complete_mapping():
    result = evaluate_dividend_gateway("NVDA", mapping=_qualified_mapping(), now=NOW)
    assert result["eligibility_status"] == "QUALIFIED"
    assert result["watchlist_admission_allowed"] is True
    assert result["automatic_activation_allowed"] is False
    assert result["freshness_status"] == "FRESH"
    assert result["minimum_fund_age_days"] == 60


def test_gateway_rechecks_monthly_income_and_disqualifies_degraded_mapping():
    result = evaluate_dividend_gateway(
        "NVDA", mapping=_qualified_mapping(observed_income_monthly_percent=0.5), now=NOW
    )
    assert result["eligibility_status"] == "DISQUALIFIED"
    assert result["watchlist_admission_allowed"] is False
    assert any("below" in reason.lower() for reason in result["reasons"])


def test_gateway_uses_fund_age_days_as_pre_watchlist_gate():
    result = evaluate_dividend_gateway(
        "NVDA", mapping=_qualified_mapping(fund_age_days=59), now=NOW
    )
    assert result["eligibility_status"] == "DISQUALIFIED"
    assert result["watchlist_admission_allowed"] is False
    assert any("60-day minimum" in reason for reason in result["reasons"])


def test_gateway_accepts_fund_at_60_day_minimum():
    result = evaluate_dividend_gateway(
        "NVDA", mapping=_qualified_mapping(fund_age_days=60), now=NOW
    )
    assert result["eligibility_status"] == "QUALIFIED"
    assert result["watchlist_admission_allowed"] is True


def test_gateway_requires_fund_age_evidence():
    result = evaluate_dividend_gateway(
        "NVDA", mapping=_qualified_mapping(fund_age_days=None), now=NOW
    )
    assert result["eligibility_status"] == "RESEARCH_REQUIRED"
    assert result["watchlist_admission_allowed"] is False


def test_gateway_fails_closed_when_upstream_freshness_is_unverified():
    result = evaluate_dividend_gateway(
        "NVDA", mapping=_qualified_mapping(freshness_status=None), now=NOW
    )
    assert result["watchlist_admission_allowed"] is False
    assert result["freshness_status"] == "UNVERIFIED"
    assert result["eligibility_status"] == "RESEARCH_REQUIRED"


def test_gateway_rejects_inactive_vehicle():
    result = evaluate_dividend_gateway(
        "NVDA", mapping=_qualified_mapping(vehicle_status="DELISTED"), now=NOW
    )
    assert result["eligibility_status"] == "DISQUALIFIED"
    assert result["watchlist_admission_allowed"] is False


def test_gateway_merges_scheduled_suitability_evidence_by_income_vehicle(tmp_path):
    results = tmp_path / "results"
    inputs = tmp_path / "inputs"
    results.mkdir()
    inputs.mkdir()
    (results / "enterprise_dividend_income_mapping.json").write_text(json.dumps({
        "candidates": [{
            "underlying_symbol": "AMD",
            "income_symbol": "AMDY",
            "income_mechanism": "OPTIONS_PREMIUM",
            "distribution_frequency": "WEEKLY",
            "mapping_status": "REVIEWED_MAPPING_AVAILABLE",
        }]
    }), encoding="utf-8")
    (inputs / "dividend_suitability_evidence.json").write_text(json.dumps({
        "vehicles": [{
            "income_symbol": "AMDY",
            "observed_income_monthly_percent": 1.2,
            "observed_income_month": "2026-08",
            "monthly_income_method": "COMPLETED_CALENDAR_MONTH_DISTRIBUTIONS_DIVIDED_BY_MONTH_END_VEHICLE_PRICE",
            "fund_age_days": 1081,
            "vehicle_status": "ACTIVE",
            "evidence_as_of": "2026-09-04",
            "freshness_status": "FRESH",
        }]
    }), encoding="utf-8")

    result = evaluate_dividend_gateway("AMD", tmp_path, now=NOW)
    assert result["eligibility_status"] == "QUALIFIED"
    assert result["watchlist_admission_allowed"] is True
    assert result["observed_income_month"] == "2026-08"
    assert result["observed_income_monthly_percent"] == 1.2


def test_gateway_excludes_unqualified_nonheld_but_keeps_held_for_lifecycle_review(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    (results / "enterprise_dividend_income_mapping.json").write_text(
        '[{"underlying_symbol":"NVDA","income_symbol":null,"income_mechanism":null,"distribution_frequency":null,"mapping_status":"RESEARCH_REQUIRED"}]',
        encoding="utf-8",
    )
    row = {
        "watchlist": [
            {"symbol": "NVDA", "currently_held": False},
            {"symbol": "NVDA", "currently_held": True},
        ]
    }
    result = apply_dividend_gateway_to_watchlist(row, tmp_path, now=NOW)
    assert len(result["watchlist"]) == 1
    assert result["watchlist"][0]["currently_held"] is True
    assert result["watchlist"][0]["gateway_lifecycle_review_required"] is True
    assert result["watchlist_count"] == 1
    assert len(result["dividend_gateway_research"]) == 2
