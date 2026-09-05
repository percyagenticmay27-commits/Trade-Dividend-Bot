from datetime import datetime, timezone

from src.dividend_bot.enterprise_dividend_gateway import (
    apply_dividend_gateway_to_watchlist,
    evaluate_dividend_gateway,
)

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)


def _qualified_mapping(**updates):
    value = {
        "underlying_symbol": "NVDA",
        "income_symbol": "NVDY",
        "income_mechanism": "option_income_distribution",
        "distribution_frequency": "WEEKLY",
        "observed_income_monthly_percent": 1.25,
        "mechanism_age_months": 3.0,
        "vehicle_status": "ACTIVE",
        "mapping_status": "QUALIFIED",
        "evidence_as_of": "2026-09-05T10:00:00Z",
    }
    value.update(updates)
    return value


def test_gateway_qualifies_only_current_complete_mapping():
    result = evaluate_dividend_gateway("NVDA", mapping=_qualified_mapping(), now=NOW)
    assert result["eligibility_status"] == "QUALIFIED"
    assert result["watchlist_admission_allowed"] is True
    assert result["automatic_activation_allowed"] is False
    assert result["freshness_status"] == "FRESH"


def test_gateway_rechecks_income_and_disqualifies_degraded_mapping():
    result = evaluate_dividend_gateway(
        "NVDA", mapping=_qualified_mapping(observed_income_monthly_percent=0.5), now=NOW
    )
    assert result["eligibility_status"] == "DISQUALIFIED"
    assert result["watchlist_admission_allowed"] is False
    assert any("below" in reason.lower() for reason in result["reasons"])


def test_gateway_fails_closed_for_stale_mapping():
    result = evaluate_dividend_gateway(
        "NVDA", mapping=_qualified_mapping(evidence_as_of="2026-08-01T10:00:00Z"), now=NOW
    )
    assert result["watchlist_admission_allowed"] is False
    assert result["freshness_status"] == "STALE_OR_UNAVAILABLE"


def test_gateway_requires_reviewed_two_month_maturity_without_inventing_days():
    result = evaluate_dividend_gateway(
        "NVDA", mapping=_qualified_mapping(mechanism_age_months=None, maturity_status=None), now=NOW
    )
    assert result["eligibility_status"] == "RESEARCH_REQUIRED"
    assert result["watchlist_admission_allowed"] is False


def test_gateway_rejects_inactive_vehicle():
    result = evaluate_dividend_gateway(
        "NVDA", mapping=_qualified_mapping(vehicle_status="DELISTED"), now=NOW
    )
    assert result["eligibility_status"] == "DISQUALIFIED"
    assert result["watchlist_admission_allowed"] is False


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
