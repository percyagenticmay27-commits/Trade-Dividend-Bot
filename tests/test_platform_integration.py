from __future__ import annotations

from dataclasses import replace

import pytest

from src.dividend_bot.platform_entities import MasterCompanyIntelligenceProfile, new_identity
from src.dividend_bot.platform_foundation import PlatformValidationError
from src.dividend_bot.platform_integration import (
    DividendPlatformPaperCycle,
    MCIPIntegrationService,
    PlatformServiceDefinition,
    PlatformServiceRegistry,
    ServiceDomain,
    build_default_service_registry,
)


def _profile() -> MasterCompanyIntelligenceProfile:
    profile = MasterCompanyIntelligenceProfile(
        identity=new_identity("MCIP"),
        company_id=new_identity("COM").internal_id,
        income={"score": 40.0},
        risk={"score": 70.0},
        quality_score=40.0,
    )
    profile.validate()
    return profile


def test_service_definition_requires_strategy_neutrality() -> None:
    definition = PlatformServiceDefinition(
        "BAD",
        ServiceDomain.RISK,
        "src.dividend_bot.example",
        strategy_neutral=False,
    )
    with pytest.raises(PlatformValidationError):
        definition.validate()


def test_registry_rejects_conflicting_registration() -> None:
    registry = PlatformServiceRegistry()
    first = PlatformServiceDefinition("RISK", ServiceDomain.RISK, "src.dividend_bot.risk_a")
    second = PlatformServiceDefinition("RISK", ServiceDomain.RISK, "src.dividend_bot.risk_b")
    registry.register(first)
    with pytest.raises(PlatformValidationError):
        registry.register(second)


def test_default_registry_contains_existing_engine_adapters() -> None:
    ids = {item.service_id for item in build_default_service_registry().list_definitions()}
    assert {"DISCOVERY", "MARKET_INTELLIGENCE", "EARNINGS", "AI_CIO", "LEARNING"} <= ids


def test_apply_section_returns_new_immutable_profile() -> None:
    original = _profile()
    revised = MCIPIntegrationService.apply_section(
        original,
        ServiceDomain.INCOME,
        {"score": 80.0, "yield": 4.2},
        quality_score=75.0,
    )
    assert revised is not original
    assert original.income["score"] == 40.0
    assert revised.income["score"] == 80.0
    assert revised.quality_score == 75.0


def test_apply_section_rejects_non_mcip_domain() -> None:
    with pytest.raises(PlatformValidationError):
        MCIPIntegrationService.apply_section(_profile(), ServiceDomain.PORTFOLIO, {"score": 50})


def test_apply_section_preserves_mcip_strategy_neutrality() -> None:
    with pytest.raises(PlatformValidationError):
        MCIPIntegrationService.apply_section(
            _profile(),
            ServiceDomain.INCOME,
            {"decision": "BUY"},
        )


def test_apply_batch_updates_multiple_sections() -> None:
    revised = MCIPIntegrationService.apply_batch(
        _profile(),
        {
            ServiceDomain.INCOME: {"score": 85.0},
            ServiceDomain.RISK: {"score": 30.0},
            ServiceDomain.EARNINGS: {"days_to_earnings": 25},
        },
        quality_score=80.0,
    )
    assert revised.income["score"] == 85.0
    assert revised.risk["score"] == 30.0
    assert revised.earnings["days_to_earnings"] == 25
    assert revised.quality_score == 80.0


def test_dividend_paper_cycle_uses_shared_mcip_and_returns_dividend_result() -> None:
    result = DividendPlatformPaperCycle().run(
        _profile(),
        {
            ServiceDomain.INCOME: {"score": 85.0},
            ServiceDomain.RISK: {"score": 25.0},
        },
        quality_score=85.0,
    )
    assert result.dividend_result.recommendation.strategy_id == "DIVIDEND"
    assert result.dividend_result.recommendation.paper_action == "REVIEW_FOR_PAPER_BUY"
    assert result.completed_steps[-1] == "PAPER_ONLY_COMPLETE"


def test_dividend_paper_cycle_does_not_create_live_order() -> None:
    result = DividendPlatformPaperCycle().run(
        _profile(),
        {ServiceDomain.INCOME: {"score": 90.0}, ServiceDomain.RISK: {"score": 10.0}},
        quality_score=90.0,
    )
    assert not hasattr(result, "order")
    assert not hasattr(result, "broker_request")


def test_profile_validation_still_runs_after_batch() -> None:
    invalid = replace(_profile(), quality_score=101.0)
    with pytest.raises(PlatformValidationError):
        MCIPIntegrationService.apply_batch(invalid, {})
