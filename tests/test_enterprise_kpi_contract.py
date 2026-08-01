from __future__ import annotations

import pytest

from src.dividend_bot.enterprise_kpi_contract import (
    normalize_metric,
    normalize_strategy_kpi_contract,
)


def test_numeric_zero_remains_a_reported_zero() -> None:
    metric = normalize_metric(0, unit="CURRENCY")

    assert metric["value"] == 0
    assert metric["status"] == "REPORTED"


def test_not_applicable_does_not_become_zero() -> None:
    metric = normalize_metric(
        {
            "value": 0,
            "status": "NOT_APPLICABLE",
            "unit": "PERCENT",
            "reason": "Futures strategy does not generate portfolio yield.",
        }
    )

    assert metric["value"] is None
    assert metric["status"] == "NOT_APPLICABLE"


def test_missing_conditional_metric_can_be_declared_not_applicable() -> None:
    row = normalize_strategy_kpi_contract(
        {"strategy_id": "FUTURES-001", "performance_percent": 8.4},
        applicability={
            "yield_percent": "NOT_APPLICABLE",
            "capital_appreciation": "NOT_APPLICABLE",
        },
    )

    assert row["metrics"]["performance_percent"]["value"] == 8.4
    assert row["metrics"]["performance_percent"]["status"] == "REPORTED"
    assert row["metrics"]["yield_percent"]["value"] is None
    assert row["metrics"]["yield_percent"]["status"] == "NOT_APPLICABLE"
    assert row["metrics"]["capital_appreciation"]["status"] == "NOT_APPLICABLE"


def test_missing_applicable_metric_is_not_reported() -> None:
    row = normalize_strategy_kpi_contract({"strategy_id": "SWING-001"})

    assert row["metrics"]["opportunity_quality"]["value"] is None
    assert row["metrics"]["opportunity_quality"]["status"] == "NOT_REPORTED"


def test_reported_status_requires_numeric_value() -> None:
    with pytest.raises(ValueError, match="requires a numeric value"):
        normalize_metric({"value": None, "status": "REPORTED"})


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        normalize_metric({"value": None, "status": "UNKNOWN_STATE"})


def test_contract_safety_metadata_is_locked() -> None:
    row = normalize_strategy_kpi_contract({"strategy_id": "OPTIONS-001"})

    assert row["enterprise_kpi_contract_version"] == "1.0"
    assert row["paper_trade_mode"] is True
    assert row["live_trading_enabled"] is False
    assert row["broker_execution_enabled"] is False
    assert row["capital_movement_enabled"] is False
    assert row["reporting_only"] is True
    assert row["read_only"] is True
