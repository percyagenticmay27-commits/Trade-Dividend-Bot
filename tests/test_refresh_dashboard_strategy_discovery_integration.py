from __future__ import annotations

import json
from pathlib import Path

import refresh_enterprise_dashboards as launcher


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _registry() -> dict[str, object]:
    return {
        "strategy_plugins": [
            {
                "strategy_id": "SWING-001",
                "display_name": "Trade Swing Bot",
                "strategy_type": "SWING",
                "lifecycle_status": "ACTIVE",
                "runtime_status": "ONLINE",
                "health_status": "HEALTHY",
                "readiness": "READY",
                "enabled": True,
                "paper_trade_mode": True,
                "paper_compatible": True,
                "advisory_only": True,
                "reporting_only": True,
            },
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Income Strategy",
                "strategy_type": "DIVIDEND_ETF",
                "lifecycle_status": "PRODUCTION",
                "runtime_status": "ONLINE",
                "health_status": "HEALTHY",
                "readiness": "READY",
                "enabled": True,
                "paper_trade_mode": True,
                "paper_compatible": True,
                "advisory_only": False,
                "reporting_only": True,
            },
        ]
    }


def test_refresh_publishes_identical_discovery_to_all_consumers(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"
    state = tmp_path / "state"
    _write_json(results / "enterprise_dividend_service_registry.json", _registry())
    _write_json(
        results / "enterprise_dividend_investor_dashboard.json",
        {
            "portfolio_summary": {
                "portfolio_value": 5000,
                "cost_basis": 4500,
                "projected_annual_income": 400,
                "cash_value": 500,
            },
            "holdings": [],
            "payment_history": [],
        },
    )
    _write_json(
        state / "paper_cash_account.json",
        {
            "available_cash": 500,
            "allocated_cash": 9500,
            "strategy_allocations": {
                "DIVIDEND-001": 5000,
                "SWING-001": 4500,
            },
            "paper_trade_mode": True,
        },
    )

    summary = launcher.refresh_enterprise_dashboards(
        root_dir=tmp_path,
        results_dir="results",
        state_dir="state",
    )

    executive = json.loads(
        (results / "ai_cio_executive_dashboard.json").read_text(encoding="utf-8")
    )
    investor = json.loads(
        (results / "enterprise_investor_dashboard.json").read_text(encoding="utf-8")
    )
    kpis = json.loads(
        (results / "enterprise_strategy_kpis.json").read_text(encoding="utf-8")
    )

    expected = {
        "registered_strategy_count": 2,
        "enabled_strategy_count": 2,
        "paper_compatible_strategy_count": 2,
        "strategy_ids": ["DIVIDEND-001", "SWING-001"],
        "paper_trade_mode": True,
        "reporting_only": True,
    }
    assert executive["strategy_discovery"]["summary"] == expected
    assert investor["strategy_discovery"]["summary"] == expected
    assert kpis["strategy_discovery"]["summary"] == expected
    assert summary["strategy_discovery_summary"] == expected
    assert summary["registered_strategy_count"] == 2

    assert executive["strategy_discovery"] == investor["strategy_discovery"]
    assert executive["strategy_discovery"] == kpis["strategy_discovery"]
    assert executive["strategy_discovery"]["read_only"] is True
    assert investor["investor_summary"]["portfolio_value"] == 5000.0
    assert investor["paper_trade_mode"] is True
    assert investor["live_trading_enabled"] is False
    assert investor["broker_execution_enabled"] is False


def test_refresh_missing_registry_publishes_safe_empty_discovery(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"

    summary = launcher.refresh_enterprise_dashboards(results_dir=results)

    executive = json.loads(
        (results / "ai_cio_executive_dashboard.json").read_text(encoding="utf-8")
    )
    investor = json.loads(
        (results / "enterprise_investor_dashboard.json").read_text(encoding="utf-8")
    )
    kpis = json.loads(
        (results / "enterprise_strategy_kpis.json").read_text(encoding="utf-8")
    )

    assert summary["registered_strategy_count"] == 0
    assert summary["strategy_discovery_summary"]["strategy_ids"] == []
    assert executive["strategy_discovery"]["strategies"] == []
    assert investor["strategy_discovery"]["strategies"] == []
    assert kpis["strategy_discovery"]["strategies"] == []
    assert any(
        "does not contain strategy_plugins" in warning
        for warning in summary["warnings"]
    )
