import json
from pathlib import Path

from src.dividend_bot import strategy_inventory_service as inventory

FIXED_TIME = "2026-07-30T03:00:00Z"


def write_contracts(root: Path, *, strategy_id: str = "STRATEGY-DIVIDEND-001", health: str = "OK") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(json.dumps({
        "strategy_id": strategy_id,
        "strategy_name": "Dividend Strategy",
        "strategy_type": "DIVIDEND_ETF",
        "version": "1.0.0",
        "lifecycle_status": "PRODUCTION_PAPER",
        "certification_level": "ENTERPRISE_CERTIFIED",
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capabilities": ["income", "paper-cycle"],
        "required_enterprise_services": ["market-data", "registry"],
    }), encoding="utf-8")
    (root / "status.json").write_text(json.dumps({
        "runtime_status": "RUNNING",
        "latest_cycle_id": "cycle-1",
        "latest_successful_run": FIXED_TIME,
        "warnings": [],
    }), encoding="utf-8")
    (root / "health.json").write_text(json.dumps({
        "overall_status": health,
        "readiness": "READY",
        "last_heartbeat": FIXED_TIME,
        "warnings": [],
    }), encoding="utf-8")
    (root / "outputs.json").write_text(json.dumps({"output_count": 4}), encoding="utf-8")
    return root


def test_safety_constants_are_locked():
    assert inventory.PAPER_TRADE_MODE is True
    assert inventory.LIVE_TRADING_ENABLED is False
    assert inventory.BROKER_EXECUTION_ENABLED is False


def test_build_complete_inventory_item(tmp_path):
    item = inventory.build_inventory_item(write_contracts(tmp_path / "dividend"))
    assert item.strategy_id == "STRATEGY-DIVIDEND-001"
    assert item.contract_complete is True
    assert item.runtime_status == "RUNNING"
    assert item.health_status == "OK"
    assert item.output_count == 4
    assert item.errors == ()


def test_missing_contracts_are_reported_not_raised(tmp_path):
    directory = tmp_path / "partial"
    directory.mkdir()
    (directory / "manifest.json").write_text(json.dumps({
        "strategy_id": "STRATEGY-PARTIAL-001",
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
    }), encoding="utf-8")
    item = inventory.build_inventory_item(directory)
    assert item.contract_complete is False
    assert any("missing contract: status.json" == message for message in item.errors)


def test_malformed_contract_is_reported(tmp_path):
    directory = write_contracts(tmp_path / "bad")
    (directory / "health.json").write_text("{bad json", encoding="utf-8")
    item = inventory.build_inventory_item(directory)
    assert any(message.startswith("invalid contract health.json") for message in item.errors)


def test_unsafe_manifest_is_flagged(tmp_path):
    directory = write_contracts(tmp_path / "unsafe")
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    manifest.update({
        "paper_trade_mode": False,
        "live_trading_enabled": True,
        "broker_execution_enabled": True,
    })
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    item = inventory.build_inventory_item(directory)
    assert "paper_trade_mode must be true" in item.errors
    assert "live_trading_enabled must be false" in item.errors
    assert "broker_execution_enabled must be false" in item.errors


def test_inventory_is_sorted_by_stable_strategy_id(tmp_path):
    second = write_contracts(tmp_path / "second", strategy_id="STRATEGY-SWING-001")
    first = write_contracts(tmp_path / "first", strategy_id="STRATEGY-DIVIDEND-001")
    result = inventory.build_strategy_inventory([second, first], generated_at_utc=FIXED_TIME)
    assert [item.strategy_id for item in result.strategies] == [
        "STRATEGY-DIVIDEND-001", "STRATEGY-SWING-001"
    ]
    assert result.generated_at_utc == FIXED_TIME


def test_duplicate_strategy_ids_create_warning(tmp_path):
    one = write_contracts(tmp_path / "one")
    two = write_contracts(tmp_path / "two")
    result = inventory.build_strategy_inventory([one, two])
    assert result.warnings == ("duplicate strategy_id: STRATEGY-DIVIDEND-001",)


def test_summary_counts(tmp_path):
    okay = write_contracts(tmp_path / "okay", strategy_id="STRATEGY-DIVIDEND-001")
    warning = write_contracts(tmp_path / "warning", strategy_id="STRATEGY-SWING-001", health="WARNING")
    result = inventory.build_strategy_inventory([okay, warning])
    summary = inventory.build_summary(result.strategies)
    assert summary["strategy_count"] == 2
    assert summary["healthy_count"] == 1
    assert summary["warning_count"] == 1
    assert summary["paper_safe_count"] == 2


def test_json_and_markdown_outputs(tmp_path):
    contract_dir = write_contracts(tmp_path / "contracts")
    result = inventory.build_strategy_inventory([contract_dir], generated_at_utc=FIXED_TIME)
    json_path = tmp_path / "results" / "strategy_inventory.json"
    md_path = tmp_path / "results" / "strategy_inventory.md"
    inventory.write_strategy_inventory_json(result, json_path)
    inventory.write_strategy_inventory_markdown(result, md_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["summary"]["strategy_count"] == 1
    assert payload["paper_trade_mode"] is True
    markdown = md_path.read_text(encoding="utf-8")
    assert "# Enterprise Strategy Inventory" in markdown
    assert "STRATEGY-DIVIDEND-001" in markdown


def test_build_and_write_uses_standard_output_names(tmp_path):
    contract_dir = write_contracts(tmp_path / "contracts")
    paths = inventory.build_and_write_strategy_inventory(
        [contract_dir], tmp_path / "results", generated_at_utc=FIXED_TIME
    )
    assert Path(paths["json"]).name == "strategy_inventory.json"
    assert Path(paths["markdown"]).name == "strategy_inventory.md"
