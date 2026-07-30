import json
from pathlib import Path

import pytest

from src.dividend_bot import enterprise_ai_cio_release_readiness as module


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _populate(root: Path) -> None:
    for filename in module.REQUIRED_OUTPUTS:
        payload = {"module_name": filename.removesuffix(".json")}
        if filename == "executive_dashboard.json":
            payload = {
                "enterprise_summary": {"enterprise_status": "HEALTHY"},
                "paper_safety": {
                    "paper_trade_mode": True,
                    "live_trading_enabled": False,
                    "broker_execution_enabled": False,
                },
            }
        _write(root / filename, payload)


def test_safety_constants_are_locked():
    assert module.PAPER_TRADE_MODE is True
    assert module.LIVE_TRADING_ENABLED is False
    assert module.BROKER_EXECUTION_ENABLED is False


def test_all_contracts_ready(tmp_path):
    _populate(tmp_path)
    report = module.build_release_readiness(tmp_path, generated_at_utc="2026-07-30T00:00:00Z")
    assert report["release_status"] == "READY_FOR_FREEZE"
    assert report["present_output_count"] == len(module.REQUIRED_OUTPUTS)
    assert report["blockers"] == []


def test_missing_contract_blocks(tmp_path):
    _populate(tmp_path)
    (tmp_path / "learning_feedback.json").unlink()
    report = module.build_release_readiness(tmp_path)
    assert report["release_status"] == "BLOCKED"
    assert any("learning_feedback.json" in item for item in report["blockers"])


def test_invalid_json_blocks(tmp_path):
    _populate(tmp_path)
    (tmp_path / "enterprise_health.json").write_text("{bad", encoding="utf-8")
    report = module.build_release_readiness(tmp_path)
    assert report["release_status"] == "BLOCKED"
    assert any("invalid JSON contract" in item for item in report["blockers"])


def test_non_object_json_blocks(tmp_path):
    _populate(tmp_path)
    (tmp_path / "strategy_inventory.json").write_text("[]", encoding="utf-8")
    report = module.build_release_readiness(tmp_path)
    assert report["release_status"] == "BLOCKED"


def test_unsafe_dashboard_blocks(tmp_path):
    _populate(tmp_path)
    _write(tmp_path / "executive_dashboard.json", {
        "enterprise_summary": {"enterprise_status": "UNSAFE"},
        "paper_safety": {
            "paper_trade_mode": False,
            "live_trading_enabled": True,
            "broker_execution_enabled": True,
        },
    })
    report = module.build_release_readiness(tmp_path)
    assert report["release_status"] == "BLOCKED"
    assert any("paper-safety" in item for item in report["blockers"])


def test_markdown_contains_status(tmp_path):
    _populate(tmp_path)
    report = module.build_release_readiness(tmp_path)
    markdown = module.render_markdown(report)
    assert "READY_FOR_FREEZE" in markdown
    assert "Manual review" in markdown


def test_standard_outputs_are_written(tmp_path):
    _populate(tmp_path)
    report = module.build_and_write_release_readiness(tmp_path)
    assert report["release_status"] == "READY_FOR_FREEZE"
    assert (tmp_path / "enterprise_ai_cio_release_readiness.json").exists()
    assert (tmp_path / "enterprise_ai_cio_release_readiness.md").exists()


def test_manual_release_only(tmp_path):
    _populate(tmp_path)
    report = module.build_release_readiness(tmp_path)
    assert report["governance"]["automatic_release_enabled"] is False
    assert report["governance"]["manual_review_required"] is True
