import json
from pathlib import Path

import pytest

from src.dividend_bot.enterprise_strategy_plugin_contract import (
    PLUGIN_CONTRACT_VERSION,
    build_plugin_contract_metadata,
    normalize_dashboard_artifacts,
    normalize_plugin_capabilities,
)
from src.dividend_bot.external_strategy_registration import (
    normalize_external_strategy_registration,
)


def _safe_registration(**overrides):
    payload = {
        "strategy_id": "SWING-001",
        "display_name": "Trade Swing Bot",
        "plugin_type": "STRATEGY_PLUGIN",
        "status": "READY",
        "enabled": True,
        "version": "1.4.0",
        "health": "HEALTHY",
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
    }
    payload.update(overrides)
    return payload


def test_legacy_registration_remains_valid_with_empty_v2_metadata():
    plugin = normalize_external_strategy_registration(_safe_registration())
    assert plugin["plugin_contract_version"] == PLUGIN_CONTRACT_VERSION
    assert plugin["capabilities"] == []
    assert plugin["dashboard_artifacts"] == []
    assert plugin["capability_count"] == 0
    assert plugin["published_artifact_count"] == 0


def test_v2_registration_normalizes_capabilities_and_artifacts():
    plugin = normalize_external_strategy_registration(_safe_registration(
        capabilities=[
            "watchlist",
            {"capability_id": "portfolio", "display_name": "Portfolio Reporting"},
            "opportunity_quality",
        ],
        dashboard_artifacts=[
            {
                "artifact_id": "watchlist",
                "type": "watchlist",
                "path": "/srv/swing/results/watchlist_report.json",
                "schema_version": "1.0",
            },
            {
                "report_id": "portfolio",
                "report_path": "/srv/swing/results/portfolio_snapshot.csv",
                "authoritative": True,
            },
        ],
    ))
    assert [item["capability_id"] for item in plugin["capabilities"]] == [
        "opportunity_quality", "portfolio", "watchlist"
    ]
    assert [item["artifact_id"] for item in plugin["dashboard_artifacts"]] == [
        "portfolio", "watchlist"
    ]
    assert plugin["dashboard_artifacts"][0]["format"] == "CSV"
    assert plugin["dashboard_artifacts"][1]["format"] == "JSON"
    assert all(item["read_only"] is True for item in plugin["dashboard_artifacts"])


def test_capabilities_are_deterministic_and_duplicate_ids_are_rejected():
    assert [item["capability_id"] for item in normalize_plugin_capabilities(["zeta", "alpha"])] == [
        "alpha", "zeta"
    ]
    with pytest.raises(ValueError, match="duplicate capability_id"):
        normalize_plugin_capabilities(["portfolio", {"id": "portfolio"}])


def test_artifacts_are_deterministic_and_duplicate_ids_are_rejected():
    artifacts = normalize_dashboard_artifacts([
        {"artifact_id": "zeta", "path": "results/zeta.json"},
        {"artifact_id": "alpha", "path": "results/alpha.json"},
    ])
    assert [item["artifact_id"] for item in artifacts] == ["alpha", "zeta"]
    with pytest.raises(ValueError, match="duplicate artifact_id"):
        normalize_dashboard_artifacts([
            {"artifact_id": "portfolio", "path": "results/a.json"},
            {"artifact_id": "portfolio", "path": "results/b.json"},
        ])


@pytest.mark.parametrize("artifact", [
    {"artifact_id": "missing-path"},
    {"artifact_id": "bad-format", "path": "results/report.exe"},
    {"artifact_id": "bad-scope", "path": "results/report.json", "scope": "BROKER"},
])
def test_invalid_artifact_contract_is_rejected(artifact):
    with pytest.raises(ValueError):
        normalize_dashboard_artifacts([artifact])


def test_write_capabilities_are_rejected():
    with pytest.raises(ValueError, match="must be read-only"):
        normalize_plugin_capabilities([
            {"capability_id": "capital_movement", "read_only": False}
        ])


def test_artifact_without_matching_capability_produces_contract_warning():
    metadata = build_plugin_contract_metadata({
        "capabilities": ["portfolio"],
        "dashboard_artifacts": [
            {"artifact_id": "watchlist", "type": "watchlist", "path": "results/watchlist.json"}
        ],
    })
    assert metadata["contract_warnings"] == [
        "Artifact type has no matching enabled capability: watchlist"
    ]


def test_contract_module_contains_no_plugin_production_imports():
    source = Path("src/dividend_bot/enterprise_strategy_plugin_contract.py").read_text(encoding="utf-8")
    assert "swing_trade_bot" not in source
    assert "Trade-Swing-Bot" not in source
    assert "subprocess" not in source
    assert "os.system" not in source
