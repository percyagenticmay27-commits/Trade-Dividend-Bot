from dataclasses import fields

import pytest

from src.dividend_bot.platform_entities import (
    AICIODecision,
    Asset,
    AuditFinding,
    AuditRun,
    Company,
    DecisionState,
    EvidenceRecord,
    FindingStatus,
    LearningRecord,
    MasterCompanyIntelligenceProfile,
    Position,
    PositionStatus,
    ReportInstance,
    StrategyEvaluation,
    StrategyRecommendation,
    new_identity,
)
from src.dividend_bot.platform_foundation import IdentifierKind, JsonSerializer, PlatformValidationError, utc_now


def make_company() -> Company:
    company = Company(
        identity=new_identity(IdentifierKind.COMPANY),
        symbol="AMD",
        legal_name="Advanced Micro Devices, Inc.",
        display_name="AMD",
        exchange="NASDAQ",
        sector="Technology",
        industry="Semiconductors",
    )
    company.validate()
    return company


def test_company_and_asset_validate() -> None:
    company = make_company()
    asset = Asset(
        identity=new_identity("AST"),
        symbol="AMD",
        instrument_type="EQUITY",
        exchange="NASDAQ",
        company_id=company.identity.internal_id,
    )
    asset.validate()


def test_company_rejects_lowercase_symbol() -> None:
    company = Company(
        identity=new_identity(IdentifierKind.COMPANY),
        symbol="amd",
        legal_name="Advanced Micro Devices, Inc.",
        display_name="AMD",
        exchange="NASDAQ",
    )
    with pytest.raises(PlatformValidationError):
        company.validate()


def test_mcip_is_strategy_neutral() -> None:
    company = make_company()
    profile = MasterCompanyIntelligenceProfile(
        identity=new_identity(IdentifierKind.PROFILE),
        company_id=company.identity.internal_id,
        fundamentals={"revenue_growth": 12.5},
        technical={"rsi": 54.0},
        quality_score=88.0,
    )
    profile.validate()
    field_names = {item.name for item in fields(profile)}
    assert "strategy_id" not in field_names
    assert "decision" not in field_names


def test_mcip_rejects_strategy_owned_keys() -> None:
    company = make_company()
    profile = MasterCompanyIntelligenceProfile(
        identity=new_identity(IdentifierKind.PROFILE),
        company_id=company.identity.internal_id,
        technical={"entry": 150.0},
    )
    with pytest.raises(PlatformValidationError):
        profile.validate()


def test_evidence_quality_bounds() -> None:
    company = make_company()
    evidence = EvidenceRecord(
        identity=new_identity(IdentifierKind.EVIDENCE),
        subject_type="COMPANY",
        subject_id=company.identity.internal_id,
        evidence_type="EARNINGS",
        source="SEC filing",
        summary="Quarterly results",
        quality_score=101.0,
        observed_at=utc_now(),
    )
    with pytest.raises(PlatformValidationError):
        evidence.validate()


def test_strategy_evaluation_and_recommendation_remain_attributed() -> None:
    company = make_company()
    profile = MasterCompanyIntelligenceProfile(
        identity=new_identity(IdentifierKind.PROFILE),
        company_id=company.identity.internal_id,
    )
    evaluation = StrategyEvaluation(
        identity=new_identity("EVA"),
        strategy_id="dividend",
        company_id=company.identity.internal_id,
        profile_id=profile.identity.internal_id,
        score=84.0,
        rationale="Income durability and balance-sheet quality are acceptable.",
    )
    evaluation.validate()
    recommendation = StrategyRecommendation(
        identity=new_identity("REC"),
        strategy_id="dividend",
        evaluation_id=evaluation.identity.internal_id,
        paper_action="WATCH",
        rationale="Await a better yield entry.",
        confidence=80.0,
    )
    recommendation.validate()
    assert recommendation.strategy_id == "dividend"


def test_ai_cio_decision_is_paper_action_and_strategy_attributed() -> None:
    recommendation_id = new_identity("REC").internal_id
    decision = AICIODecision(
        identity=new_identity(IdentifierKind.DECISION),
        strategy_id="dividend",
        recommendation_id=recommendation_id,
        paper_action="PAPER_HOLD",
        rationale="Constitutional review passed.",
        confidence=90.0,
        constitution_version="1.0.0",
        state=DecisionState.READY_FOR_REVIEW,
    )
    decision.validate()


def test_position_requires_strategy_and_dates_for_open_status() -> None:
    position = Position(
        identity=new_identity(IdentifierKind.POSITION),
        portfolio_id=new_identity("POR").internal_id,
        asset_id=new_identity("AST").internal_id,
        strategy_id="dividend",
        quantity=10.0,
        cost_basis=1000.0,
        current_value=1050.0,
        status=PositionStatus.OPEN,
    )
    with pytest.raises(PlatformValidationError):
        position.validate()


def test_report_is_strategy_isolated_and_serializable() -> None:
    now = utc_now()
    report = ReportInstance(
        identity=new_identity(IdentifierKind.REPORT),
        strategy_id="dividend",
        report_type="weekly",
        period_start=now,
        period_end=now,
        metrics={"total_return_pct": 2.5},
        output_paths=("results/dividend/weekly/report.json",),
    )
    report.validate()
    rendered = JsonSerializer.dumps(report)
    assert '"strategy_id": "dividend"' in rendered
    assert "results/dividend/weekly/report.json" in rendered


def test_audit_and_learning_support_platform_or_strategy_scope() -> None:
    audit = AuditRun(
        identity=new_identity(IdentifierKind.AUDIT),
        scope_type="STRATEGY",
        scope_id="dividend",
        strategy_id="dividend",
        findings=(AuditFinding("paper_only", FindingStatus.PASS, "Paper-only enforcement active."),),
    )
    audit.validate()
    learning = LearningRecord(
        identity=new_identity(IdentifierKind.LEARNING),
        strategy_id="dividend",
        subject_type="DECISION",
        subject_id="DEC-2026-000001",
        lesson="Yield threshold was too aggressive.",
        source_reference="AUD-2026-000001",
    )
    learning.validate()
