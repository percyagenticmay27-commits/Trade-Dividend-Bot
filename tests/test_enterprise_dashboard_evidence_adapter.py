from __future__ import annotations

import csv
import json
from pathlib import Path

from src.dividend_bot.enterprise_dashboard_evidence_adapter import build_dashboard_evidence
import refresh_enterprise_dashboards as launcher


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _registry() -> dict[str, object]:
    safety = {
        "paper_trade_mode": True,
        "paper_compatible": True,
        "advisory_only": True,
        "reporting_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
        "direct_database_writes": False,
    }
    return {
        "strategy_plugins": [
            {"strategy_id": "dividend", "display_name": "Dividend Income Strategy", "status": "READY", "health": "HEALTHY", **safety},
            {"strategy_id": "SWING-001", "display_name": "Trade Swing Bot", "status": "AVAILABLE", "health": "HEALTHY", **safety},
        ]
    }


def test_adapter_builds_two_strategy_inventory_and_healthy_enterprise(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write_json(results / "enterprise_dividend_service_registry.json", _registry())
    evidence = build_dashboard_evidence(root_dir=tmp_path, results_dir=results, state_dir=tmp_path / "state")
    assert len(evidence["strategy_inventory"]["strategies"]) == 2
    assert evidence["enterprise_health"]["enterprise_status"] == "HEALTHY"
    assert evidence["strategy_inventory"]["summary"]["contract_complete_count"] == 2


def test_adapter_reads_restored_cash_and_portfolio_snapshot(tmp_path: Path) -> None:
    results = tmp_path / "results"
    state = tmp_path / "state"
    _write_json(results / "enterprise_dividend_service_registry.json", _registry())
    _write_json(state / "paper_cash_account.json", {"available_cash": 500, "allocated_cash": 9500})
    _write_csv(results / "portfolio_snapshot.csv", [{"symbol": "TEST", "market_value": 9500, "allocation_percent": 95, "sector": "Test"}])
    evidence = build_dashboard_evidence(root_dir=tmp_path, results_dir=results, state_dir=state)
    summary = evidence["investor_evidence"]["portfolio_summary"]
    assert summary["portfolio_value"] == 10000
    assert summary["cash_value"] == 500
    assert evidence["investor_evidence"]["holdings"][0]["symbol"] == "TEST"


def test_refresh_populates_existing_dashboard_builders(tmp_path: Path) -> None:
    results = tmp_path / "results"
    state = tmp_path / "state"
    _write_json(results / "enterprise_dividend_service_registry.json", _registry())
    _write_json(state / "paper_cash_account.json", {"available_cash": 500, "allocated_cash": 9500})
    _write_csv(results / "portfolio_snapshot.csv", [{"symbol": "TEST", "market_value": 9500, "allocation_percent": 95, "sector": "Test"}])
    summary = launcher.refresh_enterprise_dashboards(root_dir=tmp_path, results_dir=results, state_dir=state)
    executive = json.loads((results / "ai_cio_executive_dashboard.json").read_text(encoding="utf-8"))
    investor = json.loads((results / "enterprise_investor_dashboard.json").read_text(encoding="utf-8"))
    assert summary["registered_strategy_count"] == 2
    assert executive["enterprise_summary"]["enterprise_status"] == "HEALTHY"
    assert executive["enterprise_summary"]["registered_strategy_count"] == 2
    assert investor["dashboard_status"] == "PARTIAL"
    assert investor["investor_summary"]["portfolio_value"] == 10000
    assert investor["investor_summary"]["cash_or_reserve_value"] == 500
    provenance = investor["evidence_provenance"]
    assert provenance["source_type"] == "ADAPTER_RECONSTRUCTION"
    assert provenance["authoritative"] is False
    assert provenance["reconstructed"] is True


def test_adapter_is_read_only_for_state_files(tmp_path: Path) -> None:
    results = tmp_path / "results"
    state = tmp_path / "state"
    _write_json(results / "enterprise_dividend_service_registry.json", _registry())
    cash = state / "paper_cash_account.json"
    approvals = state / "paper_allocation_approvals.json"
    _write_json(cash, {"available_cash": 500})
    _write_json(approvals, {"records": ["unchanged"]})
    before = {cash: cash.read_bytes(), approvals: approvals.read_bytes()}
    launcher.refresh_enterprise_dashboards(root_dir=tmp_path, results_dir=results, state_dir=state)
    assert {path: path.read_bytes() for path in before} == before


def test_unsafe_registry_entry_is_not_reported_healthy(tmp_path: Path) -> None:
    results = tmp_path / "results"
    registry = _registry()
    registry["strategy_plugins"][1]["live_trading_enabled"] = True
    _write_json(results / "enterprise_dividend_service_registry.json", registry)
    evidence = build_dashboard_evidence(root_dir=tmp_path, results_dir=results, state_dir=tmp_path / "state")
    assert evidence["enterprise_health"]["enterprise_status"] == "CRITICAL"
    assert evidence["strategy_inventory"]["summary"]["contract_complete_count"] == 1


def test_adapter_prefers_canonical_payment_json_without_legacy_missing_warnings(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"
    state = tmp_path / "state"
    _write_json(results / "enterprise_dividend_service_registry.json", _registry())
    _write_json(state / "paper_cash_account.json", {"available_cash": 500})
    _write_json(
        results / "payment_history.json",
        {
            "evidence_status": "AVAILABLE",
            "records": [
                {
                    "date": "2026-08-10",
                    "symbol": "AMDW",
                    "event_type": "DISTRIBUTION_RECEIVED",
                    "amount": 2.50,
                }
            ],
        },
    )
    _write_json(
        results / "upcoming_payments.json",
        {
            "evidence_status": "NOT_REPORTED",
            "records": [],
            "empty_state_reason": "No authoritative upcoming date is currently reported.",
        },
    )

    evidence = build_dashboard_evidence(
        root_dir=tmp_path,
        results_dir=results,
        state_dir=state,
    )

    assert evidence["investor_evidence"]["payment_history"][0]["symbol"] == "AMDW"
    assert evidence["investor_evidence"]["upcoming_payments"] == []
    assert not any("paper_dividend_history.csv" in warning for warning in evidence["warnings"])
    assert not any("upcoming_payments.csv" in warning for warning in evidence["warnings"])
