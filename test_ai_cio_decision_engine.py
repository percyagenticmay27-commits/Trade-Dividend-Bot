from pathlib import Path

import pytest

import ai_cio_decision_engine as engine


def base_payload():
    return {
        "current_candidate_id": "AMDW + PLTU",
        "challenger_candidate_id": "AMDW + GGLL",
        "current_capital_efficiency_score": 84.3,
        "challenger_capital_efficiency_score": 86.3,
        "decision_stability": {
            "recommended_capital_action": "KEEP",
            "change_allowed": False,
            "stability_gate": "KEEP_CURRENT",
            "decision_stability_score": 82.7,
            "decision_stability_label": "STABLE",
        },
        "evidence_confidence": 94.0,
        "market_regime": "BULL",
        "challenger_qualified": True,
        "investment_policy_compliant": True,
        "autonomy_level": "LEVEL_1_ADVISOR",
    }


def test_public_functions_exist():
    assert callable(engine.build_ai_cio_decision)
    assert callable(engine.format_ai_cio_decision_markdown)
    assert callable(engine.write_ai_cio_decision)


def test_small_advantage_keeps_current_allocation():
    report = engine.build_ai_cio_decision(**base_payload())
    assert report["final_capital_action"] == "KEEP"
    assert "Continue holding AMDW + PLTU" in report["ai_cio_verdict"]
    assert "Capital Efficiency Score" in report["ai_cio_verdict"]
    assert report["policy_action_allowed"] is True


def test_stability_authorized_replacement():
    payload = base_payload()
    payload["challenger_capital_efficiency_score"] = 92.0
    payload["decision_stability"] = {
        "recommended_capital_action": "REPLACE",
        "change_allowed": True,
        "stability_gate": "CHANGE_ALLOWED",
        "decision_stability_score": 52.0,
        "decision_stability_label": "UNSTABLE",
    }
    report = engine.build_ai_cio_decision(**payload)
    assert report["final_capital_action"] == "REPLACE"
    assert report["decision_reason"] == "STABILITY_AUTHORIZED_REPLACEMENT"
    assert "Replace AMDW + PLTU with AMDW + GGLL" in report["ai_cio_verdict"]


def test_earnings_lock_parks_affected_capital_in_sgov():
    payload = base_payload()
    payload["earnings_lock"] = True
    report = engine.build_ai_cio_decision(**payload)
    assert report["final_capital_action"] == "PARK_IN_SGOV"
    assert "EARNINGS_LOCK" in report["protection_reasons"]
    assert "SGOV" in report["ai_cio_verdict"]


def test_hard_risk_breach_overrides_normal_stability():
    payload = base_payload()
    payload["hard_risk_breach"] = True
    report = engine.build_ai_cio_decision(**payload)
    assert report["final_capital_action"] == "PARK_IN_SGOV"
    assert report["decision_reason"] == "HARD_RISK_BREACH"


def test_sale_signal_prepares_replacement():
    payload = base_payload()
    payload["sale_signal"] = True
    report = engine.build_ai_cio_decision(**payload)
    assert report["final_capital_action"] == "PREPARE_REPLACEMENT"
    assert "confirmed sale condition" in report["ai_cio_verdict"].lower()


def test_invalid_market_data_parks_capital():
    payload = base_payload()
    payload["invalid_market_data"] = True
    report = engine.build_ai_cio_decision(**payload)
    assert report["final_capital_action"] == "PARK_IN_SGOV"
    assert "INVALID_MARKET_DATA" in report["protection_reasons"]


def test_low_confidence_waits():
    payload = base_payload()
    payload["evidence_confidence"] = 45.0
    report = engine.build_ai_cio_decision(**payload)
    assert report["final_capital_action"] == "WAIT"
    assert report["decision_reason"] == "LOW_ANALYSIS_CONFIDENCE"


def test_policy_block_prevents_discretionary_change():
    payload = base_payload()
    payload["investment_policy_compliant"] = False
    payload["decision_stability"] = {
        "recommended_capital_action": "REPLACE",
        "change_allowed": True,
        "stability_gate": "CHANGE_ALLOWED",
        "decision_stability_score": 40.0,
        "decision_stability_label": "UNSTABLE",
    }
    report = engine.build_ai_cio_decision(**payload)
    assert report["final_capital_action"] == "WAIT"
    assert report["policy_action_allowed"] is False
    assert report["warnings"]


def test_reentry_from_sgov_requires_eligibility_and_stability():
    payload = base_payload()
    payload["current_candidate_id"] = "SGOV"
    payload["challenger_candidate_id"] = "AMDW + GGLL"
    payload["reentry_eligible"] = True
    payload["decision_stability"] = {
        "recommended_capital_action": "REENTER",
        "change_allowed": True,
        "stability_gate": "CHANGE_ALLOWED",
        "decision_stability_score": 55.0,
        "decision_stability_label": "UNSTABLE",
    }
    report = engine.build_ai_cio_decision(**payload)
    assert report["final_capital_action"] == "REENTER"
    assert "Re-enter capital from SGOV" in report["ai_cio_verdict"]


def test_increase_and_reduce_actions_supported():
    increase_payload = base_payload()
    increase_payload["increase_supported"] = True
    increase = engine.build_ai_cio_decision(**increase_payload)
    assert increase["final_capital_action"] == "INCREASE"

    reduce_payload = base_payload()
    reduce_payload["reduce_supported"] = True
    reduce = engine.build_ai_cio_decision(**reduce_payload)
    assert reduce["final_capital_action"] == "REDUCE"


def test_autonomy_level_controls_automatic_paper_authority():
    advisor = engine.build_ai_cio_decision(**base_payload())
    assert advisor["automatic_paper_action_authorized"] is False

    payload = base_payload()
    payload["autonomy_level"] = "LEVEL_3_AUTONOMOUS_CIO"
    autonomous = engine.build_ai_cio_decision(**payload)
    assert autonomous["automatic_paper_action_authorized"] is True
    assert autonomous["investor_override_available"] is True


def test_markdown_uses_full_investor_facing_names():
    report = engine.build_ai_cio_decision(**base_payload())
    markdown = engine.format_ai_cio_decision_markdown(report)
    assert "AI CIO Verdict" in markdown
    assert "Compare Candidates" in markdown
    assert "Capital Efficiency Score" in markdown
    assert "Decision Stability Score" in markdown
    assert "Evidence Confidence" in markdown
    assert "CES" not in markdown
    assert "DSS" not in markdown


def test_write_outputs(tmp_path: Path):
    report = engine.write_ai_cio_decision(base_payload(), root_path=str(tmp_path))
    assert report["final_capital_action"] == "KEEP"
    assert (tmp_path / "ai_cio_decision.json").exists()
    assert (tmp_path / "ai_cio_decision.md").exists()


def test_missing_current_candidate_rejected():
    payload = base_payload()
    payload["current_candidate_id"] = ""
    with pytest.raises(ValueError):
        engine.build_ai_cio_decision(**payload)


def test_paper_only_flags_are_enforced():
    report = engine.build_ai_cio_decision(**base_payload())
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["reporting_only"] is True


def test_source_contains_no_restricted_execution_calls():
    source = Path(engine.__file__).read_text(encoding="utf-8")
    forbidden = ["os.system(", "subprocess.", "place_order(", "execute_trade(", "robin_stocks"]
    for token in forbidden:
        assert token not in source
