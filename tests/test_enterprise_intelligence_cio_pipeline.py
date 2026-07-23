from __future__ import annotations

from dataclasses import replace

import pytest

from src.dividend_bot.enterprise_ai_cio_runtime import EnterpriseRecommendation
from src.dividend_bot.enterprise_intelligence_cio_pipeline import (
    EnterpriseIntelligenceCIOPipeline,
    IntelligenceCIOPipelineResult,
    IntelligenceCIOPolicy,
)
from src.dividend_bot.enterprise_intelligence_service import EnterpriseIntelligenceProfile
from src.dividend_bot.platform_entities import MasterCompanyIntelligenceProfile, new_identity
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now


def _intelligence(*, completeness: float = 100.0, quality: float = 80.0, evidence: int = 3) -> EnterpriseIntelligenceProfile:
    profile = MasterCompanyIntelligenceProfile(
        identity=new_identity("MCIP"),
        company_id=new_identity("COM").internal_id,
        fundamentals={"score": 80},
        income={"score": 75},
        financial_health={"score": 80},
        risk={"score": 30},
        market_intelligence={"score": 70},
        technical={"score": 65},
        earnings={"days": 20},
        quality_score=quality,
    )
    profile.validate()
    result = EnterpriseIntelligenceProfile(
        generated_at=utc_now(),
        profile=profile,
        completeness_score=completeness,
        quality_score=quality,
        contributing_services=("FUNDAMENTALS", "RISK"),
        missing_sections=(),
        evidence_count=evidence,
    )
    result.validate()
    return result


def test_policy_defaults_validate() -> None:
    IntelligenceCIOPolicy().validate()


def test_policy_rejects_invalid_completeness() -> None:
    with pytest.raises(PlatformValidationError):
        IntelligenceCIOPolicy(minimum_completeness_score=101).validate()


def test_policy_rejects_invalid_quality() -> None:
    with pytest.raises(PlatformValidationError):
        IntelligenceCIOPolicy(minimum_quality_score=-1).validate()


def test_policy_rejects_negative_evidence_requirement() -> None:
    with pytest.raises(PlatformValidationError):
        IntelligenceCIOPolicy(minimum_evidence_count=-1).validate()


def test_ready_intelligence_preserves_proposed_advisory() -> None:
    result = EnterpriseIntelligenceCIOPipeline().run(
        _intelligence(),
        proposed_recommendation="BUY",
        confidence=82,
        stability_checked=True,
        rationale="Strong shared intelligence.",
    )
    assert result.gates_passed is True
    assert result.gate_failures == ()
    assert result.advisory.recommendation is EnterpriseRecommendation.BUY


def test_low_completeness_forces_review() -> None:
    result = EnterpriseIntelligenceCIOPipeline().run(
        _intelligence(completeness=50),
        proposed_recommendation="BUY",
        confidence=90,
        stability_checked=True,
        rationale="Proposed buy.",
    )
    assert result.gates_passed is False
    assert result.advisory.recommendation is EnterpriseRecommendation.REVIEW
    assert "completeness" in result.gate_failures[0]


def test_low_quality_forces_review() -> None:
    result = EnterpriseIntelligenceCIOPipeline().run(
        _intelligence(quality=40),
        proposed_recommendation="HOLD",
        confidence=70,
        stability_checked=True,
        rationale="Proposed hold.",
    )
    assert result.advisory.recommendation is EnterpriseRecommendation.REVIEW
    assert any("quality" in item for item in result.gate_failures)


def test_missing_evidence_forces_review() -> None:
    result = EnterpriseIntelligenceCIOPipeline().run(
        _intelligence(evidence=0),
        proposed_recommendation="BUY",
        confidence=88,
        stability_checked=True,
        rationale="Proposed buy.",
    )
    assert result.advisory.recommendation is EnterpriseRecommendation.REVIEW
    assert any("evidence count" in item for item in result.gate_failures)


def test_stability_is_still_required_after_gates_pass() -> None:
    result = EnterpriseIntelligenceCIOPipeline().run(
        _intelligence(),
        proposed_recommendation="BUY",
        confidence=88,
        stability_checked=False,
        rationale="Proposed buy.",
    )
    assert result.gates_passed is True
    assert result.advisory.recommendation is EnterpriseRecommendation.REVIEW


def test_pipeline_history_is_append_only_snapshot() -> None:
    pipeline = EnterpriseIntelligenceCIOPipeline()
    pipeline.run(
        _intelligence(),
        proposed_recommendation="WATCH",
        confidence=60,
        stability_checked=True,
        rationale="Watch.",
    )
    history = pipeline.history()
    assert isinstance(history, tuple)
    assert len(history) == 1


def test_result_requires_timezone_aware_completed_at() -> None:
    result = EnterpriseIntelligenceCIOPipeline().run(
        _intelligence(),
        proposed_recommendation="HOLD",
        confidence=70,
        stability_checked=True,
        rationale="Hold.",
    )
    invalid = replace(result, completed_at=result.completed_at.replace(tzinfo=None))
    with pytest.raises(PlatformValidationError):
        invalid.validate()


def test_result_rejects_failed_gates_with_non_review() -> None:
    result = EnterpriseIntelligenceCIOPipeline().run(
        _intelligence(completeness=10),
        proposed_recommendation="BUY",
        confidence=90,
        stability_checked=True,
        rationale="Buy.",
    )
    invalid = replace(
        result,
        advisory=replace(result.advisory, recommendation=EnterpriseRecommendation.BUY),
    )
    with pytest.raises(PlatformValidationError):
        invalid.validate()


def test_pipeline_has_no_capital_or_order_interface() -> None:
    pipeline = EnterpriseIntelligenceCIOPipeline()
    assert not hasattr(pipeline, "allocate_capital")
    assert not hasattr(pipeline, "place_order")
    assert not hasattr(pipeline, "broker_request")


def test_result_preserves_paper_only_flags() -> None:
    result = EnterpriseIntelligenceCIOPipeline().run(
        _intelligence(),
        proposed_recommendation="HOLD",
        confidence=70,
        stability_checked=True,
        rationale="Hold.",
    )
    assert result.paper_trade_mode is True
    assert result.live_trading_enabled is False
    assert result.broker_execution_enabled is False
