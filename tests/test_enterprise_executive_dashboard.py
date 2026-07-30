import json
from pathlib import Path

from src.dividend_bot import enterprise_executive_dashboard as dashboard

FIXED_TIME = "2026-07-30T04:00:00Z"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def valid_inventory() -> dict:
    return {
        "summary": {"running_count": 1, "contract_complete_count": 1},
        "strategies": [{
            "strategy_id": "BOT-001",
            "strategy_name": "Dividend Bot",
            "strategy_type": "DIVIDEND_ETF",
            "version": "1.0.0",
            "lifecycle_status": "PRODUCTION",
            "certification_level": "CERTIFIED",
            "runtime_status": "RUNNING",
            "health_status": "OK",
            "readiness": "READY",
            "output_count": 4,
            "contract_complete": True,
            "paper_trade_mode": True,
            "live_trading_enabled": False,
            "broker_execution_enabled": False,
        }],
    }


def valid_health() -> dict:
    return {
        "enterprise_status": "HEALTHY",
        "summary": {
            "healthy_count": 1,
            "warning_count": 0,
            "degraded_count": 0,
            "critical_count": 0,
            "offline_count": 0,
            "average_health_score": 98.0,
        },
        "strategies": [{
            "strategy_id": "BOT-001",
            "health_score": 98,
            "classification": "HEALTHY",
        }],
    }


def create_required_inputs(root: Path) -> None:
    write_json(root / "strategy_inventory.json", valid_inventory())
    write_json(root / "enterprise_health.json", valid_health())


def test_safety_constants_are_locked():
    assert dashboard.PAPER_TRADE_MODE is True
    assert dashboard.LIVE_TRADING_ENABLED is False
    assert dashboard.BROKER_EXECUTION_ENABLED is False


def test_required_and_optional_inputs_are_declared():
    assert dashboard.REQUIRED_INPUTS == ("strategy_inventory.json", "enterprise_health.json")
    assert "runtime_snapshot.json" in dashboard.OPTIONAL_INPUTS


def test_missing_required_inputs_produce_clear_errors(tmp_path):
    result = dashboard.build_executive_dashboard(tmp_path, generated_at_utc=FIXED_TIME)
    assert result["enterprise_summary"]["enterprise_status"] == "UNSAFE"
    assert len(result["errors"]) == 2


def test_missing_optional_inputs_are_warnings_not_errors(tmp_path):
    create_required_inputs(tmp_path)
    result = dashboard.build_executive_dashboard(tmp_path)
    assert not result["errors"]
    assert len(result["warnings"]) == len(dashboard.OPTIONAL_INPUTS)


def test_strategy_and_health_aggregation(tmp_path):
    create_required_inputs(tmp_path)
    result = dashboard.build_executive_dashboard(tmp_path, generated_at_utc=FIXED_TIME)
    strategy = result["strategy_summary"][0]
    assert strategy["strategy_id"] == "BOT-001"
    assert strategy["health_score"] == 98
    assert strategy["health_status"] == "HEALTHY"
    assert result["health_summary"]["average_health_score"] == 98.0


def test_healthy_inputs_create_healthy_dashboard(tmp_path):
    create_required_inputs(tmp_path)
    for filename in dashboard.OPTIONAL_INPUTS:
        write_json(tmp_path / filename, {})
    result = dashboard.build_executive_dashboard(tmp_path)
    assert result["enterprise_summary"]["enterprise_status"] == "HEALTHY"
    assert result["paper_safety"]["status"] == "SAFE"


def test_unsafe_strategy_forces_unsafe_enterprise_status(tmp_path):
    inventory = valid_inventory()
    inventory["strategies"][0]["live_trading_enabled"] = True
    write_json(tmp_path / "strategy_inventory.json", inventory)
    write_json(tmp_path / "enterprise_health.json", valid_health())
    result = dashboard.build_executive_dashboard(tmp_path)
    assert result["paper_safety"]["status"] == "UNSAFE"
    assert result["enterprise_summary"]["enterprise_status"] == "UNSAFE"


def test_contract_incomplete_creates_warning(tmp_path):
    inventory = valid_inventory()
    inventory["strategies"][0]["contract_complete"] = False
    write_json(tmp_path / "strategy_inventory.json", inventory)
    write_json(tmp_path / "enterprise_health.json", valid_health())
    result = dashboard.build_executive_dashboard(tmp_path)
    assert "BOT-001: contract incomplete" in result["alerts"]["warnings"]


def test_runtime_snapshot_is_optional_and_aggregated(tmp_path):
    create_required_inputs(tmp_path)
    write_json(tmp_path / "runtime_snapshot.json", {"runtime_status": "RUNNING", "plugin_count": 3})
    result = dashboard.build_executive_dashboard(tmp_path)
    assert result["runtime_summary"]["runtime_status"] == "RUNNING"
    assert result["runtime_summary"]["plugin_count"] == 3


def test_empty_inventory_is_supported(tmp_path):
    write_json(tmp_path / "strategy_inventory.json", {"summary": {}, "strategies": []})
    write_json(tmp_path / "enterprise_health.json", {"enterprise_status": "HEALTHY", "summary": {}, "strategies": []})
    result = dashboard.build_executive_dashboard(tmp_path)
    assert result["strategy_summary"] == []
    assert result["enterprise_summary"]["registered_strategy_count"] == 0


def test_invalid_json_is_reported(tmp_path):
    (tmp_path / "strategy_inventory.json").write_text("{bad", encoding="utf-8")
    write_json(tmp_path / "enterprise_health.json", valid_health())
    result = dashboard.build_executive_dashboard(tmp_path)
    assert any("invalid input strategy_inventory.json" in value for value in result["errors"])


def test_json_and_markdown_outputs(tmp_path):
    create_required_inputs(tmp_path)
    result = dashboard.build_executive_dashboard(tmp_path, generated_at_utc=FIXED_TIME)
    json_path = tmp_path / "out/executive_dashboard.json"
    md_path = tmp_path / "out/executive_dashboard.md"
    assert dashboard.write_executive_dashboard_json(result, json_path) == str(json_path)
    assert dashboard.write_executive_dashboard_markdown(result, md_path) == str(md_path)
    assert json.loads(json_path.read_text(encoding="utf-8"))["module_name"] == dashboard.MODULE_NAME
    assert "# Enterprise Executive Dashboard" in md_path.read_text(encoding="utf-8")


def test_build_and_write_uses_standard_filenames(tmp_path):
    create_required_inputs(tmp_path)
    paths = dashboard.build_and_write_executive_dashboard(tmp_path, tmp_path / "output")
    assert paths["json"].endswith("executive_dashboard.json")
    assert paths["markdown"].endswith("executive_dashboard.md")


def test_schema_and_metadata_are_present(tmp_path):
    create_required_inputs(tmp_path)
    result = dashboard.build_executive_dashboard(tmp_path, generated_at_utc=FIXED_TIME)
    assert result["module_version"] == "1.0.0"
    assert result["schema_version"] == "1.0"
    assert result["enterprise_version"] == "1.0"
    assert result["generated_at_utc"] == FIXED_TIME
    assert result["metadata"]["read_only"] is True
    assert result["metadata"]["allocation_allowed"] is False
    assert result["metadata"]["brokerage_communication_allowed"] is False
