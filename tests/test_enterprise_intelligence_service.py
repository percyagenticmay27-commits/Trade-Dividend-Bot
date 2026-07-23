from __future__ import annotations

from dataclasses import replace

import pytest

from src.dividend_bot.enterprise_intelligence_service import (
    EnterpriseIntelligenceService,
    IntelligenceContribution,
)
from src.dividend_bot.platform_entities import MasterCompanyIntelligenceProfile, new_identity
from src.dividend_bot.platform_foundation import PlatformValidationError
from src.dividend_bot.platform_integration import ServiceDomain


def _profile() -> MasterCompanyIntelligenceProfile:
    profile = MasterCompanyIntelligenceProfile(
        identity=new_identity("MCIP"),
        company_id=new_identity("COM").internal_id,
        fundamentals={"score": 70.0},
        income={"score": 75.0},
        quality_score=80.0,
    )
    profile.validate()
    return profile


def test_build_preserves_existing_intelligence() -> None:
    result = EnterpriseIntelligenceService().build(
        _profile(),
        (IntelligenceContribution("RISK_ENGINE", ServiceDomain.RISK, {"score": 30.0}),),
    )
    assert result.profile.fundamentals["score"] == 70.0
    assert result.profile.risk["score"] == 30.0


def test_duplicate_domains_are_rejected() -> None:
    contributions = (
        IntelligenceContribution("RISK_A", ServiceDomain.RISK, {"score": 30.0}),
        IntelligenceContribution("RISK_B", ServiceDomain.RISK, {"score": 35.0}),
    )
    with pytest.raises(PlatformValidationError):
        EnterpriseIntelligenceService().build(_profile(), contributions)


def test_missing_sections_are_reported() -> None:
    result = EnterpriseIntelligenceService().build(_profile(), ())
    assert "risk" in result.missing_sections
    assert result.completeness_score < 100.0


def test_complete_profile_scores_100_percent() -> None:
    contributions = (
        IntelligenceContribution("HEALTH", ServiceDomain.FINANCIAL_HEALTH, {"score": 80.0}),
        IntelligenceContribution("RISK", ServiceDomain.RISK, {"score": 20.0}),
        IntelligenceContribution("MARKET", ServiceDomain.MARKET_INTELLIGENCE, {"score": 70.0}),
        IntelligenceContribution("TECHNICAL", ServiceDomain.TECHNICAL, {"score": 65.0}),
        IntelligenceContribution("EARNINGS", ServiceDomain.EARNINGS, {"days": 20}),
    )
    result = EnterpriseIntelligenceService().build(_profile(), contributions)
    assert result.completeness_score == 100.0
    assert not result.missing_sections


def test_strategy_owned_keys_are_rejected() -> None:
    contribution = IntelligenceContribution("BAD", ServiceDomain.RISK, {"decision": "BUY"})
    with pytest.raises(PlatformValidationError):
        EnterpriseIntelligenceService().build(_profile(), (contribution,))


def test_invalid_profile_quality_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        EnterpriseIntelligenceService().build(replace(_profile(), quality_score=101.0), ())


def test_negative_evidence_count_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        EnterpriseIntelligenceService().build(_profile(), (), evidence_count=-1)


def test_zero_evidence_adds_warning() -> None:
    result = EnterpriseIntelligenceService().build(_profile(), (), evidence_count=0)
    assert any("No evidence" in warning for warning in result.warnings)


def test_json_output_is_deterministic() -> None:
    service = EnterpriseIntelligenceService()
    result = service.build(_profile(), ())
    assert service.render_json(result) == service.render_json(result)


def test_markdown_contains_required_sections() -> None:
    result = EnterpriseIntelligenceService().build(_profile(), ())
    markdown = EnterpriseIntelligenceService.render_markdown(result)
    assert "# Enterprise Intelligence Report" in markdown
    assert "## Available Intelligence" in markdown
    assert "## Missing Intelligence" in markdown
    assert "## Advisory Boundary" in markdown


def test_service_registry_is_preserved() -> None:
    result = EnterpriseIntelligenceService().build(
        _profile(),
        (IntelligenceContribution("RISK_ENGINE", ServiceDomain.RISK, {"score": 25.0}),),
    )
    assert result.contributing_services == ("RISK_ENGINE",)


def test_result_remains_paper_only() -> None:
    result = EnterpriseIntelligenceService().build(_profile(), ())
    assert result.paper_trade_mode is True
    assert result.live_trading_enabled is False
    assert result.broker_execution_enabled is False


def test_no_recommendation_interface_exists() -> None:
    result = EnterpriseIntelligenceService().build(_profile(), ())
    assert not hasattr(result, "recommendation")
    assert not hasattr(result, "paper_action")


def test_no_capital_or_order_interface_exists() -> None:
    result = EnterpriseIntelligenceService().build(_profile(), ())
    assert not hasattr(result, "allocation")
    assert not hasattr(result, "order")
    assert not hasattr(result, "broker_request")


def test_generated_timestamps_are_timezone_aware() -> None:
    result = EnterpriseIntelligenceService().build(_profile(), ())
    assert result.generated_at.tzinfo is not None
    assert result.profile.refreshed_at.tzinfo is not None


def test_contribution_requires_uppercase_service_id() -> None:
    contribution = IntelligenceContribution("risk", ServiceDomain.RISK, {"score": 25.0})
    with pytest.raises(PlatformValidationError):
        contribution.validate()
