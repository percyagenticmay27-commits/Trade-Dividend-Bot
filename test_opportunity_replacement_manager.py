from pathlib import Path

import opportunity_replacement_manager as module


def _base_payload():
    return {
        "current_candidate_id": "AMDW + PLTU",
        "challenger_candidate_id": "AMDW + GGLL",
        "current_capital_efficiency_score": 84.3,
        "challenger_capital_efficiency_score": 93.1,
        "decision_stability_score": 80.0,
        "decision_stability_label": "STABLE",
        "change_allowed_by_stability": True,
        "evidence_confidence": 92.0,
        "challenger_persistence_days": 7,
        "minimum_score_improvement": 5.0,
        "minimum_persistence_days": 3,
        "challenger_qualified": True,
        "investment_policy_compliant": True,
        "current_lifecycle_state": "ACTIVE",
        "current_replacement_eligible": True,
    }


def test_public_functions_exist():
    for name in (
        "build_opportunity_replacement",
        "format_opportunity_replacement_markdown",
        "write_opportunity_replacement",
        "build_and_write_opportunity_replacement",
    ):
        assert callable(getattr(module, name))


def test_paper_only_flags_are_enforced():
    report = module.build_opportunity_replacement(**_base_payload())
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["reporting_only"] is True


def test_strong_persistent_challenger_earns_replacement():
    report = module.build_opportunity_replacement(**_base_payload())
    assert report["recommendation"] == "REPLACE_CURRENT"
    assert report["decision_reason"] == "CHALLENGER_EARNED_REPLACEMENT"


def test_small_improvement_keeps_current():
    payload = _base_payload()
    payload["challenger_capital_efficiency_score"] = 86.0
    report = module.build_opportunity_replacement(**payload)
    assert report["recommendation"] == "KEEP_CURRENT"


def test_large_but_new_improvement_waits_for_persistence():
    payload = _base_payload()
    payload["challenger_persistence_days"] = 1
    report = module.build_opportunity_replacement(**payload)
    assert report["recommendation"] == "WAIT_FOR_PERSISTENCE"


def test_decision_stability_can_block_replacement():
    payload = _base_payload()
    payload["change_allowed_by_stability"] = False
    report = module.build_opportunity_replacement(**payload)
    assert report["recommendation"] == "WAIT_FOR_PERSISTENCE"


def test_unqualified_challenger_cannot_replace():
    payload = _base_payload()
    payload["challenger_qualified"] = False
    report = module.build_opportunity_replacement(**payload)
    assert report["recommendation"] == "KEEP_CURRENT"


def test_policy_noncompliance_blocks_replacement():
    payload = _base_payload()
    payload["investment_policy_compliant"] = False
    report = module.build_opportunity_replacement(**payload)
    assert report["recommendation"] == "KEEP_CURRENT"


def test_earnings_lock_parks_current_in_sgov():
    payload = _base_payload()
    payload["current_earnings_lock"] = True
    report = module.build_opportunity_replacement(**payload)
    assert report["recommendation"] == "PARK_CURRENT_IN_SGOV"
    assert report["protection_reason"] == "EARNINGS_LOCK"


def test_sale_signal_prepares_safe_replacement():
    payload = _base_payload()
    payload["current_sale_signal"] = True
    report = module.build_opportunity_replacement(**payload)
    assert report["recommendation"] == "PREPARE_REPLACEMENT"


def test_sale_signal_without_safe_challenger_parks_in_sgov():
    payload = _base_payload()
    payload["current_sale_signal"] = True
    payload["challenger_stale_data"] = True
    report = module.build_opportunity_replacement(**payload)
    assert report["recommendation"] == "PARK_CURRENT_IN_SGOV"


def test_no_challenger_is_reported_cleanly():
    payload = _base_payload()
    payload["challenger_candidate_id"] = ""
    report = module.build_opportunity_replacement(**payload)
    assert report["recommendation"] == "NO_QUALIFIED_CHALLENGER"
    assert report["challenger_candidate_id"] is None


def test_sector_context_does_not_create_entitlement():
    payload = _base_payload()
    payload["sector_context_current"] = "WEAK"
    payload["sector_context_challenger"] = "STRONG"
    payload["challenger_capital_efficiency_score"] = 85.0
    report = module.build_opportunity_replacement(**payload)
    assert report["sector_allocation_entitlement_used"] is False
    assert report["recommendation"] == "KEEP_CURRENT"


def test_same_underlying_concentration_blocks_replacement():
    payload = _base_payload()
    payload["same_underlying_concentration"] = True
    report = module.build_opportunity_replacement(**payload)
    assert report["recommendation"] != "REPLACE_CURRENT"
    assert "concentration_risk_clear" in report["replacement_blockers"]


def test_markdown_uses_full_investor_facing_names():
    report = module.build_opportunity_replacement(**_base_payload())
    markdown = module.format_opportunity_replacement_markdown(report)
    assert "Capital Efficiency Score" in markdown
    assert "Decision Stability Score" in markdown
    assert "Evidence Confidence" in markdown
    assert "Sector context is supporting evidence only" in markdown


def test_outputs_are_created(tmp_path: Path):
    report = module.write_opportunity_replacement(_base_payload(), root_path=str(tmp_path))
    assert report["recommendation"] == "REPLACE_CURRENT"
    assert (tmp_path / "opportunity_replacement.json").exists()
    assert (tmp_path / "opportunity_replacement.md").exists()
    assert (tmp_path / "opportunity_replacement.html").exists()


def test_invalid_current_candidate_is_rejected():
    payload = _base_payload()
    payload["current_candidate_id"] = ""
    try:
        module.build_opportunity_replacement(**payload)
    except ValueError as exc:
        assert "current_candidate_id" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_non_finite_values_are_safely_normalized():
    payload = _base_payload()
    payload["current_capital_efficiency_score"] = float("nan")
    payload["challenger_capital_efficiency_score"] = float("inf")
    report = module.build_opportunity_replacement(**payload)
    assert report["current_capital_efficiency_score"] == 0.0
    assert report["challenger_capital_efficiency_score"] == 0.0


def test_source_contains_no_restricted_execution_calls():
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = ("place_order(", "execute_trade(", "robin_stocks", "subprocess.", "os.system(")
    assert not any(term in source for term in forbidden)
