from __future__ import annotations

import json
from pathlib import Path

import pytest

from enterprise_core.integrations.dividend_bot import (
    DIVIDEND_STRATEGY_ID,
    DividendBotEnterprisePlugin,
    DividendContractPaths,
)
from enterprise_core.plugin_sdk.models import PluginContext
from enterprise_core.strategy_registry.loader import StrategyManifestLoader
from enterprise_core.strategy_registry.validator import StrategyManifestValidator


def _context(root: Path) -> PluginContext:
    return PluginContext(
        strategy_id=DIVIDEND_STRATEGY_ID,
        strategy_root=str(root),
        required_services=("enterprise_market_data",),
    )


def test_plugin_is_permanently_paper_only() -> None:
    plugin = DividendBotEnterprisePlugin(lambda context: {})
    assert plugin.paper_trade_mode is True
    assert plugin.live_trading_enabled is False
    assert plugin.broker_execution_enabled is False


def test_initialize_writes_enterprise_contracts(tmp_path: Path) -> None:
    plugin = DividendBotEnterprisePlugin(lambda context: {})
    plugin.initialize(_context(tmp_path))
    for name in ("manifest", "status", "health", "outputs"):
        assert (tmp_path / "enterprise_contracts" / f"{name}.json").exists()


def test_manifest_is_discoverable_and_valid(tmp_path: Path) -> None:
    (tmp_path / "run_daily_paper_cycle.py").write_text("pass\n", encoding="utf-8")
    plugin = DividendBotEnterprisePlugin(lambda context: {})
    plugin.initialize(_context(tmp_path))
    path = tmp_path / "enterprise_contracts" / "manifest.json"
    manifest = StrategyManifestLoader().load(path)
    validation = StrategyManifestValidator().validate(manifest, strategy_root=tmp_path)
    assert validation.valid is True
    assert manifest.strategy_id == DIVIDEND_STRATEGY_ID


def test_run_delegates_without_changing_strategy_payload(tmp_path: Path) -> None:
    received: list[PluginContext] = []

    def runner(context: PluginContext):
        received.append(context)
        return {
            "status": "SUCCESS",
            "output_paths": {"daily_report": "daily_paper_report.md"},
            "metadata": {"positions": 4},
        }

    plugin = DividendBotEnterprisePlugin(runner)
    plugin.initialize(_context(tmp_path))
    result = plugin.run()
    assert received == [_context(tmp_path)]
    assert result.status == "SUCCESS"
    assert result.output_paths == {"daily_report": "daily_paper_report.md"}
    assert result.metadata == {"positions": 4}


def test_run_updates_status_health_and_outputs(tmp_path: Path) -> None:
    plugin = DividendBotEnterprisePlugin(
        lambda context: {
            "status": "WARNING",
            "warnings": ["optional report missing"],
            "output_paths": {"portfolio": "portfolio_snapshot.csv"},
        }
    )
    plugin.initialize(_context(tmp_path))
    plugin.run()
    status = json.loads((tmp_path / "enterprise_contracts/status.json").read_text(encoding="utf-8"))
    health = json.loads((tmp_path / "enterprise_contracts/health.json").read_text(encoding="utf-8"))
    outputs = json.loads((tmp_path / "enterprise_contracts/outputs.json").read_text(encoding="utf-8"))
    assert status["runtime_status"] == "ONLINE"
    assert status["last_run_status"] == "WARNING"
    assert health["health_status"] == "WARNING"
    assert outputs["outputs"]["portfolio"] == "portfolio_snapshot.csv"


def test_runner_failure_writes_error_contracts_and_reraises(tmp_path: Path) -> None:
    def failing_runner(context: PluginContext):
        raise RuntimeError("paper cycle failed")

    plugin = DividendBotEnterprisePlugin(failing_runner)
    plugin.initialize(_context(tmp_path))
    with pytest.raises(RuntimeError, match="paper cycle failed"):
        plugin.run()
    health = json.loads((tmp_path / "enterprise_contracts/health.json").read_text(encoding="utf-8"))
    assert health["health_status"] == "ERROR"


def test_shutdown_marks_strategy_offline(tmp_path: Path) -> None:
    plugin = DividendBotEnterprisePlugin(lambda context: {})
    plugin.initialize(_context(tmp_path))
    plugin.shutdown()
    status = json.loads((tmp_path / "enterprise_contracts/status.json").read_text(encoding="utf-8"))
    assert status["runtime_status"] == "OFFLINE"


def test_rejects_wrong_strategy_id(tmp_path: Path) -> None:
    plugin = DividendBotEnterprisePlugin(lambda context: {})
    context = PluginContext(
        strategy_id="wrong",
        strategy_root=str(tmp_path),
        required_services=("enterprise_market_data",),
    )
    with pytest.raises(ValueError, match="does not match"):
        plugin.initialize(context)


def test_rejects_contract_path_escape(tmp_path: Path) -> None:
    plugin = DividendBotEnterprisePlugin(
        lambda context: {},
        contract_paths=DividendContractPaths(manifest="../manifest.json"),
    )
    with pytest.raises(ValueError, match="escapes strategy root"):
        plugin.initialize(_context(tmp_path))


def test_plugin_requires_initialization(tmp_path: Path) -> None:
    plugin = DividendBotEnterprisePlugin(lambda context: {})
    with pytest.raises(RuntimeError, match="not initialized"):
        plugin.run()
