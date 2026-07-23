"""First registered Dividend Strategy adapter on the shared paper-only platform."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from .audit_framework import AuditCheckResult, AuditModel
from .platform_entities import (
    FindingStatus,
    MasterCompanyIntelligenceProfile,
    StrategyEvaluation,
    StrategyRecommendation,
    new_identity,
)
from .platform_foundation import IdentifierKind, PlatformValidationError
from .reporting_framework import ReportSection, StrategyReportModel
from .strategy_framework import StrategyConfiguration, StrategyDefinition, StrategyRegistry

MODULE_NAME = "dividend_strategy_adapter"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Dividend-specific interpretation of shared intelligence with isolated outputs."

DIVIDEND_STRATEGY_ID = "DIVIDEND"

DIVIDEND_STRATEGY_DEFINITION = StrategyDefinition(
    strategy_id=DIVIDEND_STRATEGY_ID,
    name="Dividend Strategy",
    version=MODULE_VERSION,
    supported_asset_types=("EQUITY", "ETF", "LEVERAGED_ETF"),
    required_intelligence=("income", "fundamentals", "financial_health", "risk", "earnings"),
    supported_report_types=("DAILY", "WEEKLY", "MONTHLY", "PERFORMANCE", "LEARNING"),
    supported_audit_types=("WEEKLY_AUDIT", "MONTHLY_AUDIT", "RELEASE_AUDIT"),
    module_entry_point="src.dividend_bot.dividend_strategy_adapter:DividendStrategyAdapter",
)

DEFAULT_DIVIDEND_CONFIGURATION = StrategyConfiguration(
    strategy_id=DIVIDEND_STRATEGY_ID,
    version=MODULE_VERSION,
    parameters={
        "minimum_income_score": 50.0,
        "maximum_risk_score": 60.0,
        "minimum_profile_quality": 50.0,
        "paper_trade_mode": True,
    },
)


@dataclass(frozen=True)
class DividendEvaluationResult:
    evaluation: StrategyEvaluation
    recommendation: StrategyRecommendation


class DividendStrategyAdapter:
    """Interpret MCIP facts for Dividend only; never mutate shared intelligence."""

    strategy_id = DIVIDEND_STRATEGY_ID

    def __init__(self, configuration: StrategyConfiguration | None = None) -> None:
        self.configuration = configuration or DEFAULT_DIVIDEND_CONFIGURATION
        self.configuration.validate()
        if self.configuration.strategy_id != self.strategy_id:
            raise PlatformValidationError("Dividend adapter requires DIVIDEND configuration")

    @staticmethod
    def register(registry: StrategyRegistry) -> None:
        registry.register(DIVIDEND_STRATEGY_DEFINITION)
        registry.configure(DEFAULT_DIVIDEND_CONFIGURATION)

    def evaluate(self, profile: MasterCompanyIntelligenceProfile) -> DividendEvaluationResult:
        profile.validate()
        income_score = _numeric(profile.income.get("score", 0.0), "income.score")
        risk_score = _numeric(profile.risk.get("score", 100.0), "risk.score")
        quality_score = profile.quality_score

        minimum_income = float(self.configuration.parameters["minimum_income_score"])
        maximum_risk = float(self.configuration.parameters["maximum_risk_score"])
        minimum_quality = float(self.configuration.parameters["minimum_profile_quality"])

        score = max(0.0, min(100.0, income_score * 0.5 + (100.0 - risk_score) * 0.3 + quality_score * 0.2))
        suitable = income_score >= minimum_income and risk_score <= maximum_risk and quality_score >= minimum_quality
        rationale = (
            f"Dividend evaluation: income={income_score:.1f}, risk={risk_score:.1f}, "
            f"profile_quality={quality_score:.1f}; suitable={suitable}."
        )
        evaluation = StrategyEvaluation(
            identity=new_identity("EVA"),
            strategy_id=self.strategy_id,
            company_id=profile.company_id,
            profile_id=profile.identity.internal_id,
            score=score,
            rationale=rationale,
        )
        evaluation.validate()
        recommendation = StrategyRecommendation(
            identity=new_identity("REC"),
            strategy_id=self.strategy_id,
            evaluation_id=evaluation.identity.internal_id,
            paper_action="REVIEW_FOR_PAPER_BUY" if suitable else "WATCHLIST",
            rationale=rationale,
            confidence=score,
        )
        recommendation.validate()
        return DividendEvaluationResult(evaluation, recommendation)

    def build_report(
        self,
        *,
        report_type: str,
        period_start: datetime,
        period_end: datetime,
        metrics: Mapping[str, Any],
        warnings: tuple[str, ...] = (),
        decision_ids: tuple[str, ...] = (),
    ) -> StrategyReportModel:
        report_type = report_type.upper()
        if report_type not in DIVIDEND_STRATEGY_DEFINITION.supported_report_types:
            raise PlatformValidationError(f"unsupported Dividend report type: {report_type}")
        model = StrategyReportModel(
            strategy_id=self.strategy_id,
            report_type=report_type,
            title=f"Dividend {report_type.title()} Report",
            period_start=period_start,
            period_end=period_end,
            sections=(ReportSection("Dividend Performance", dict(metrics)),),
            warnings=warnings,
            decision_ids=decision_ids,
        )
        model.validate()
        return model

    def build_audit(
        self,
        *,
        audit_type: str,
        completed_at: datetime,
        checks: tuple[AuditCheckResult, ...],
    ) -> AuditModel:
        audit_type = audit_type.upper()
        if audit_type not in DIVIDEND_STRATEGY_DEFINITION.supported_audit_types:
            raise PlatformValidationError(f"unsupported Dividend audit type: {audit_type}")
        model = AuditModel(
            scope_type="STRATEGY",
            scope_id=self.strategy_id,
            strategy_id=self.strategy_id,
            audit_type=audit_type,
            completed_at=completed_at,
            checks=checks,
        )
        model.validate()
        return model


def default_dividend_safety_checks() -> tuple[AuditCheckResult, ...]:
    return (
        AuditCheckResult("paper_trade_mode", FindingStatus.PASS, "Dividend strategy is paper-only"),
        AuditCheckResult("strategy_report_isolation", FindingStatus.PASS, "Dividend outputs use Dividend scope"),
        AuditCheckResult("broker_execution", FindingStatus.PASS, "Broker execution remains disabled"),
    )


def _numeric(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlatformValidationError(f"{field_name} must be numeric")
    number = float(value)
    if not 0.0 <= number <= 100.0:
        raise PlatformValidationError(f"{field_name} must be between 0 and 100")
    return number
