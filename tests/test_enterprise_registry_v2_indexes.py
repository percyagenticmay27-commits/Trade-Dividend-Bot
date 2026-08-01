import json
from pathlib import Path

from src.dividend_bot.enterprise_dividend_service_registry_event_wiring import (
    REGISTRY_CONTRACT_VERSION,
    build_service_registry,
    default_dividend_strategy_plugins,
    render_service_registry_markdown,
)

FIXED_TIME = "2026-07-31T21:30:00Z"


def _write_swing_registration(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "strategy_id": "SWING-001",
                "display_name": "Trade Swing Bot",
                "plugin_type": "STRATEGY",
                "enabled": True,
                "status": "AVAILABLE",
                "health": "HEALTHY",
                "version": "1.4",
                "paper_trade_mode": True,
                "paper_compatible": True,
                "advisory_only": True,
                "reporting_only": True,
                "governance_review_required": True,
                "live_trading_enabled": False,
                "broker_execution_enabled": False,
                "capital_movement_enabled": False,
                "automatic_activation_allowed": False,
                "direct_database_writes": False,
                "capabilities": [
                    "executive_dashboard",
                    "opportunity_quality",
                    "watchlist",
                ],
                "dashboard_artifacts": [
                    {
                        "artifact_id": "executive_dashboard",
                        "artifact_type": "executive_dashboard",
                        "path": "/home/tradebot/Trade-Swing-Bot/main/results/executive_dashboard.json",
                        "format": "JSON",
                        "scope": "STRATEGY",
                        "authoritative": True,
                        "required": False,
                    },
                    {
                        "artifact_id": "opportunity_quality",
                        "artifact_type": "opportunity_quality",
                        "path": "/home/tradebot/Trade-Swing-Bot/main/results/opportunity_quality.json",
                        "format": "JSON",
                        "scope": "STRATEGY",
                        "authoritative": True,
                        "required": False,
                    },
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_config(path: Path, registration_path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "registrations": [
                    {
                        "strategy_id": "SWING-001",
                        "registration_path": str(registration_path),
                        "required": False,
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_canonical_dividend_plugin_publishes_v2_metadata():
    plugin = default_dividend_strategy_plugins()[0]
    assert plugin["plugin_contract_version"] == REGISTRY_CONTRACT_VERSION
    assert plugin["capability_count"] == 7
    assert plugin["published_artifact_count"] == 4
    assert plugin["paper_trade_mode"] is True
    assert plugin["broker_execution_enabled"] is False


def test_registry_summary_counts_capabilities_and_artifacts():
    registry = build_service_registry(generated_at_utc=FIXED_TIME)
    assert registry["registry_contract_version"] == REGISTRY_CONTRACT_VERSION
    assert registry["summary"]["strategy_plugin_count"] == 1
    assert registry["summary"]["capability_count"] == 7
    assert registry["summary"]["published_artifact_count"] == 4
    assert registry["summary"]["strategy_with_capabilities_count"] == 1
    assert registry["summary"]["strategy_with_artifacts_count"] == 1


def test_registry_indexes_are_populated_for_dividend():
    registry = build_service_registry(generated_at_utc=FIXED_TIME)
    contracts = registry["strategy_contracts"]
    assert "dividend" in contracts["capabilities_by_strategy"]
    assert "dividend" in contracts["artifacts_by_strategy"]
    assert contracts["capability_index"]["portfolio"] == ["dividend"]
    assert contracts["artifact_type_index"]["portfolio"] == [
        {"strategy_id": "dividend", "artifact_id": "portfolio_snapshot"}
    ]


def test_external_plugin_is_added_to_capability_and_artifact_indexes(tmp_path: Path):
    registration = tmp_path / "swing_registration.json"
    config = tmp_path / "external_strategy_registrations.json"
    _write_swing_registration(registration)
    _write_config(config, registration)

    registry = build_service_registry(
        generated_at_utc=FIXED_TIME,
        external_registration_config=config,
    )

    assert registry["summary"]["strategy_plugin_count"] == 2
    assert registry["summary"]["accepted_external_strategy_count"] == 1
    assert registry["summary"]["capability_count"] == 10
    assert registry["summary"]["published_artifact_count"] == 6
    assert registry["strategy_contracts"]["capability_index"]["executive_dashboard"] == [
        "SWING-001",
        "dividend",
    ]
    assert registry["strategy_contracts"]["artifact_type_index"]["opportunity_quality"] == [
        {"strategy_id": "SWING-001", "artifact_id": "opportunity_quality"}
    ]


def test_registry_order_and_indexes_are_deterministic(tmp_path: Path):
    registration = tmp_path / "swing_registration.json"
    config = tmp_path / "external_strategy_registrations.json"
    _write_swing_registration(registration)
    _write_config(config, registration)

    first = build_service_registry(
        generated_at_utc=FIXED_TIME,
        external_registration_config=config,
    )
    second = build_service_registry(
        generated_at_utc=FIXED_TIME,
        external_registration_config=config,
    )
    assert first == second
    assert [item["strategy_id"] for item in first["strategy_plugins"]] == [
        "dividend",
        "SWING-001",
    ]


def test_registry_hash_includes_strategy_contract_metadata(tmp_path: Path):
    base = build_service_registry(generated_at_utc=FIXED_TIME)
    registration = tmp_path / "swing_registration.json"
    config = tmp_path / "external_strategy_registrations.json"
    _write_swing_registration(registration)
    _write_config(config, registration)
    combined = build_service_registry(
        generated_at_utc=FIXED_TIME,
        external_registration_config=config,
    )
    assert base["registry_hash"] != combined["registry_hash"]


def test_markdown_displays_contract_capabilities_and_artifacts():
    registry = build_service_registry(generated_at_utc=FIXED_TIME)
    markdown = render_service_registry_markdown(registry)
    assert "Registry contract: **2.0**" in markdown
    assert "Capabilities: **7**" in markdown
    assert "Published artifacts: **4**" in markdown
    assert "portfolio_snapshot" in markdown
    assert "paper-only / advisory-only / reporting-only" in markdown


def test_registry_v2_does_not_enable_execution_or_capital_movement():
    registry = build_service_registry(generated_at_utc=FIXED_TIME)
    assert registry["paper_trade_mode"] is True
    assert registry["live_trading_enabled"] is False
    assert registry["broker_execution_enabled"] is False
    assert registry["governance"]["service_invocation_allowed"] is False
    assert registry["governance"]["order_execution_allowed"] is False
    assert registry["governance"]["capital_movement_allowed"] is False
