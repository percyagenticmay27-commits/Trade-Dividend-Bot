from __future__ import annotations

from dataclasses import replace

import pytest

from src.dividend_bot.enterprise_decision_engine import (
    EnterpriseDecisionAction,
    EnterpriseDecisionEngine,
    EnterpriseDecisionLedger,
    StrategyAdvisory,
)
from src.dividend_bot.enterprise_intelligence_cio_pipeline import EnterpriseIntelligenceCIOPipeline
from src.dividend_bot.enterprise_intelligence_service import EnterpriseIntelligenceProfile
from src.dividend_bot.platform_entities import DecisionState, MasterCompanyIntelligenceProfile, new_identity
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


def _pipeline(*, recommendation: str = "BUY", stable: bool = True, completeness: float = 100.0):
    return EnterpriseIntelligenceCIOPipeline().run(
        _intelligence(completeness=completeness),
        proposed_recommendation=recommendation,
        confidence=82,
        stability_checked=stable,
        rationale="Shared intelligence supports the advisory.",
    )


def _advisory(strategy: str = "DIVIDEND", action: str = "BUY", quality: float = 84.0) -> StrategyAdvisory:
    return StrategyAdvisory(
        strategy_id=strategy,
        action=action,
        confidence=80,
        opportunity_quality=quality,
        rationale="Strategy-specific advisory evidence.",
        service_id=f"{strategy}_ADAPTER",
    )


def test_strategy_advisory_validates() -> None:
    _advisory().validate()


def test_strategy_advisory_rejects_unknown_action() -> None:
    with pytest.raises(PlatformValidationError):
        _advisory(action="MOON").validate()


def test_engine_is_only_canonical_decision_creator() -> None:
    decision = EnterpriseDecisionEngine().create_decision(_pipeline(), (_advisory(),))
    assert decision.action is EnterpriseDecisionAction.BUY
    assert decision.identity.public_id.startswith("DEC-")
    assert decision.state is DecisionState.READY_FOR_CIO


def test_failed_intelligence_gates_force_review() -> None:
    decision = EnterpriseDecisionEngine().create_decision(
        _pipeline(completeness=20),
        (_advisory(),),
    )
    assert decision.action is EnterpriseDecisionAction.REVIEW
    assert decision.state is DecisionState.READY_FOR_REVIEW
    assert decision.confidence <= 50


def test_missing_stability_forces_review() -> None:
    decision = EnterpriseDecisionEngine().create_decision(
        _pipeline(stable=False),
        (_advisory(),),
    )
    assert decision.action is EnterpriseDecisionAction.REVIEW
    assert decision.state is DecisionState.READY_FOR_REVIEW


def test_multiple_strategy_advisories_are_preserved() -> None:
    decision = EnterpriseDecisionEngine().create_decision(
        _pipeline(recommendation="HOLD"),
        (_advisory(), _advisory("SWING", "WATCH", 60)),
    )
    assert [item.strategy_id for item in decision.strategy_advisories] == ["DIVIDEND", "SWING"]
    assert decision.opportunity_quality == 72.0


def test_ledger_is_append_only_tuple_snapshot() -> None:
    ledger = EnterpriseDecisionLedger()
    engine = EnterpriseDecisionEngine(ledger)
    engine.create_decision(_pipeline(), (_advisory(),))
    assert isinstance(ledger.all(), tuple)
    assert len(ledger.all()) == 1


def test_ledger_rejects_duplicate_decision() -> None:
    ledger = EnterpriseDecisionLedger()
    decision = EnterpriseDecisionEngine(ledger).create_decision(_pipeline(), (_advisory(),))
    with pytest.raises(PlatformValidationError):
        ledger.append(decision)


def test_later_decision_links_to_previous_company_decision() -> None:
    ledger = EnterpriseDecisionLedger()
    engine = EnterpriseDecisionEngine(ledger)
    first_pipeline = _pipeline()
    first = engine.create_decision(first_pipeline, (_advisory(),))
    second_pipeline = EnterpriseIntelligenceCIOPipeline().run(
        first_pipeline.intelligence,
        proposed_recommendation="HOLD",
        confidence=70,
        stability_checked=True,
        rationale="Updated evidence supports holding.",
    )
    second = engine.create_decision(second_pipeline, (_advisory(action="HOLD"),))
    assert second.supersedes_decision_id == first.identity.internal_id


def test_json_and_markdown_outputs_are_governed() -> None:
    decision = EnterpriseDecisionEngine().create_decision(_pipeline(), (_advisory(),))
    json_text = EnterpriseDecisionEngine.render_json(decision)
    markdown = EnterpriseDecisionEngine.render_markdown(decision)
    assert '"paper_trade_mode": true' in json_text
    assert "# Enterprise AI CIO Decision" in markdown
    assert "Investor Status: PENDING" in markdown
    assert "does not allocate capital" in markdown


def test_decision_rejects_naive_timestamp() -> None:
    decision = EnterpriseDecisionEngine().create_decision(_pipeline(), (_advisory(),))
    with pytest.raises(PlatformValidationError):
        replace(decision, created_at=decision.created_at.replace(tzinfo=None)).validate()


def test_non_review_decision_requires_stability() -> None:
    decision = EnterpriseDecisionEngine().create_decision(_pipeline(), (_advisory(),))
    with pytest.raises(PlatformValidationError):
        replace(decision, stability_checked=False).validate()


def test_decision_preserves_paper_only_flags() -> None:
    decision = EnterpriseDecisionEngine().create_decision(_pipeline(), (_advisory(),))
    assert decision.paper_trade_mode is True
    assert decision.live_trading_enabled is False
    assert decision.broker_execution_enabled is False


def test_engine_has_no_capital_or_order_interface() -> None:
    engine = EnterpriseDecisionEngine()
    assert not hasattr(engine, "allocate_capital")
    assert not hasattr(engine, "place_order")
    assert not hasattr(engine, "broker_request")
