from __future__ import annotations

import json
from pathlib import Path

import refresh_enterprise_dashboards as launcher


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _enterprise_inputs(results: Path) -> None:
    _write_json(
        results / "strategy_inventory.json",
        {
            "strategies": [
                {
                    "strategy_id": "dividend",
                    "strategy_name": "Dividend Income Strategy",
                    "strategy_type": "DIVIDEND_ETF",
                    "version": "1.0.0",
                    "runtime_status": "ONLINE",
                    "health_status": "HEALTHY",
                    "readiness": "READY",
                    "output_count": 4,
                    "contract_complete": True,
                    "paper_trade_mode": True,
                    "live_trading_enabled": False,
                    "broker_execution_enabled": False,
                }
            ],
            "summary": {"running_count": 1, "contract_complete_count": 1},
        },
    )
    _write_json(
        results / "enterprise_health.json",
        {
            "enterprise_status": "HEALTHY",
            "strategies": [
                {
                    "strategy_id": "dividend",
                    "classification": "HEALTHY",
                    "health_score": 95,
                }
            ],
            "summary": {"healthy_count": 1, "average_health_score": 95.0},
        },
    )


def test_refresh_writes_exact_portal_artifact_names(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _enterprise_inputs(results)
    _write_json(
        results / "enterprise_dividend_investor_dashboard.json",
        {
            "portfolio_summary": {
                "portfolio_value": 5000,
                "cost_basis": 4500,
                "projected_annual_income": 400,
                "cash_value": 500,
            },
            "holdings": [
                {
                    "symbol": "TEST",
                    "market_value": 4500,
                    "allocation_percent": 90,
                    "annual_income": 400,
                    "sector": "Test",
                }
            ],
            "payment_history": [{"status": "RECEIVED"}],
        },
    )

    summary = launcher.refresh_enterprise_dashboards(results_dir=results)

    executive_path = results / "ai_cio_executive_dashboard.json"
    investor_path = results / "enterprise_investor_dashboard.json"
    assert executive_path.is_file()
    assert investor_path.is_file()
    assert (results / "ai_cio_executive_dashboard.md").is_file()
    assert (results / "enterprise_investor_dashboard.md").is_file()
    assert summary["investor_source"].endswith(
        "enterprise_dividend_investor_dashboard.json"
    )
    provenance = summary["investor_evidence_provenance"]
    assert provenance["source_type"] == "PUBLISHED_ARTIFACT"
    assert provenance["completeness"] == "COMPLETE"
    assert provenance["authoritative"] is True

    executive = json.loads(executive_path.read_text(encoding="utf-8"))
    investor = json.loads(investor_path.read_text(encoding="utf-8"))
    assert executive["enterprise_summary"]["registered_strategy_count"] == 1
    assert investor["investor_summary"]["portfolio_value"] == 5000.0
    assert investor["evidence_provenance"] == provenance
    assert investor["paper_trade_mode"] is True
    assert investor["live_trading_enabled"] is False
    assert investor["broker_execution_enabled"] is False


def test_missing_sources_produce_explicit_partial_artifacts_without_failure(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"

    summary = launcher.refresh_enterprise_dashboards(results_dir=results)

    assert (results / "ai_cio_executive_dashboard.json").is_file()
    assert (results / "enterprise_investor_dashboard.json").is_file()
    assert summary["investor_dashboard_status"] == "PARTIAL"
    assert summary["investor_source"] is None
    provenance = summary["investor_evidence_provenance"]
    assert provenance["source_type"] == "NONE"
    assert provenance["completeness"] == "NONE"
    assert summary["warnings"]
    assert summary["errors"]

    investor = json.loads(
        (results / "enterprise_investor_dashboard.json").read_text(
            encoding="utf-8"
        )
    )
    assert investor["dashboard_status"] == "PARTIAL"
    assert investor["evidence_provenance"]["source_type"] == "NONE"
    assert investor["warnings"]
    assert investor["investor_summary"]["portfolio_value"] == 0.0
    assert investor["reporting_only"] is True


def test_malformed_optional_investor_source_warns_and_falls_back(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"
    _enterprise_inputs(results)
    results.mkdir(parents=True, exist_ok=True)
    (results / "enterprise_dividend_investor_dashboard.json").write_text(
        "{bad", encoding="utf-8"
    )

    summary = launcher.refresh_enterprise_dashboards(results_dir=results)

    assert summary["investor_source"] is None
    assert summary["investor_evidence_provenance"]["source_type"] == "NONE"
    assert summary["investor_dashboard_status"] == "PARTIAL"
    assert any(
        "invalid dashboard source" in warning
        for warning in summary["warnings"]
    )
    assert (results / "enterprise_investor_dashboard.json").is_file()


def test_adapter_reconstruction_is_labeled_and_not_claimed_authoritative(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"
    state = tmp_path / "state"
    _enterprise_inputs(results)
    _write_json(
        state / "paper_cash_account.json",
        {
            "available_cash": 500,
            "allocated_cash": 9500,
            "paper_trade_mode": True,
        },
    )

    summary = launcher.refresh_enterprise_dashboards(
        results_dir=results,
        state_dir=state,
    )

    assert summary["investor_source"] == "enterprise_dashboard_evidence_adapter"
    provenance = summary["investor_evidence_provenance"]
    assert provenance["source_type"] == "ADAPTER_RECONSTRUCTION"
    assert provenance["completeness"] == "PARTIAL"
    assert provenance["authoritative"] is False
    assert provenance["reconstructed"] is True
    assert summary["investor_dashboard_status"] == "PARTIAL"
    assert any(
        "enterprise_dashboard_evidence_adapter" in warning
        for warning in summary["warnings"]
    )


def test_refresh_does_not_touch_cash_or_governance_files(tmp_path: Path) -> None:
    results = tmp_path / "results"
    state = tmp_path / "state"
    cash = state / "paper_cash_account.json"
    approvals = state / "paper_allocation_approvals.jsonl"
    requests = state / "paper_allocation_requests.jsonl"
    _write_json(cash, {"available_cash": 1234.56})
    approvals.write_text("approval-record\n", encoding="utf-8")
    requests.write_text("request-record\n", encoding="utf-8")
    before = {
        cash: cash.read_bytes(),
        approvals: approvals.read_bytes(),
        requests: requests.read_bytes(),
    }

    launcher.refresh_enterprise_dashboards(
        results_dir=results,
        state_dir=state,
    )

    assert {path: path.read_bytes() for path in before} == before


def test_atomic_writer_replaces_target_and_leaves_no_temp_file(
    tmp_path: Path,
) -> None:
    target = tmp_path / "results" / "dashboard.json"
    target.parent.mkdir(parents=True)
    target.write_text("old", encoding="utf-8")

    launcher._atomic_write_json(target, {"status": "new"})

    assert json.loads(target.read_text(encoding="utf-8")) == {
        "status": "new"
    }
    assert not list(target.parent.glob(f".{target.name}.*.tmp"))


def test_main_returns_zero_for_missing_optional_evidence(
    tmp_path: Path,
    capsys,
) -> None:
    code = launcher.main(["--results-dir", str(tmp_path / "results")])

    output = capsys.readouterr().out
    assert code == 0
    assert "Executive dashboard:" in output
    assert "Investor dashboard:" in output
    assert "Investor evidence: NONE / NONE" in output
    assert "WARNING:" in output
