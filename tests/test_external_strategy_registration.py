import json
from pathlib import Path

import pytest

from src.dividend_bot.enterprise_dividend_service_registry_event_wiring import (
    build_service_registry,
    write_service_registry,
)
from src.dividend_bot.external_strategy_registration import (
    load_external_strategy_plugins,
    normalize_external_strategy_registration,
)


def valid_registration(**overrides):
    payload = {
        "strategy_id": "SWING-001",
        "display_name": "Trade Swing Bot",
        "plugin_type": "STRATEGY_PLUGIN",
        "status": "READY",
        "enabled": True,
        "version": "1.0.0",
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


def write_config(tmp_path: Path, registration_path: Path, *, required=False, strategy_id="SWING-001") -> Path:
    path = tmp_path / "external.json"
    path.write_text(json.dumps({
        "schema_version": "1.0",
        "registrations": [{
            "strategy_id": strategy_id,
            "registration_path": str(registration_path),
            "required": required,
        }],
    }), encoding="utf-8")
    return path


def test_dividend_only_when_config_absent(tmp_path: Path):
    registry = build_service_registry(external_registration_config=tmp_path / "missing.json")
    assert [item["strategy_id"] for item in registry["strategy_plugins"]] == ["dividend"]
    assert registry["summary"]["accepted_external_strategy_count"] == 0


def test_optional_missing_registration_warns_and_keeps_dividend(tmp_path: Path):
    config = write_config(tmp_path, tmp_path / "missing-registration.json")
    registry = build_service_registry(external_registration_config=config)
    assert [item["strategy_id"] for item in registry["strategy_plugins"]] == ["dividend"]
    assert registry["external_registration_warnings"][0]["code"] == "REGISTRATION_MISSING"


def test_valid_swing_registration_is_accepted(tmp_path: Path):
    registration = tmp_path / "swing.json"
    registration.write_text(json.dumps(valid_registration()), encoding="utf-8")
    config = write_config(tmp_path, registration)
    registry = build_service_registry(external_registration_config=config)
    assert [item["strategy_id"] for item in registry["strategy_plugins"]] == ["dividend", "SWING-001"]
    assert registry["summary"]["strategy_plugin_count"] == 2
    assert registry["summary"]["accepted_external_strategy_count"] == 1


@pytest.mark.parametrize("field,value", [
    ("live_trading_enabled", True),
    ("broker_execution_enabled", True),
    ("capital_movement_enabled", True),
    ("paper_trade_mode", False),
    ("paper_compatible", False),
    ("automatic_activation_allowed", True),
    ("direct_database_writes", True),
])
def test_unsafe_external_registration_is_rejected(field, value):
    with pytest.raises(ValueError, match=field):
        normalize_external_strategy_registration(valid_registration(**{field: value}))


def test_duplicate_dividend_strategy_id_is_rejected_safely(tmp_path: Path):
    registration = tmp_path / "duplicate.json"
    registration.write_text(json.dumps(valid_registration(strategy_id="dividend")), encoding="utf-8")
    config = write_config(tmp_path, registration, strategy_id="dividend")
    registry = build_service_registry(external_registration_config=config)
    assert [item["strategy_id"] for item in registry["strategy_plugins"]] == ["dividend"]
    assert "duplicate strategy_id" in registry["external_registration_warnings"][0]["message"]


def test_invalid_json_is_warning_for_optional_registration(tmp_path: Path):
    registration = tmp_path / "bad.json"
    registration.write_text("{not-json", encoding="utf-8")
    config = write_config(tmp_path, registration)
    registry = build_service_registry(external_registration_config=config)
    assert registry["summary"]["strategy_plugin_count"] == 1
    assert registry["external_registration_warnings"][0]["code"] == "REGISTRATION_REJECTED"


def test_required_registration_failure_is_host_failure(tmp_path: Path):
    config = write_config(tmp_path, tmp_path / "missing.json", required=True)
    with pytest.raises(ValueError, match="Required external strategy registration failed"):
        build_service_registry(external_registration_config=config)


def test_registry_output_is_atomic_and_has_no_tmp_files(tmp_path: Path):
    registry = build_service_registry()
    paths = write_service_registry(registry, tmp_path)
    assert Path(paths["json"]).is_file()
    assert Path(paths["markdown"]).is_file()
    assert not list(tmp_path.glob(".*.tmp"))


def test_adapter_has_no_swing_production_imports():
    source = Path("src/dividend_bot/external_strategy_registration.py").read_text(encoding="utf-8")
    assert "swing_trade_bot" not in source
    assert "Trade-Swing-Bot" not in source

def test_external_registration_preserves_declared_repository_root(tmp_path: Path):
    swing_root = tmp_path / "swing-repo"
    registration = swing_root / "configs/swing.json"
    registration.parent.mkdir(parents=True)
    registration.write_text(json.dumps(valid_registration()), encoding="utf-8")
    config = tmp_path / "external.json"
    config.write_text(json.dumps({
        "schema_version": "1.0",
        "registrations": [{
            "strategy_id": "SWING-001",
            "registration_path": str(registration),
            "repository_root": str(swing_root),
            "required": False,
        }],
    }), encoding="utf-8")

    plugins, warnings = load_external_strategy_plugins(config)

    assert warnings == []
    assert plugins[0]["repository_root"] == str(swing_root.resolve())


def test_external_registration_infers_repository_root_from_configs_directory(tmp_path: Path):
    swing_root = tmp_path / "swing-repo"
    registration = swing_root / "configs/swing.json"
    registration.parent.mkdir(parents=True)
    registration.write_text(json.dumps(valid_registration()), encoding="utf-8")
    config = write_config(tmp_path, registration)

    plugins, warnings = load_external_strategy_plugins(config)

    assert warnings == []
    assert plugins[0]["repository_root"] == str(swing_root.resolve())

