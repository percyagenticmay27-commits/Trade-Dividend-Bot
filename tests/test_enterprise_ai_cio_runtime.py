from __future__ import annotations

from dataclasses import replace

import pytest

from src.dividend_bot.enterprise_ai_cio_runtime import (
    EnterpriseAICIORuntime,
    EnterpriseRecommendation,
    ServiceStatus,
)
from src.dividend_bot.platform_entities import MasterCompanyIntelligenceProfile, new_identity
from src.dividend_bot.platform_foundation import PlatformValidationError


def _profile() -> MasterCompanyIntelligenceProfile:
    profile = MasterCompanyIntelligenceProfile(
        identity=new_identity("MCIP"),
        company_id=new_identity("COM").internal_id,
        income={"score": 75.0},
        risk={"score": 30.0},
        quality_score=80.0,
    )
    profile.validate()
    return profile


def test_runtime_discovers_existing_service_states() -> None:
    states = EnterpriseAICIORuntime().discover_services()
    assert len(states) == 5
    assert all(state.status in set(ServiceStatus) for state in states)


def test_runtime_preserves_valid_advisory_recommendation() -> None:
    result = EnterpriseAICIORuntime().run(
        _profile(),
        evidence_count=3,
        proposed_recommendation="BUY",
        confidence=82.0,
        stability_checked=True,
        rationale="Evidence and stability support review for strategy use.",
    )
    assert result.recommendation is EnterpriseRecommendation.BUY
    assert result.confidence == 82.0


def test_missing_evidence_degrades_to_review() -> None:
    result = EnterpriseAICIORuntime().run(
        _profile(),
        evidence_count=0,
        proposed_recommendation="BUY",
        confidence=90.0,
        stability_checked=True,
        rationale="Original rationale",
    )
    assert result.recommendation is EnterpriseRecommendation.REVIEW
    assert result.confidence <= 50.0


def test_missing_stability_degrades_to_review() -> None:
    result = EnterpriseAICIORuntime().run(
        _profile(),
        evidence_count=2,
        proposed_recommendation="HOLD",
        confidence=70.0,
        stability_checked=False,
        rationale="Original rationale",
    )
    assert result.recommendation is EnterpriseRecommendation.REVIEW


def test_runtime_is_permanently_paper_only() -> None:
    result = EnterpriseAICIORuntime().run(
        _profile(),
        evidence_count=1,
        proposed_recommendation="WATCH",
        confidence=60.0,
        stability_checked=True,
        rationale="Watch pending further evidence.",
    )
    assert result.paper_trade_mode is True
    assert result.live_trading_enabled is False
    assert result.broker_execution_enabled is False


def test_runtime_creates_no_order_or_capital_interface() -> None:
    result = EnterpriseAICIORuntime().run(
        _profile(),
        evidence_count=1,
        proposed_recommendation="WATCH",
        confidence=60.0,
        stability_checked=True,
        rationale="Watch pending further evidence.",
    )
    assert not hasattr(result, "order")
    assert not hasattr(result, "broker_request")
    assert not hasattr(result, "capital_allocation")


def test_runtime_history_is_append_only_snapshot() -> None:
    runtime = EnterpriseAICIORuntime()
    runtime.run(
        _profile(),
        evidence_count=1,
        proposed_recommendation="WATCH",
        confidence=60.0,
        stability_checked=True,
        rationale="First advisory.",
    )
    first = runtime.history()
    runtime.run(
        _profile(),
        evidence_count=2,
        proposed_recommendation="HOLD",
        confidence=70.0,
        stability_checked=True,
        rationale="Second advisory.",
    )
    assert len(first) == 1
    assert len(runtime.history()) == 2


def test_invalid_recommendation_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        EnterpriseAICIORuntime().run(
            _profile(),
            evidence_count=1,
            proposed_recommendation="EXECUTE_NOW",
            confidence=50.0,
            stability_checked=True,
            rationale="Invalid.",
        )


def test_negative_evidence_count_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        EnterpriseAICIORuntime().run(
            _profile(),
            evidence_count=-1,
            proposed_recommendation="REVIEW",
            confidence=50.0,
            stability_checked=True,
            rationale="Invalid evidence count.",
        )


def test_profile_validation_runs_before_decision() -> None:
    invalid = replace(_profile(), quality_score=101.0)
    with pytest.raises(PlatformValidationError):
        EnterpriseAICIORuntime().run(
            invalid,
            evidence_count=1,
            proposed_recommendation="REVIEW",
            confidence=50.0,
            stability_checked=True,
            rationale="Invalid profile.",
        )


def test_json_and_markdown_outputs_include_advisory_boundary() -> None:
    runtime = EnterpriseAICIORuntime()
    result = runtime.run(
        _profile(),
        evidence_count=2,
        proposed_recommendation="DO_NOT_BUY",
        confidence=75.0,
        stability_checked=True,
        rationale="Risk is unacceptable.",
    )
    assert '"recommendation": "DO_NOT_BUY"' in runtime.render_json(result)
    markdown = runtime.render_markdown(result)
    assert "# Enterprise AI CIO Runtime" in markdown
    assert "does not assign capital" in markdown


def test_confidence_out_of_range_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        EnterpriseAICIORuntime().run(
            _profile(),
            evidence_count=1,
            proposed_recommendation="BUY",
            confidence=101.0,
            stability_checked=True,
            rationale="Invalid confidence.",
        )
