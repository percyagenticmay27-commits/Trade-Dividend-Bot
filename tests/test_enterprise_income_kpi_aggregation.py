from __future__ import annotations

from pathlib import Path

import src.dividend_bot.enterprise_strategy_kpi_adapter as adapter


def _dividend_plugin() -> dict:
    return {
        "strategy_id": "DIVIDEND-001",
        "display_name": "Dividend Income Strategy",
        "strategy_type": "DIVIDEND",
        "lifecycle_status": "PRODUCTION",
        "runtime_status": "ONLINE",
        "health_status": "HEALTHY",
        "readiness": "READY",
        "paper_trade_mode": True,
        "paper_compatible": True,
        "advisory_only": True,
        "reporting_only": True,
        "enabled": True,
        "capabilities": ["income"],
        "dashboard_artifacts": [],
    }


def test_dividend_dashboard_income_fields_reach_enterprise_kpi_row(
    tmp_path: Path, monkeypatch,
) -> None:
    dashboard_evidence = {
        "evidence_sources": ["market_data_snapshot.json", "paper_trade_log.csv"],
        "portfolio_value": 468.16,
        "position_count": 7,
        "holdings": [
            {"symbol": "AVGW", "annual_income": 23.14},
            {"symbol": "AVGX", "annual_income": 0.20},
            {"symbol": "NVDW", "annual_income": 19.51},
            {"symbol": "NVDX", "annual_income": 0.40},
            {"symbol": "PLTU", "annual_income": 5.06},
            {"symbol": "PLTW", "annual_income": 29.16},
            {"symbol": "SGOV", "annual_income": None, "position_status": "PARKED"},
        ],
        "projected_annual_income": 77.47,
        "income": 2.50,
        "gross_distribution_income": 3.00,
        "income_adjustments": -0.50,
        "net_income_received": 2.50,
        "realized_income_event_count": 2,
        "positive_income_event_count": 1,
        "negative_income_event_count": 1,
        "income_accounting_method": "GROSS_DISTRIBUTIONS_PLUS_ADJUSTMENTS_EQUALS_NET",
        "income_evidence_source": "paper_trade_log.csv",
        "income_events": [
            {"event_type": "DIVIDEND_RECEIVED", "amount": 3.00},
            {"event_type": "DIVIDEND_REVERSAL", "amount": -0.50},
        ],
        "watchlist": [],
        "alerts": [],
        "risk_flags": [],
        "performance_detail": {},
    }

    monkeypatch.setattr(
        adapter,
        "_append_host_dividend_evidence",
        lambda **_: {"watchlist_count": 0, "opportunity_quality": None, "win_rate_percent": None},
    )
    monkeypatch.setattr(
        adapter,
        "_host_dividend_dashboard_evidence",
        lambda **_: dashboard_evidence,
    )

    rows, warnings = adapter.build_strategy_kpis(
        registry={"strategy_plugins": [_dividend_plugin()]},
        strategy_allocations={"DIVIDEND-001": 5000.0},
        root_dir=tmp_path,
    )

    assert warnings == []
    assert len(rows) == 1
    row = rows[0]
    assert row["projected_annual_income"] == 77.47
    assert row["gross_distribution_income"] == 3.00
    assert row["income_adjustments"] == -0.50
    assert row["net_income_received"] == 2.50
    assert row["realized_income_event_count"] == 2
    assert row["positive_income_event_count"] == 1
    assert row["negative_income_event_count"] == 1
    assert row["income_accounting_method"] == "GROSS_DISTRIBUTIONS_PLUS_ADJUSTMENTS_EQUALS_NET"
    assert row["income_evidence_source"] == "paper_trade_log.csv"
    assert row["income"] == 2.50


def test_missing_projected_income_is_not_fabricated(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        adapter,
        "_append_host_dividend_evidence",
        lambda **_: {"watchlist_count": 0, "opportunity_quality": None, "win_rate_percent": None},
    )
    monkeypatch.setattr(
        adapter,
        "_host_dividend_dashboard_evidence",
        lambda **_: {"evidence_sources": ["paper_state.json"], "holdings": []},
    )

    rows, warnings = adapter.build_strategy_kpis(
        registry={"strategy_plugins": [_dividend_plugin()]},
        strategy_allocations={"DIVIDEND-001": 5000.0},
        root_dir=tmp_path,
    )

    assert warnings == []
    row = rows[0]
    assert row["projected_annual_income"] is None
    assert row["gross_distribution_income"] is None
    assert row["income_adjustments"] is None
    assert row["net_income_received"] is None
