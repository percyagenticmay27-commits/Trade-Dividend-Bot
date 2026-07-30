from __future__ import annotations

import json
from pathlib import Path

from enterprise_core.ai_cio.discovery import AICIODiscoveryService


def _write_strategy(root: Path, strategy_id: str = "strategy-001") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "strategy_id": strategy_id,
        "strategy_name": "Test Strategy",
        "version": "1.0.0",
        "lifecycle_status": "PAPER",
        "certification_level": "DEVELOPMENT",
        "entrypoint": "run.py",
        "capabilities": ["market_analysis"],
        "permissions": ["market_data.read"],
        "required_services": ["enterprise_market_data"],
        "output_paths": {
            "manifest": "manifest.json",
            "status": "status.json",
            "health": "health.json",
            "outputs": "outputs.json",
        },
        "state_owner": strategy_id,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
    }
    (root / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    (root / "run.py").write_text("pass\n", encoding="utf-8")
    (root / "status.json").write_text(
        json.dumps({"strategy_id": strategy_id, "runtime_status": "ONLINE"}), encoding="utf-8"
    )
    (root / "health.json").write_text(
        json.dumps({"strategy_id": strategy_id, "health_status": "OK"}), encoding="utf-8"
    )
    (root / "outputs.json").write_text(
        json.dumps({"strategy_id": strategy_id, "output_files": []}), encoding="utf-8"
    )
    return root


def test_discovers_valid_strategy(tmp_path: Path) -> None:
    _write_strategy(tmp_path / "strategy")
    snapshot = AICIODiscoveryService().discover([tmp_path])
    assert snapshot.strategy_count == 1
    assert snapshot.strategies[0].strategy_id == "strategy-001"
    assert snapshot.strategies[0].health_status == "HEALTHY"


def test_orders_records_by_stable_id(tmp_path: Path) -> None:
    _write_strategy(tmp_path / "b", "strategy-b")
    _write_strategy(tmp_path / "a", "strategy-a")
    snapshot = AICIODiscoveryService().discover([tmp_path])
    assert [item.strategy_id for item in snapshot.strategies] == ["strategy-a", "strategy-b"]


def test_missing_root_is_warning(tmp_path: Path) -> None:
    snapshot = AICIODiscoveryService().discover([tmp_path / "missing"])
    assert snapshot.strategy_count == 0
    assert "discovery root not found" in snapshot.warnings[0]


def test_invalid_manifest_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "bad"
    root.mkdir()
    (root / "manifest.json").write_text("{}", encoding="utf-8")
    snapshot = AICIODiscoveryService().discover([tmp_path])
    assert snapshot.strategy_count == 0
    assert snapshot.rejected


def test_duplicate_strategy_id_is_rejected(tmp_path: Path) -> None:
    _write_strategy(tmp_path / "one", "duplicate")
    _write_strategy(tmp_path / "two", "duplicate")
    snapshot = AICIODiscoveryService().discover([tmp_path])
    assert snapshot.strategy_count == 1
    assert any("already registered" in item for item in snapshot.rejected)


def test_health_warning_is_exposed(tmp_path: Path) -> None:
    root = _write_strategy(tmp_path / "strategy")
    (root / "health.json").unlink()
    snapshot = AICIODiscoveryService().discover([tmp_path])
    assert snapshot.strategies[0].health_status == "WARNING"
    assert snapshot.strategies[0].health_score == 75


def test_snapshot_serialization_contains_safety_flags(tmp_path: Path) -> None:
    _write_strategy(tmp_path / "strategy")
    payload = AICIODiscoveryService().discover([tmp_path]).to_dict()
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False


def test_writes_snapshot_json(tmp_path: Path) -> None:
    _write_strategy(tmp_path / "strategy")
    snapshot = AICIODiscoveryService().discover([tmp_path])
    target = AICIODiscoveryService.write_snapshot(snapshot, tmp_path / "reports" / "discovery.json")
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["strategy_count"] == 1


def test_discovers_direct_manifest_path(tmp_path: Path) -> None:
    root = _write_strategy(tmp_path / "strategy")
    snapshot = AICIODiscoveryService().discover([root / "manifest.json"])
    assert snapshot.strategy_count == 1


def test_service_is_permanently_paper_only() -> None:
    service = AICIODiscoveryService()
    assert service.paper_trade_mode is True
    assert service.live_trading_enabled is False
    assert service.broker_execution_enabled is False
