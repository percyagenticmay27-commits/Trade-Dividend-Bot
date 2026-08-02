from __future__ import annotations

import json
from pathlib import Path

import refresh_enterprise_dashboards as launcher


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _safe_plugin(
    strategy_id: str,
    artifact_path: Path | None = None,
) -> dict[str, object]:
    plugin: dict[str, object] = {
        "strategy_id": strategy_id,
        "display_name": strategy_id,
        "plugin_contract_version": "2.0",
        "paper_trade_mode": True,
        "paper_compatible": True,
        "advisory_only": True,
        "reporting_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
        "governance_review_required": True,
        "direct_database_writes": False,
        "capabilities": ["executive_dashboard"],
        "dashboard_artifacts": [],
    }
    if artifact_path is not None:
        plugin["dashboard_artifacts"] = [
            {
                "artifact_id": f"{strategy_id.lower()}-executive",
                "artifact_type": "EXECUTIVE_DASHBOARD",
                "path": str(artifact_path),
                "format": "JSON",
                "scope": "STRATEGY",
                "authoritative": True,
                "required": False,
            }
        ]
    return plugin


def _host_inputs(results: Path) -> None:
    _write_json(
        results / "strategy_inventory.json",
        {
            "strategies": [],
            "summary": {"running_count": 0, "contract_complete_count": 0},
        },
    )
    _write_json(
        results / "enterprise_health.json",
        {
            "enterprise_status": "HEALTHY",
            "strategies": [],
            "summary": {"healthy_count": 0, "average_health_score": 0.0},
        },
    )


def test_refresh_publishes_registry_strategy_evidence_to_both_dashboards(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"
    dividend_artifact = tmp_path / "dividend.json"
    swing_artifact = tmp_path / "swing.json"
    _host_inputs(results)
    _write_json(dividend_artifact, {"portfolio_value": 1000})
    _write_json(swing_artifact, {"portfolio_value": 500})
    _write_json(
        results / "enterprise_dividend_service_registry.json",
        {
            "registry_contract_version": "2.0",
            "strategy_plugins": [
                _safe_plugin("DIVIDEND-001", dividend_artifact),
                _safe_plugin("SWING-001", swing_artifact),
            ],
        },
    )

    summary = launcher.refresh_enterprise_dashboards(
        root_dir=tmp_path,
        results_dir=results,
        state_dir=tmp_path / "state",
    )

    evidence_path = Path(summary["paths"]["registry_strategy_evidence"])
    assert evidence_path.is_file()
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["plugin_evidence_source"] == "REGISTRY_V2_DECLARED_ARTIFACTS"
    assert evidence["summary"]["strategy_count"] == 2
    assert evidence["summary"]["available_count"] == 2
    assert [row["strategy_id"] for row in evidence["strategies"]] == [
        "DIVIDEND-001",
        "SWING-001",
    ]

    executive = json.loads(
        Path(summary["paths"]["executive_json"]).read_text(encoding="utf-8")
    )
    investor = json.loads(
        Path(summary["paths"]["investor_json"]).read_text(encoding="utf-8")
    )
    for dashboard in (executive, investor):
        assert dashboard["dashboard_evidence_contract_version"] == "2.0"
        assert dashboard["plugin_evidence_source"] == "REGISTRY_V2_DECLARED_ARTIFACTS"
        assert dashboard["registry_declared_evidence_summary"]["strategy_count"] == 2
        assert len(dashboard["registry_declared_strategy_evidence"]) == 2


def test_optional_missing_plugin_artifact_remains_registry_only(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"
    _host_inputs(results)
    _write_json(
        results / "enterprise_dividend_service_registry.json",
        {
            "registry_contract_version": "2.0",
            "strategy_plugins": [
                _safe_plugin("SWING-001", tmp_path / "missing.json"),
            ],
        },
    )

    summary = launcher.refresh_enterprise_dashboards(
        root_dir=tmp_path,
        results_dir=results,
        state_dir=tmp_path / "state",
    )

    evidence = json.loads(
        Path(summary["paths"]["registry_strategy_evidence"]).read_text(
            encoding="utf-8"
        )
    )
    assert evidence["summary"]["registry_only_count"] == 1
    assert evidence["strategies"][0]["strategy_id"] == "SWING-001"
    assert evidence["strategies"][0]["evidence_status"] == "REGISTRY_ONLY"
    assert evidence["required_plugin_evidence_failures"] == []


def test_refresh_reads_but_does_not_modify_declared_artifact(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"
    artifact = tmp_path / "swing.json"
    _host_inputs(results)
    _write_json(artifact, {"portfolio_value": 500, "watchlist_count": 12})
    _write_json(
        results / "enterprise_dividend_service_registry.json",
        {
            "registry_contract_version": "2.0",
            "strategy_plugins": [_safe_plugin("SWING-001", artifact)],
        },
    )
    before = artifact.read_bytes()

    launcher.refresh_enterprise_dashboards(
        root_dir=tmp_path,
        results_dir=results,
        state_dir=tmp_path / "state",
    )

    assert artifact.read_bytes() == before
