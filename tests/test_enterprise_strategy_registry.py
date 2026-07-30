from __future__ import annotations

import json
from pathlib import Path

import pytest

from enterprise_core.strategy_registry import (
    DuplicateStrategyError,
    ManifestLoadError,
    StrategyDiscoveryService,
    StrategyHealthMonitor,
    StrategyManifest,
    StrategyManifestLoader,
    StrategyManifestValidator,
    StrategyRegistry,
)


def manifest_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "strategy_id": "dividend-bot",
        "strategy_name": "Dividend Bot",
        "version": "1.0.0",
        "lifecycle_status": "QA",
        "certification_level": "QA",
        "entrypoint": "run.py",
        "capabilities": ["income_analysis"],
        "permissions": ["read_market_data", "write_strategy_outputs"],
        "required_services": ["enterprise_market_data"],
        "output_paths": {
            "manifest": "manifest.json",
            "status": "status.json",
            "health": "health.json",
            "outputs": "outputs.json",
        },
        "state_owner": "dividend-bot",
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "schema_version": "1.0",
    }
    payload.update(overrides)
    return payload


def make_manifest(**overrides: object) -> StrategyManifest:
    return StrategyManifest.from_dict(manifest_payload(**overrides))


def write_strategy(root: Path, **overrides: object) -> Path:
    root.mkdir(parents=True)
    (root / "run.py").write_text("print('paper only')\n", encoding="utf-8")
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps(manifest_payload(**overrides)), encoding="utf-8")
    return manifest


def test_manifest_round_trip() -> None:
    manifest = make_manifest()
    assert StrategyManifest.from_dict(manifest.to_dict()) == manifest


def test_manifest_requires_paper_only() -> None:
    with pytest.raises(ValueError, match="paper_trade_mode"):
        make_manifest(paper_trade_mode=False)


def test_manifest_rejects_live_trading() -> None:
    with pytest.raises(ValueError, match="live_trading_enabled"):
        make_manifest(live_trading_enabled=True)


def test_manifest_rejects_broker_execution() -> None:
    with pytest.raises(ValueError, match="broker_execution_enabled"):
        make_manifest(broker_execution_enabled=True)


def test_manifest_requires_all_contract_paths() -> None:
    with pytest.raises(ValueError, match="missing required output paths"):
        make_manifest(output_paths={"manifest": "manifest.json"})


def test_manifest_rejects_duplicate_capabilities() -> None:
    with pytest.raises(ValueError, match="duplicates"):
        make_manifest(capabilities=["income", "income"])


def test_loader_loads_valid_manifest(tmp_path: Path) -> None:
    path = write_strategy(tmp_path / "strategy")
    assert StrategyManifestLoader().load(path).strategy_id == "dividend-bot"


def test_loader_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ManifestLoadError, match="not found"):
        StrategyManifestLoader().load(tmp_path / "manifest.json")


def test_loader_rejects_non_object_json(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ManifestLoadError, match="root"):
        StrategyManifestLoader().load(path)


def test_validator_accepts_valid_manifest(tmp_path: Path) -> None:
    root = tmp_path / "strategy"
    write_strategy(root)
    result = StrategyManifestValidator().validate(make_manifest(), strategy_root=root)
    assert result.valid is True
    assert result.errors == ()


def test_validator_rejects_forbidden_permission() -> None:
    manifest = make_manifest(permissions=["broker_execution"])
    result = StrategyManifestValidator().validate(manifest)
    assert result.valid is False
    assert "forbidden permissions" in result.errors[0]


def test_validator_rejects_missing_entrypoint(tmp_path: Path) -> None:
    root = tmp_path / "strategy"
    root.mkdir()
    result = StrategyManifestValidator().validate(make_manifest(), strategy_root=root)
    assert result.valid is False
    assert any("entrypoint not found" in error for error in result.errors)


def test_validator_rejects_escaping_entrypoint(tmp_path: Path) -> None:
    root = tmp_path / "strategy"
    root.mkdir()
    manifest = make_manifest(entrypoint="../run.py")
    result = StrategyManifestValidator().validate(manifest, strategy_root=root)
    assert any("escapes strategy root" in error for error in result.errors)


def test_registry_registers_and_gets_case_insensitively() -> None:
    registry = StrategyRegistry()
    registry.register(make_manifest())
    assert registry.get("DIVIDEND-BOT").strategy_name == "Dividend Bot"


def test_registry_rejects_duplicate_ids() -> None:
    registry = StrategyRegistry()
    registry.register(make_manifest())
    with pytest.raises(DuplicateStrategyError):
        registry.register(make_manifest(strategy_name="Other"))


def test_registry_lists_in_stable_order() -> None:
    registry = StrategyRegistry()
    registry.register(make_manifest(strategy_id="zeta"))
    registry.register(make_manifest(strategy_id="alpha"))
    assert [item.strategy_id for item in registry.list()] == ["alpha", "zeta"]


def test_discovery_finds_nested_manifests(tmp_path: Path) -> None:
    write_strategy(tmp_path / "one", strategy_id="one")
    write_strategy(tmp_path / "nested" / "two", strategy_id="two")
    result = StrategyDiscoveryService().discover((tmp_path,))
    assert [item.strategy_id for item in result.discovered] == ["one", "two"]
    assert result.rejected == ()


def test_discovery_rejects_duplicate_strategy_ids(tmp_path: Path) -> None:
    write_strategy(tmp_path / "one")
    write_strategy(tmp_path / "two")
    result = StrategyDiscoveryService().discover((tmp_path,))
    assert len(result.discovered) == 1
    assert len(result.rejected) == 1


def test_discovery_warns_for_missing_root(tmp_path: Path) -> None:
    result = StrategyDiscoveryService().discover((tmp_path / "missing",))
    assert result.discovered == ()
    assert len(result.warnings) == 1


def test_health_monitor_reports_healthy_contracts(tmp_path: Path) -> None:
    root = tmp_path / "strategy"
    write_strategy(root)
    (root / "status.json").write_text(json.dumps({"strategy_id": "dividend-bot", "runtime_status": "ONLINE"}), encoding="utf-8")
    (root / "health.json").write_text(json.dumps({"strategy_id": "dividend-bot", "health_status": "OK"}), encoding="utf-8")
    (root / "outputs.json").write_text(json.dumps({"strategy_id": "dividend-bot", "output_files": []}), encoding="utf-8")
    result = StrategyHealthMonitor().assess(make_manifest(), root)
    assert result.status == "HEALTHY"
    assert result.score == 100


def test_health_monitor_reports_missing_contracts(tmp_path: Path) -> None:
    root = tmp_path / "strategy"
    write_strategy(root)
    result = StrategyHealthMonitor().assess(make_manifest(), root)
    assert result.status == "ERROR"
    assert result.score == 25
    assert len(result.missing_files) == 3


def test_registry_components_are_permanently_paper_only() -> None:
    for component in (StrategyRegistry, StrategyHealthMonitor):
        assert component.paper_trade_mode is True
        assert component.live_trading_enabled is False
        assert component.broker_execution_enabled is False
