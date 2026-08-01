from __future__ import annotations

import pytest

from src.dividend_bot.enterprise_contributor_engine import (
    build_all_enterprise_contributor_details,
    build_enterprise_contributor_details,
)


def _interpretation() -> dict[str, object]:
    return {
        "strategies": [
            {
                "strategy_id": "SWING-001",
                "display_name": "Trade Swing Bot",
                "strategy_type": "SWING",
                "income": 100.0,
                "realized_gain": 300.0,
                "unrealized_gain": 75.0,
                "win_rate_percent": 60.0,
                "wins": 6,
                "losses": 4,
                "completed_observations": 10,
                "yield_percent": 2.0,
                "yield_basis": 4000.0,
                "capital_appreciation": 500.0,
                "watchlist_count": 8,
                "performance_percent": 12.0,
                "runtime_status": "ONLINE",
                "health_status": "HEALTHY",
                "readiness": "READY",
                "lifecycle_status": "ACTIVE",
                "evidence_status": "AVAILABLE",
                "paper_trade_mode": True,
                "reporting_only": True,
            },
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Income Strategy",
                "strategy_type": "DIVIDEND_ETF",
                "income": 300.0,
                "realized_gain": 100.0,
                "unrealized_gain": 25.0,
                "win_rate_percent": 80.0,
                "wins": 8,
                "losses": 2,
                "completed_observations": 10,
                "yield_percent": 6.0,
                "yield_basis": 6000.0,
                "capital_appreciation": 200.0,
                "watchlist_count": 4,
                "performance_percent": 8.0,
                "runtime_status": "ONLINE",
                "health_status": "HEALTHY",
                "readiness": "READY",
                "lifecycle_status": "ACTIVE",
                "evidence_status": "AVAILABLE",
                "paper_trade_mode": True,
                "reporting_only": True,
            },
        ]
    }


def test_income_details_sum_and_contribution_percentages() -> None:
    document, warnings = build_enterprise_contributor_details(
        interpretation=_interpretation(), metric_id="income"
    )

    assert warnings == []
    assert document["enterprise_value"] == 400.0
    assert document["complete"] is True
    assert [item["strategy_id"] for item in document["contributors"]] == [
        "DIVIDEND-001",
        "SWING-001",
    ]
    assert document["contributors"][0]["contribution_percent"] == 75.0
    assert document["contributors"][1]["contribution_percent"] == 25.0


def test_missing_evidence_is_not_reported_not_zero() -> None:
    interpretation = _interpretation()
    interpretation["strategies"][1].pop("income")

    document, _ = build_enterprise_contributor_details(
        interpretation=interpretation, metric_id="income"
    )

    dividend = document["contributors"][0]
    assert dividend["value"] is None
    assert dividend["display_status"] == "NOT_REPORTED"
    assert document["enterprise_value"] == 100.0
    assert document["complete"] is False
    assert document["missing_strategy_ids"] == ["DIVIDEND-001"]


def test_win_rate_is_weighted_by_completed_observations() -> None:
    document, _ = build_enterprise_contributor_details(
        interpretation=_interpretation(), metric_id="win_rate"
    )

    assert document["enterprise_value"] == 70.0
    assert document["calculation_method"] == "WEIGHTED_BY_COMPLETED_OBSERVATIONS"


def test_yield_is_weighted_by_reported_basis() -> None:
    document, _ = build_enterprise_contributor_details(
        interpretation=_interpretation(), metric_id="yield"
    )

    assert document["enterprise_value"] == 4.4
    assert document["calculation_method"] == "WEIGHTED_BY_REPORTED_BASIS"


def test_performance_does_not_invent_combined_total() -> None:
    document, warnings = build_enterprise_contributor_details(
        interpretation=_interpretation(), metric_id="performance"
    )

    assert document["enterprise_value"] is None
    assert document["reported_strategy_count"] == 2
    assert any("normalization contract" in warning for warning in warnings)
    assert [item["value"] for item in document["contributors"]] == [8.0, 12.0]


def test_contributors_preserve_status_lifecycle_and_safety_metadata() -> None:
    document, _ = build_enterprise_contributor_details(
        interpretation=_interpretation(), metric_id="realized_pnl"
    )
    swing = next(
        item for item in document["contributors"] if item["strategy_id"] == "SWING-001"
    )

    assert swing["runtime_status"] == "ONLINE"
    assert swing["health_status"] == "HEALTHY"
    assert swing["readiness"] == "READY"
    assert swing["lifecycle_status"] == "ACTIVE"
    assert swing["paper_trade_mode"] is True
    assert swing["reporting_only"] is True


def test_builds_every_approved_details_document() -> None:
    documents, warnings = build_all_enterprise_contributor_details(
        interpretation=_interpretation()
    )

    assert set(documents) == {
        "income",
        "performance",
        "realized_pnl",
        "unrealized_pnl",
        "win_rate",
        "yield",
        "capital_appreciation",
        "watchlist_count",
    }
    assert documents["watchlist_count"]["enterprise_value"] == 12.0
    assert any("normalization contract" in warning for warning in warnings)


def test_unknown_metric_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported enterprise contributor metric"):
        build_enterprise_contributor_details(
            interpretation=_interpretation(), metric_id="unknown"
        )
