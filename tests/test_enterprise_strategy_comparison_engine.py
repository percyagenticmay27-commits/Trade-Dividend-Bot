from __future__ import annotations

from copy import deepcopy

from src.dividend_bot.enterprise_strategy_comparison_engine import (
    build_enterprise_strategy_comparison,
)


def _interpretation() -> dict[str, object]:
    return {
        "source": "ENTERPRISE_AI_CIO_MULTI_STRATEGY_INTERPRETATION",
        "strategies": [
            {
                "strategy_id": "SWING-001",
                "display_name": "Swing Strategy",
                "runtime_status": "ONLINE",
                "health_status": "HEALTHY",
                "readiness": "READY",
                "evidence_status": "AVAILABLE",
                "allocated_capital": 4500.0,
                "portfolio_value": 4700.0,
                "realized_gain": 300.0,
                "unrealized_gain": 200.0,
                "income": 100.0,
                "watchlist_count": 8,
                "position_count": 3,
                "opportunity_quality": 82.0,
                "win_rate_percent": 62.5,
            },
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Strategy",
                "runtime_status": "ONLINE",
                "health_status": "HEALTHY",
                "readiness": "READY",
                "evidence_status": "AVAILABLE",
                "allocated_capital": 5000.0,
                "portfolio_value": 5200.0,
                "realized_gain": 150.0,
                "unrealized_gain": 200.0,
                "income": 900.0,
                "watchlist_count": 5,
                "position_count": 6,
                "opportunity_quality": 75.0,
                "win_rate_percent": 70.0,
            },
        ],
    }


def test_builds_deterministic_comparisons_for_dividend_and_swing() -> None:
    document, warnings = build_enterprise_strategy_comparison(
        interpretation=_interpretation()
    )

    assert warnings == []
    assert document["strategy_ids"] == ["DIVIDEND-001", "SWING-001"]
    income = document["metric_comparisons"]["income"]
    assert income["enterprise_total"] == 1000.0
    assert income["leader"]["strategy_id"] == "DIVIDEND-001"
    assert income["contributors"][0]["share_of_reported_total_percent"] == 90.0
    assert income["complete"] is True


def test_compares_performance_style_metrics_without_recommendations() -> None:
    document, _ = build_enterprise_strategy_comparison(
        interpretation=_interpretation()
    )

    quality = document["metric_comparisons"]["opportunity_quality"]
    assert quality["leader"]["strategy_id"] == "SWING-001"
    assert quality["leader"]["value"] == 82.0
    assert document["comparison_policy"]["recommendations_generated"] is False
    assert document["comparison_policy"]["allocation_changes_generated"] is False


def test_pairwise_difference_preserves_direction() -> None:
    document, _ = build_enterprise_strategy_comparison(
        interpretation=_interpretation()
    )

    difference = document["pairwise_differences"]["portfolio_value"][0]
    assert difference["left_strategy_id"] == "DIVIDEND-001"
    assert difference["right_strategy_id"] == "SWING-001"
    assert difference["difference"] == 500.0
    assert difference["absolute_difference"] == 500.0


def test_missing_evidence_is_not_converted_to_zero() -> None:
    interpretation = _interpretation()
    interpretation["strategies"][0]["income"] = None

    document, warnings = build_enterprise_strategy_comparison(
        interpretation=interpretation
    )

    income = document["metric_comparisons"]["income"]
    assert income["enterprise_total"] == 900.0
    assert income["reported_strategy_count"] == 1
    assert income["registered_strategy_count"] == 2
    assert income["complete"] is False
    assert income["missing_strategy_ids"] == ["SWING-001"]
    assert any("income" in warning for warning in warnings)


def test_status_comparisons_preserve_each_strategy() -> None:
    document, _ = build_enterprise_strategy_comparison(
        interpretation=_interpretation()
    )

    health = document["status_comparisons"]["health_status"]
    assert health["counts"] == {"HEALTHY": 2}
    assert [item["strategy_id"] for item in health["strategies"]] == [
        "DIVIDEND-001",
        "SWING-001",
    ]


def test_empty_interpretation_returns_safe_read_only_document() -> None:
    document, warnings = build_enterprise_strategy_comparison(
        interpretation={}
    )

    assert document["registered_strategy_count"] == 0
    assert document["strategy_ids"] == []
    assert document["paper_trade_mode"] is True
    assert document["live_trading_enabled"] is False
    assert document["broker_execution_enabled"] is False
    assert document["capital_movement_enabled"] is False
    assert document["reporting_only"] is True
    assert document["read_only"] is True
    assert warnings


def test_duplicate_and_malformed_rows_are_ignored_with_warnings() -> None:
    interpretation = _interpretation()
    interpretation["strategies"].append(
        {"strategy_id": "SWING-001", "income": 999999.0}
    )
    interpretation["strategies"].append("bad-row")

    document, warnings = build_enterprise_strategy_comparison(
        interpretation=interpretation
    )

    assert document["registered_strategy_count"] == 2
    assert document["metric_comparisons"]["income"]["enterprise_total"] == 1000.0
    assert "Duplicate interpreted strategy ignored: SWING-001" in warnings
    assert "Malformed interpreted strategy row ignored." in warnings


def test_does_not_mutate_interpretation_input() -> None:
    interpretation = _interpretation()
    before = deepcopy(interpretation)

    build_enterprise_strategy_comparison(interpretation=interpretation)

    assert interpretation == before
