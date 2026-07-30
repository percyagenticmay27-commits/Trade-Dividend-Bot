import json
from pathlib import Path

import pytest

from src.dividend_bot import cross_strategy_risk_engine as risk

FIXED_TIME = "2026-07-30T04:30:00Z"


def manager(weights=None, reserve=20.0):
    weights = weights or [("dividend", 40.0), ("swing", 40.0)]
    return {
        "recommendations": [
            {"strategy_id": strategy_id, "recommended_weight_pct": weight, "health_classification": "HEALTHY"}
            for strategy_id, weight in weights
        ],
        "cash_reserve_pct": reserve,
    }


def test_safety_constants_are_locked():
    assert risk.PAPER_TRADE_MODE is True
    assert risk.LIVE_TRADING_ENABLED is False
    assert risk.BROKER_EXECUTION_ENABLED is False
    assert risk.CAPITAL_MOVEMENT_ENABLED is False


def test_acceptable_balanced_portfolio():
    report = risk.build_cross_strategy_risk_report(manager(), generated_at_utc=FIXED_TIME)
    assert report["risk_status"] == "WATCH"
    assert report["summary"]["strategy_count"] == 2
    assert report["generated_at_utc"] == FIXED_TIME


def test_single_strategy_does_not_require_correlation_warning():
    report = risk.build_cross_strategy_risk_report(manager([("dividend", 80.0)], 20.0), policy={"max_strategy_weight_pct": 100.0})
    assert not report["warnings"]


def test_concentration_creates_high_finding():
    report = risk.build_cross_strategy_risk_report(manager([("dividend", 75.0)], 25.0))
    assert report["risk_status"] == "HIGH"
    assert any(item["type"] == "CONCENTRATION" for item in report["findings"])


def test_low_cash_reserve_creates_high_finding():
    report = risk.build_cross_strategy_risk_report(manager([("dividend", 95.0)], 5.0), policy={"max_strategy_weight_pct": 100.0})
    assert any(item["type"] == "CASH_RESERVE" for item in report["findings"])


def test_overallocation_is_critical():
    report = risk.build_cross_strategy_risk_report(manager([("a", 60.0), ("b", 50.0)], 0.0), policy={"max_strategy_weight_pct": 100.0})
    assert report["risk_status"] == "CRITICAL"
    assert any(item["type"] == "OVERALLOCATION" for item in report["findings"])


def test_critical_health_exposure_is_critical():
    health = {"strategies": [{"strategy_id": "dividend", "classification": "CRITICAL"}]}
    report = risk.build_cross_strategy_risk_report(manager([("dividend", 50.0)], 50.0), enterprise_health=health, policy={"max_strategy_weight_pct": 100.0})
    assert report["risk_status"] == "CRITICAL"
    assert any(item["type"] == "HEALTH_EXPOSURE" for item in report["findings"])


def test_high_correlation_is_reported():
    evidence = {"pairs": [{"strategy_a": "dividend", "strategy_b": "swing", "correlation": 0.91}]}
    report = risk.build_cross_strategy_risk_report(manager(), correlation_evidence=evidence)
    assert any(item["type"] == "CORRELATION" for item in report["findings"])


def test_policy_thresholds_are_applied():
    report = risk.build_cross_strategy_risk_report(manager(), policy={"max_strategy_weight_pct": 35.0})
    assert sum(item["type"] == "CONCENTRATION" for item in report["findings"]) == 2


def test_missing_required_input_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        risk.build_and_write_cross_strategy_risk(tmp_path / "missing.json", tmp_path / "results")


def test_invalid_required_input_raises(tmp_path):
    path = tmp_path / "manager.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        risk.build_and_write_cross_strategy_risk(path, tmp_path / "results")


def test_optional_invalid_input_adds_warning(tmp_path):
    manager_path = tmp_path / "manager.json"
    manager_path.write_text(json.dumps(manager()), encoding="utf-8")
    bad_path = tmp_path / "health.json"
    bad_path.write_text("not json", encoding="utf-8")
    outputs = risk.build_and_write_cross_strategy_risk(manager_path, tmp_path / "results", enterprise_health_path=bad_path)
    payload = json.loads(Path(outputs["json"]).read_text(encoding="utf-8"))
    assert any("invalid optional input" in item for item in payload["warnings"])


def test_json_and_markdown_outputs(tmp_path):
    manager_path = tmp_path / "manager.json"
    manager_path.write_text(json.dumps(manager()), encoding="utf-8")
    outputs = risk.build_and_write_cross_strategy_risk(manager_path, tmp_path / "results", generated_at_utc=FIXED_TIME)
    payload = json.loads(Path(outputs["json"]).read_text(encoding="utf-8"))
    markdown = Path(outputs["markdown"]).read_text(encoding="utf-8")
    assert payload["module_name"] == risk.MODULE_NAME
    assert "# Cross-Strategy Risk Report" in markdown
    assert outputs["json"].endswith("cross_strategy_risk.json")
    assert outputs["markdown"].endswith("cross_strategy_risk.md")


def test_schema_and_governance_are_present():
    report = risk.build_cross_strategy_risk_report(manager())
    assert report["schema_version"] == "1.0"
    assert report["governance"]["advisory_only"] is True
    assert report["governance"]["automatic_reallocation_allowed"] is False
    assert report["governance"]["investor_approval_required"] is True
