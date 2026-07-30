import json
from pathlib import Path

import pytest

from src.dividend_bot import capital_allocation_review_service as service

FIXED_TIME = "2026-07-30T04:40:00Z"


def portfolio(*, safe=True, recommendations=True, blockers=None, warnings=None):
    return {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "recommendations": ([{"strategy_id": "DIVIDEND", "recommended_weight_pct": 70.0}] if recommendations else []),
        "blockers": blockers or [],
        "warnings": warnings or [],
        "governance": {
            "paper_trade_mode": safe,
            "live_trading_enabled": not safe,
            "broker_execution_enabled": not safe,
            "capital_movement_enabled": not safe,
        },
    }


def risk(level="ACCEPTABLE", findings=None):
    return {"overall_risk": level, "findings": findings or []}


def test_safety_constants_are_locked():
    assert service.PAPER_TRADE_MODE is True
    assert service.LIVE_TRADING_ENABLED is False
    assert service.BROKER_EXECUTION_ENABLED is False
    assert service.CAPITAL_MOVEMENT_ENABLED is False
    assert service.AUTOMATIC_APPROVAL_ENABLED is False


def test_acceptable_review_is_approved_for_investor_review():
    review = service.build_capital_allocation_review(portfolio(), risk(), generated_at_utc=FIXED_TIME)
    assert review["decision"] == "APPROVE_FOR_INVESTOR_REVIEW"
    assert review["generated_at_utc"] == FIXED_TIME


def test_watch_risk_is_eligible_by_default():
    review = service.build_capital_allocation_review(portfolio(), risk("WATCH"))
    assert review["decision"] == "APPROVE_FOR_INVESTOR_REVIEW"


def test_high_risk_causes_hold():
    review = service.build_capital_allocation_review(portfolio(), risk("HIGH"))
    assert review["decision"] == "HOLD"


def test_critical_risk_causes_reject():
    review = service.build_capital_allocation_review(portfolio(), risk("CRITICAL"))
    assert review["decision"] == "REJECT"


def test_unsafe_governance_causes_reject():
    review = service.build_capital_allocation_review(portfolio(safe=False), risk())
    assert review["decision"] == "REJECT"
    assert review["summary"]["paper_safe"] is False


def test_portfolio_blocker_causes_hold():
    review = service.build_capital_allocation_review(portfolio(blockers=["enterprise degraded"]), risk())
    assert review["decision"] == "HOLD"


def test_missing_recommendations_causes_hold():
    review = service.build_capital_allocation_review(portfolio(recommendations=False), risk())
    assert review["decision"] == "HOLD"


def test_policy_can_allow_no_recommendations():
    review = service.build_capital_allocation_review(
        portfolio(recommendations=False), risk(), review_policy={"require_recommendations": False}
    )
    assert review["decision"] == "APPROVE_FOR_INVESTOR_REVIEW"


def test_critical_finding_causes_reject():
    review = service.build_capital_allocation_review(
        portfolio(), risk("WATCH", [{"severity": "CRITICAL", "message": "unsafe concentration"}])
    )
    assert review["decision"] == "REJECT"


def test_high_finding_causes_hold_by_default():
    review = service.build_capital_allocation_review(
        portfolio(), risk("WATCH", [{"severity": "HIGH", "message": "high concentration"}])
    )
    assert review["decision"] == "HOLD"


def test_governance_never_creates_request_or_moves_capital():
    review = service.build_capital_allocation_review(portfolio(), risk())
    governance = review["governance"]
    assert governance["creates_allocation_request"] is False
    assert governance["automatic_activation_allowed"] is False
    assert governance["order_execution_allowed"] is False
    assert governance["brokerage_communication_allowed"] is False
    assert governance["capital_movement_allowed"] is False
    assert governance["allocation_request_owner"] == "paper_capital_allocation.py"


def test_missing_required_input_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        service.build_review_from_files(tmp_path / "missing.json", tmp_path / "risk.json")


def test_invalid_required_input_raises(tmp_path):
    bad = tmp_path / "bad.json"
    good = tmp_path / "risk.json"
    bad.write_text("not json", encoding="utf-8")
    good.write_text(json.dumps(risk()), encoding="utf-8")
    with pytest.raises(ValueError):
        service.build_review_from_files(bad, good)


def test_json_and_markdown_outputs(tmp_path):
    review = service.build_capital_allocation_review(portfolio(), risk(), generated_at_utc=FIXED_TIME)
    json_path = tmp_path / "results/capital_allocation_review.json"
    md_path = tmp_path / "results/capital_allocation_review.md"
    service.write_capital_allocation_review_json(review, json_path)
    service.write_capital_allocation_review_markdown(review, md_path)
    assert json.loads(json_path.read_text(encoding="utf-8"))["decision"] == "APPROVE_FOR_INVESTOR_REVIEW"
    markdown = md_path.read_text(encoding="utf-8")
    assert "# Capital Allocation Review" in markdown
    assert "Investor approval required" in markdown


def test_standard_output_names(tmp_path):
    manager = tmp_path / "ai_cio_portfolio_manager.json"
    risk_path = tmp_path / "cross_strategy_risk.json"
    manager.write_text(json.dumps(portfolio()), encoding="utf-8")
    risk_path.write_text(json.dumps(risk()), encoding="utf-8")
    outputs = service.build_and_write_capital_allocation_review(manager, risk_path, tmp_path / "results")
    assert Path(outputs["json"]).name == "capital_allocation_review.json"
    assert Path(outputs["markdown"]).name == "capital_allocation_review.md"


def test_schema_and_metadata_are_present():
    review = service.build_capital_allocation_review(portfolio(), risk())
    assert review["module_name"] == service.MODULE_NAME
    assert review["module_version"] == service.MODULE_VERSION
    assert review["schema_version"] == service.SCHEMA_VERSION
    assert set(review["decision_allowed_values"]) == service.ALLOWED_DECISIONS
