from pathlib import Path

import pytest

import decision_stability_engine as engine


def base_payload():
    return {
        "current_candidate_id": "AMDW",
        "challenger_candidate_id": "QQQI_TQQQ",
        "current_capital_efficiency_score": 90.0,
        "challenger_capital_efficiency_score": 92.0,
        "current_action": "KEEP",
        "decision_history": [
            {"capital_action": "KEEP", "current_capital_efficiency_score": 90.0, "challenger_capital_efficiency_score": 91.0},
            {"capital_action": "KEEP", "current_capital_efficiency_score": 90.0, "challenger_capital_efficiency_score": 91.5},
            {"capital_action": "KEEP", "current_capital_efficiency_score": 90.0, "challenger_capital_efficiency_score": 92.0},
        ],
        "evidence_confidence": 95.0,
        "market_regime": "BULL",
        "market_regime_history": ["BULL", "BULL", "BULL"],
        "sector_persistence_days": 4,
        "distance_to_sale_threshold": 25.0,
    }


def test_public_functions_exist():
    assert callable(engine.calculate_decision_stability)
    assert callable(engine.build_decision_stability_report)
    assert callable(engine.write_decision_stability)


def test_small_challenger_advantage_keeps_current_strategy():
    report = engine.calculate_decision_stability(**base_payload())
    assert report["recommended_capital_action"] == "KEEP"
    assert report["change_allowed"] is False
    assert "below the required" in report["natural_explanation"]


def test_large_persistent_advantage_can_allow_replacement():
    payload = base_payload()
    payload["challenger_capital_efficiency_score"] = 99.0
    payload["decision_history"] = [
        {"capital_action": "KEEP", "current_capital_efficiency_score": 92, "challenger_capital_efficiency_score": 94},
        {"capital_action": "KEEP", "current_capital_efficiency_score": 90, "challenger_capital_efficiency_score": 96},
        {"capital_action": "KEEP", "current_capital_efficiency_score": 88, "challenger_capital_efficiency_score": 99},
    ]
    payload["distance_to_sale_threshold"] = 2.0
    report = engine.calculate_decision_stability(**payload)
    assert report["challenger_improvement_points"] >= 5
    assert report["persistence_requirement_met"] is True
    assert report["change_allowed"] is True
    assert report["recommended_capital_action"] == "REPLACE"


def test_large_advantage_without_persistence_waits():
    payload = base_payload()
    payload["challenger_capital_efficiency_score"] = 98.0
    payload["decision_history"] = []
    payload["market_regime_history"] = []
    payload["sector_persistence_days"] = 0
    report = engine.calculate_decision_stability(**payload)
    assert report["change_allowed"] is False
    assert report["recommended_capital_action"] == "WAIT"
    assert report["stability_gate"] == "WAIT_FOR_PERSISTENCE"


def test_earnings_lock_authorizes_sgov_parking():
    payload = base_payload()
    payload["earnings_lock"] = True
    report = engine.calculate_decision_stability(**payload)
    assert report["change_allowed"] is True
    assert report["recommended_capital_action"] == "PARK_IN_SGOV"
    assert "earnings lock" in report["natural_explanation"].lower()


def test_hard_risk_breach_overrides_stability():
    payload = base_payload()
    payload["hard_risk_breach"] = True
    report = engine.calculate_decision_stability(**payload)
    assert report["change_allowed"] is True
    assert report["stability_gate"] == "CHANGE_AUTHORIZED_BY_PROTECTION_RULE"


def test_sale_signal_prepares_replacement():
    payload = base_payload()
    payload["sale_signal"] = True
    report = engine.calculate_decision_stability(**payload)
    assert report["recommended_capital_action"] == "PREPARE_REPLACEMENT"
    assert "confirmed sale signal" in report["natural_explanation"].lower()


def test_stale_data_reduces_confidence_component():
    fresh = engine.calculate_decision_stability(**base_payload())
    payload = base_payload()
    payload["stale_data"] = True
    stale = engine.calculate_decision_stability(**payload)
    assert stale["components"]["evidence_confidence"] < fresh["components"]["evidence_confidence"]
    assert stale["warnings"]


def test_score_labels_cover_expected_ranges():
    assert engine._label(95) == "VERY_STABLE"
    assert engine._label(80) == "STABLE"
    assert engine._label(65) == "TRANSITION_WATCH"
    assert engine._label(50) == "UNSTABLE"
    assert engine._label(20) == "CRITICAL"


def test_missing_current_candidate_rejected():
    payload = base_payload()
    payload["current_candidate_id"] = ""
    with pytest.raises(ValueError):
        engine.calculate_decision_stability(**payload)


def test_report_uses_full_score_names_and_natural_explanation():
    report = engine.calculate_decision_stability(**base_payload())
    markdown = engine.format_decision_stability_markdown(report)
    assert "Decision Stability Score" in markdown
    assert "Capital Efficiency" in report["natural_explanation"]
    assert "CES" not in markdown
    assert "DSS" not in markdown


def test_write_outputs(tmp_path: Path):
    report = engine.write_decision_stability(base_payload(), root_path=str(tmp_path))
    assert report["current_candidate_id"] == "AMDW"
    assert (tmp_path / "decision_stability.json").exists()
    assert (tmp_path / "decision_stability.md").exists()


def test_paper_only_flags_are_enforced():
    report = engine.calculate_decision_stability(**base_payload())
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["reporting_only"] is True


def test_source_contains_no_restricted_execution_calls():
    source = Path(engine.__file__).read_text(encoding="utf-8")
    forbidden = ["os.system(", "subprocess.", "place_order(", "execute_trade(", "robin_stocks"]
    for token in forbidden:
        assert token not in source
