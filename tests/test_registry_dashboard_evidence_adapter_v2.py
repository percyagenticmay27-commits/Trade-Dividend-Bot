from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.registry_dashboard_evidence_adapter_v2 import (
    build_registry_dashboard_evidence_v2,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _safe_plugin(
    strategy_id: str,
    artifact_path: Path | None = None,
    *,
    required: bool = False,
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
        "direct_database_writes": False,
        "dashboard_artifacts": [],
    }
    if artifact_path is not None:
        plugin["dashboard_artifacts"] = [
            {
                "artifact_id": f"{strategy_id.lower()}-dashboard",
                "artifact_type": "EXECUTIVE_DASHBOARD",
                "path": str(artifact_path),
                "format": "JSON",
                "scope": "STRATEGY",
                "authoritative": True,
                "required": required,
            }
        ]
    return plugin


def test_v2_adapter_loads_each_registered_strategy_artifact(tmp_path: Path) -> None:
    results = tmp_path / "results"
    dividend = tmp_path / "dividend.json"
    swing = tmp_path / "swing.json"
    _write_json(dividend, {"portfolio_value": 1000})
    _write_json(swing, {"portfolio_value": 500})
    _write_json(
        results / "enterprise_dividend_service_registry.json",
        {"strategy_plugins": [_safe_plugin("DIVIDEND-001", dividend), _safe_plugin("SWING-001", swing)]},
    )

    evidence = build_registry_dashboard_evidence_v2(
        root_dir=tmp_path,
        results_dir=results,
        state_dir=tmp_path / "state",
    )

    rows = evidence["registry_declared_strategy_evidence"]
    assert [row["strategy_id"] for row in rows] == ["DIVIDEND-001", "SWING-001"]
    assert all(row["evidence_status"] == "AVAILABLE" for row in rows)
    assert evidence["registry_declared_evidence_summary"]["available_artifact_count"] == 2
    assert evidence["plugin_evidence_source"] == "REGISTRY_V2_DECLARED_ARTIFACTS"


def test_optional_missing_artifact_keeps_strategy_visible(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write_json(
        results / "enterprise_dividend_service_registry.json",
        {"strategy_plugins": [_safe_plugin("SWING-001", tmp_path / "missing.json")]},
    )
    evidence = build_registry_dashboard_evidence_v2(root_dir=tmp_path, results_dir=results)
    strategy = evidence["registry_declared_strategy_evidence"][0]
    assert strategy["strategy_id"] == "SWING-001"
    assert strategy["evidence_status"] == "REGISTRY_ONLY"
    assert evidence["required_plugin_evidence_failures"] == []


def test_required_missing_artifact_is_isolated_and_reported(tmp_path: Path) -> None:
    results = tmp_path / "results"
    good = tmp_path / "good.json"
    _write_json(good, {"status": "ok"})
    _write_json(
        results / "enterprise_dividend_service_registry.json",
        {
            "strategy_plugins": [
                _safe_plugin("DIVIDEND-001", good),
                _safe_plugin("SWING-001", tmp_path / "missing.json", required=True),
            ]
        },
    )
    evidence = build_registry_dashboard_evidence_v2(root_dir=tmp_path, results_dir=results)
    by_id = {row["strategy_id"]: row for row in evidence["registry_declared_strategy_evidence"]}
    assert by_id["DIVIDEND-001"]["evidence_status"] == "AVAILABLE"
    assert by_id["SWING-001"]["evidence_status"] == "REQUIRED_EVIDENCE_MISSING"
    assert evidence["required_plugin_evidence_failures"] == ["SWING-001"]


def test_host_state_fallback_is_explicitly_non_authoritative_for_plugins(tmp_path: Path) -> None:
    results = tmp_path / "results"
    state = tmp_path / "state"
    _write_json(
        results / "enterprise_dividend_service_registry.json",
        {"strategy_plugins": [_safe_plugin("DIVIDEND-001")]},
    )
    _write_json(state / "paper_cash_account.json", {"available_cash": 500})
    evidence = build_registry_dashboard_evidence_v2(
        root_dir=tmp_path,
        results_dir=results,
        state_dir=state,
    )
    assert evidence["evidence_policy"]["host_state_fallback_retained"] is True
    assert evidence["evidence_policy"]["fallback_is_authoritative_plugin_evidence"] is False
    assert evidence["evidence_policy"]["missing_optional_artifacts_fabricated"] is False


def test_missing_registry_does_not_crash_existing_host_adapter(tmp_path: Path) -> None:
    evidence = build_registry_dashboard_evidence_v2(root_dir=tmp_path)
    assert evidence["plugin_evidence_source"] == "NONE"
    assert evidence["registry_declared_strategy_evidence"] == []
    assert evidence["dashboard_evidence_contract_version"] == "2.0"


def test_adapter_is_read_only_for_declared_artifacts_and_state(tmp_path: Path) -> None:
    results = tmp_path / "results"
    state = tmp_path / "state"
    artifact = tmp_path / "swing.json"
    cash = state / "paper_cash_account.json"
    _write_json(artifact, {"portfolio_value": 500})
    _write_json(cash, {"available_cash": 500})
    _write_json(
        results / "enterprise_dividend_service_registry.json",
        {"strategy_plugins": [_safe_plugin("SWING-001", artifact)]},
    )
    before = {artifact: artifact.read_bytes(), cash: cash.read_bytes()}
    build_registry_dashboard_evidence_v2(root_dir=tmp_path, results_dir=results, state_dir=state)
    assert {path: path.read_bytes() for path in before} == before
