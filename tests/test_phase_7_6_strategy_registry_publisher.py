from __future__ import annotations

import json
from pathlib import Path

import publish_enterprise_strategy_registry as launcher
from src.dividend_bot.enterprise_strategy_registry_publisher import (
    publish_enterprise_strategy_registry,
    validate_registry_source,
)


def _plugin(strategy_id: str) -> dict:
    return {
        "strategy_id": strategy_id,
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


def _source(root: Path) -> Path:
    path = root / "config" / "registry.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps({
            "strategy_plugins": [
                _plugin("DIVIDEND-001"),
                _plugin("SWING-001"),
            ]
        }),
        encoding="utf-8",
    )
    return path


def test_valid_source_requires_both_canonical_strategies() -> None:
    assert validate_registry_source({
        "strategy_plugins": [_plugin("DIVIDEND-001"), _plugin("SWING-001")]
    }) == []


def test_missing_required_strategy_is_blocked() -> None:
    errors = validate_registry_source({
        "strategy_plugins": [_plugin("DIVIDEND-001")]
    })
    assert any("SWING-001" in item for item in errors)


def test_unsafe_plugin_is_blocked(tmp_path: Path) -> None:
    source = _source(tmp_path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["strategy_plugins"][0]["live_trading_enabled"] = True
    source.write_text(json.dumps(payload), encoding="utf-8")
    report = publish_enterprise_strategy_registry(
        root_dir=tmp_path, source_path=source, target_path="results/registry.json"
    )
    assert report["publish_status"] == "BLOCKED"
    assert not (tmp_path / "results" / "registry.json").exists()


def test_publisher_writes_canonical_registry(tmp_path: Path) -> None:
    source = _source(tmp_path)
    report = publish_enterprise_strategy_registry(
        root_dir=tmp_path, source_path=source, target_path="results/registry.json"
    )
    payload = json.loads(
        (tmp_path / "results" / "registry.json").read_text(encoding="utf-8")
    )
    assert report["publish_status"] == "PASSED"
    assert report["strategy_ids"] == ["DIVIDEND-001", "SWING-001"]
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False


def test_canonical_dividend_source_declares_existing_evidence_contract() -> None:
    payload = json.loads(
        Path("config/enterprise_strategy_registry.json").read_text(encoding="utf-8")
    )
    dividend = next(
        item for item in payload["strategy_plugins"]
        if item["strategy_id"] == "DIVIDEND-001"
    )
    capabilities = {
        item["capability_id"] for item in dividend["capabilities"] if item["enabled"]
    }
    artifacts = {
        item["artifact_id"]: item["path"]
        for item in dividend["dashboard_artifacts"]
    }
    assert capabilities == {
        "executive_dashboard",
        "income_reporting",
        "investor_dashboard",
        "portfolio",
        "portfolio_lifecycle",
        "strategy_health",
        "wealth_attribution",
    }
    assert artifacts["ai_cio_executive_dashboard"] == (
        "results/ai_cio_executive_dashboard.json"
    )
    assert artifacts["enterprise_investor_dashboard"] == (
        "results/enterprise_investor_dashboard.json"
    )
    assert artifacts["portfolio_snapshot"] == "portfolio_snapshot.csv"
    assert dividend["capability_count"] == 7
    assert dividend["published_artifact_count"] == 4


def test_unrelated_existing_plugin_is_preserved(tmp_path: Path) -> None:
    source = _source(tmp_path)
    target = tmp_path / "results" / "registry.json"
    target.parent.mkdir()
    target.write_text(
        json.dumps({"strategy_plugins": [_plugin("OPTIONS-001")]}),
        encoding="utf-8",
    )
    report = publish_enterprise_strategy_registry(
        root_dir=tmp_path, source_path=source, target_path=target
    )
    assert report["strategy_ids"] == [
        "DIVIDEND-001", "OPTIONS-001", "SWING-001"
    ]
    assert report["preserved_strategy_ids"] == ["OPTIONS-001"]


def test_canonical_entries_replace_stale_versions(tmp_path: Path) -> None:
    source = _source(tmp_path)
    target = tmp_path / "results" / "registry.json"
    target.parent.mkdir()
    stale = _plugin("DIVIDEND-001")
    stale["live_trading_enabled"] = True
    target.write_text(
        json.dumps({"strategy_plugins": [stale]}), encoding="utf-8"
    )
    publish_enterprise_strategy_registry(
        root_dir=tmp_path, source_path=source, target_path=target
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    dividend = next(
        item for item in payload["strategy_plugins"]
        if item["strategy_id"] == "DIVIDEND-001"
    )
    assert dividend["live_trading_enabled"] is False


def test_legacy_dividend_alias_is_replaced_not_preserved(tmp_path: Path) -> None:
    source = _source(tmp_path)
    target = tmp_path / "results" / "registry.json"
    target.parent.mkdir()
    target.write_text(
        json.dumps({"strategy_plugins": [_plugin("dividend")]}),
        encoding="utf-8",
    )
    report = publish_enterprise_strategy_registry(
        root_dir=tmp_path, source_path=source, target_path=target
    )
    assert report["strategy_ids"] == ["DIVIDEND-001", "SWING-001"]
    assert "DIVIDEND" not in report["preserved_strategy_ids"]


def test_launcher_exit_codes(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        launcher,
        "publish_enterprise_strategy_registry",
        lambda **kwargs: {
            "publish_status": "PASSED",
            "strategy_ids": ["DIVIDEND-001", "SWING-001"],
            "target_path": "results/registry.json",
            "errors": [],
        },
    )
    assert launcher.main([]) == 0
    assert "Registry publish status: PASSED" in capsys.readouterr().out
