"""Enterprise CIO strategy availability and capital recommendation reporting.

This module presents registered strategy readiness and optional capital guidance to
an investor before any enterprise cash is assigned. It is advisory and paper-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from .enterprise_capital_manager import CapitalRecommendation, EnterpriseCapitalManager, StrategyAvailability
from .platform_foundation import JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_cio_capital_report"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Investor-facing Enterprise CIO strategy availability and capital recommendation report."


@dataclass(frozen=True)
class StrategyCapitalView:
    strategy_id: str
    name: str
    version: str
    status: str
    ready_for_allocation: bool
    minimum_capital: float
    current_allocation: float
    recommended_new_allocation: float = 0.0
    recommendation_reason: str = ""

    def validate(self) -> None:
        if not self.strategy_id or self.strategy_id != self.strategy_id.upper():
            raise PlatformValidationError("strategy_id must be non-empty uppercase text")
        if not self.name.strip() or not self.version.strip() or not self.status.strip():
            raise PlatformValidationError("strategy display fields must not be empty")
        if self.minimum_capital < 0 or self.current_allocation < 0 or self.recommended_new_allocation < 0:
            raise PlatformValidationError("capital values must not be negative")


@dataclass(frozen=True)
class EnterpriseCapitalReport:
    generated_at: datetime
    unassigned_cash: float
    strategies: tuple[StrategyCapitalView, ...]
    recommendation_total: float
    recommendation_rationale: str
    investor_action_required: bool = True
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if self.generated_at.tzinfo is None:
            raise PlatformValidationError("generated_at must be timezone-aware")
        if self.unassigned_cash < 0 or self.recommendation_total < 0:
            raise PlatformValidationError("report capital values must not be negative")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")
        if not self.strategies:
            raise PlatformValidationError("capital report requires at least one registered strategy")
        for strategy in self.strategies:
            strategy.validate()
        calculated = sum(row.recommended_new_allocation for row in self.strategies)
        if abs(calculated - self.recommendation_total) > 1e-9:
            raise PlatformValidationError("recommendation_total must equal strategy recommendation values")
        if self.recommendation_total > self.unassigned_cash:
            raise PlatformValidationError("recommendation exceeds unassigned cash")
        if self.recommendation_total > 0 and not self.recommendation_rationale.strip():
            raise PlatformValidationError("capital recommendation requires rationale")


class EnterpriseCIOCapitalReporter:
    """Build investor-facing reports without assigning or transferring capital."""

    def __init__(self, capital_manager: EnterpriseCapitalManager) -> None:
        self._capital_manager = capital_manager

    def build_report(
        self,
        *,
        minimum_capital_by_strategy: Mapping[str, float] | None = None,
        recommendation: CapitalRecommendation | None = None,
        recommendation_reasons: Mapping[str, str] | None = None,
        generated_at: datetime | None = None,
    ) -> EnterpriseCapitalReport:
        availability = self._capital_manager.discover_available_strategies(minimum_capital_by_strategy)
        recommendation_map: Mapping[str, float] = {}
        rationale = "No Enterprise CIO allocation recommendation was requested."
        if recommendation is not None:
            recommendation.validate()
            recommendation_map = recommendation.strategy_allocations
            rationale = recommendation.rationale
            self._validate_recommendation(availability, recommendation)

        reasons = recommendation_reasons or {}
        rows = tuple(
            StrategyCapitalView(
                strategy_id=item.strategy_id,
                name=item.name,
                version=item.version,
                status=item.status.value,
                ready_for_allocation=item.ready_for_allocation,
                minimum_capital=item.minimum_capital,
                current_allocation=item.current_allocation,
                recommended_new_allocation=float(recommendation_map.get(item.strategy_id, 0.0)),
                recommendation_reason=str(reasons.get(item.strategy_id, "")),
            )
            for item in availability
        )
        warnings = tuple(
            f"{item.strategy_id} is installed but not ready for capital allocation"
            for item in availability
            if not item.ready_for_allocation
        )
        report = EnterpriseCapitalReport(
            generated_at=generated_at or utc_now(),
            unassigned_cash=self._capital_manager.unassigned_cash,
            strategies=rows,
            recommendation_total=sum(row.recommended_new_allocation for row in rows),
            recommendation_rationale=rationale,
            warnings=warnings,
        )
        report.validate()
        return report

    def render_json(self, report: EnterpriseCapitalReport) -> str:
        report.validate()
        return JsonSerializer.dumps(report)

    def render_markdown(self, report: EnterpriseCapitalReport) -> str:
        report.validate()
        lines = [
            "# Enterprise CIO Capital Assignment Report",
            "",
            f"- Generated At: {JsonSerializer.to_primitive(report.generated_at)}",
            f"- Unassigned Cash: ${report.unassigned_cash:,.2f}",
            f"- Recommended Assignment: ${report.recommendation_total:,.2f}",
            f"- Investor Approval Required: {'YES' if report.investor_action_required else 'NO'}",
            f"- Paper Trade Mode: {'YES' if report.paper_trade_mode else 'NO'}",
            "",
            "## Available Strategies",
            "",
            "| Strategy | Version | Status | Ready | Minimum Capital | Current Allocation | CIO Recommendation |",
            "|---|---:|---|---|---:|---:|---:|",
        ]
        for row in report.strategies:
            lines.append(
                f"| {row.strategy_id} | {row.version} | {row.status} | "
                f"{'YES' if row.ready_for_allocation else 'NO'} | "
                f"${row.minimum_capital:,.2f} | ${row.current_allocation:,.2f} | "
                f"${row.recommended_new_allocation:,.2f} |"
            )
        lines.extend(["", "## Enterprise CIO Recommendation", "", report.recommendation_rationale, ""])
        reasons = [row for row in report.strategies if row.recommendation_reason]
        if reasons:
            lines.extend(["## Strategy Rationale", ""])
            lines.extend(f"- {row.strategy_id}: {row.recommendation_reason}" for row in reasons)
            lines.append("")
        if report.warnings:
            lines.extend(["## Warnings", ""])
            lines.extend(f"- {warning}" for warning in report.warnings)
            lines.append("")
        lines.extend(
            [
                "## Investor Decision",
                "",
                "No capital is assigned by this report. The investor must approve an allocation instruction before the Enterprise Capital Manager changes strategy balances.",
                "",
            ]
        )
        return "\n".join(lines)

    def _validate_recommendation(
        self,
        availability: tuple[StrategyAvailability, ...],
        recommendation: CapitalRecommendation,
    ) -> None:
        available_by_id = {item.strategy_id: item for item in availability}
        total = sum(float(amount) for amount in recommendation.strategy_allocations.values())
        if total > self._capital_manager.unassigned_cash:
            raise PlatformValidationError("Enterprise CIO recommendation exceeds unassigned cash")
        for strategy_id, amount in recommendation.strategy_allocations.items():
            if strategy_id not in available_by_id:
                raise PlatformValidationError(f"recommendation references unregistered strategy: {strategy_id}")
            if amount > 0 and not available_by_id[strategy_id].ready_for_allocation:
                raise PlatformValidationError(f"recommendation references unready strategy: {strategy_id}")
