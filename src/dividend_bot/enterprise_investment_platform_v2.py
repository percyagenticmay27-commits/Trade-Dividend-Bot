"""Enterprise Investment Platform Version 2.0 paper-only runtime.

This module composes the strategy registry, Enterprise CIO capital report,
investor approval workflow, enterprise capital ledger, shared MCIP integration,
and the Dividend Strategy paper cycle. It does not place broker orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .dividend_strategy_adapter import DIVIDEND_STRATEGY_ID, DividendStrategyAdapter
from .enterprise_capital_manager import CapitalRecommendation, EnterpriseCapitalManager
from .enterprise_capital_workflow import CapitalWorkflowResult, EnterpriseCapitalApprovalWorkflow
from .enterprise_cio_capital_report import EnterpriseCIOCapitalReporter, EnterpriseCapitalReport
from .platform_entities import MasterCompanyIntelligenceProfile
from .platform_foundation import PlatformValidationError
from .platform_integration import DividendPaperCycleResult, DividendPlatformPaperCycle, ServiceDomain
from .strategy_framework import StrategyRegistry, StrategyStatus

MODULE_NAME = "enterprise_investment_platform_v2"
MODULE_VERSION = "2.0.0"
MODULE_DESCRIPTION = "Paper-only enterprise orchestration for capital assignment and strategy execution."


@dataclass(frozen=True)
class EnterprisePlatformSnapshot:
    unassigned_cash: float
    strategy_allocations: Mapping[str, float]
    strategy_statuses: Mapping[str, str]
    total_managed_capital: float
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if self.unassigned_cash < 0 or self.total_managed_capital < 0:
            raise PlatformValidationError("enterprise capital values must not be negative")
        if any(float(value) < 0 for value in self.strategy_allocations.values()):
            raise PlatformValidationError("strategy allocations must not be negative")
        calculated = self.unassigned_cash + sum(float(value) for value in self.strategy_allocations.values())
        if abs(calculated - self.total_managed_capital) > 1e-9:
            raise PlatformValidationError("total managed capital must equal cash plus strategy allocations")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterpriseInvestmentPlatformV2:
    """Compose enterprise governance and the first operational Dividend strategy."""

    def __init__(self) -> None:
        self.strategy_registry = StrategyRegistry()
        DividendStrategyAdapter.register(self.strategy_registry)
        self.strategy_registry.transition(
            DIVIDEND_STRATEGY_ID,
            StrategyStatus.CONFIGURED,
            "Dividend Strategy configuration validated for Enterprise Platform v2",
        )
        self.strategy_registry.transition(
            DIVIDEND_STRATEGY_ID,
            StrategyStatus.PAPER_VALIDATION,
            "Dividend Strategy enabled for paper validation only",
        )

        self.capital_manager = EnterpriseCapitalManager(self.strategy_registry)
        self.capital_reporter = EnterpriseCIOCapitalReporter(self.capital_manager)
        self.capital_workflow = EnterpriseCapitalApprovalWorkflow(self.capital_manager)
        self.dividend_paper_cycle = DividendPlatformPaperCycle()

    def record_deposit(self, amount: float, *, reason: str = "Investor cash deposit") -> None:
        self.capital_manager.record_deposit(amount, reason=reason)

    def build_capital_report(
        self,
        *,
        minimum_capital_by_strategy: Mapping[str, float] | None = None,
        recommended_allocations: Mapping[str, float] | None = None,
        recommendation_rationale: str = "",
        recommendation_reasons: Mapping[str, str] | None = None,
    ) -> EnterpriseCapitalReport:
        recommendation = None
        if recommended_allocations is not None:
            recommendation = CapitalRecommendation(
                strategy_allocations=dict(recommended_allocations),
                rationale=recommendation_rationale,
            )
        return self.capital_reporter.build_report(
            minimum_capital_by_strategy=minimum_capital_by_strategy,
            recommendation=recommendation,
            recommendation_reasons=recommendation_reasons,
        )

    def approve_capital(
        self,
        report: EnterpriseCapitalReport,
        *,
        investor_id: str,
        strategy_allocations: Mapping[str, float],
        reason: str,
    ) -> CapitalWorkflowResult:
        return self.capital_workflow.approve_and_apply(
            report,
            investor_id=investor_id,
            strategy_allocations=strategy_allocations,
            reason=reason,
        )

    def run_dividend_paper_cycle(
        self,
        profile: MasterCompanyIntelligenceProfile,
        intelligence_updates: Mapping[ServiceDomain, Mapping[str, Any]],
        *,
        quality_score: float | None = None,
    ) -> DividendPaperCycleResult:
        status = self.strategy_registry.status(DIVIDEND_STRATEGY_ID)
        if status not in {StrategyStatus.PAPER_VALIDATION, StrategyStatus.OPERATIONAL}:
            raise PlatformValidationError("Dividend Strategy is not ready for a paper cycle")
        if self.capital_manager.strategy_balance(DIVIDEND_STRATEGY_ID) <= 0:
            raise PlatformValidationError("Dividend Strategy requires investor-assigned capital before execution")
        return self.dividend_paper_cycle.run(
            profile,
            intelligence_updates,
            quality_score=quality_score,
        )

    def snapshot(self) -> EnterprisePlatformSnapshot:
        allocations = {
            definition.strategy_id: self.capital_manager.strategy_balance(definition.strategy_id)
            for definition in self.strategy_registry.list_definitions()
        }
        statuses = {
            definition.strategy_id: self.strategy_registry.status(definition.strategy_id).value
            for definition in self.strategy_registry.list_definitions()
        }
        snapshot = EnterprisePlatformSnapshot(
            unassigned_cash=self.capital_manager.unassigned_cash,
            strategy_allocations=allocations,
            strategy_statuses=statuses,
            total_managed_capital=self.capital_manager.unassigned_cash + sum(allocations.values()),
        )
        snapshot.validate()
        return snapshot
