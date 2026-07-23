"""Audited investor approval workflow for Enterprise CIO capital assignments.

The Enterprise CIO report is advisory.  This module preserves the report recommendation,
records the investor's independent instruction, and only then applies that instruction to
the Enterprise Capital Manager.  It never creates broker or live-order requests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping
from uuid import UUID, uuid4

from .enterprise_capital_manager import (
    CapitalLedgerEntry,
    EnterpriseCapitalManager,
    InvestorCapitalInstruction,
)
from .enterprise_cio_capital_report import EnterpriseCapitalReport
from .platform_foundation import PlatformValidationError, utc_now

MODULE_NAME = "enterprise_capital_workflow"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Investor approval and audited application of Enterprise CIO capital guidance."


class CapitalApprovalStatus(str, Enum):
    APPROVED = "APPROVED"
    APPLIED = "APPLIED"


@dataclass(frozen=True)
class CapitalApprovalRecord:
    approval_id: UUID
    investor_id: str
    report_generated_at: datetime
    report_unassigned_cash: float
    cio_recommendation: Mapping[str, float]
    cio_rationale: str
    investor_allocations: Mapping[str, float]
    investor_reason: str
    approved_at: datetime = field(default_factory=utc_now)
    status: CapitalApprovalStatus = CapitalApprovalStatus.APPROVED

    def validate(self) -> None:
        if not self.investor_id.strip() or not self.investor_reason.strip():
            raise PlatformValidationError("investor_id and investor_reason must not be empty")
        if self.report_generated_at.tzinfo is None or self.approved_at.tzinfo is None:
            raise PlatformValidationError("capital approval timestamps must be timezone-aware")
        if self.report_unassigned_cash < 0:
            raise PlatformValidationError("report_unassigned_cash must not be negative")
        if not self.investor_allocations:
            raise PlatformValidationError("investor approval must include at least one strategy")
        if any(float(amount) < 0 for amount in self.investor_allocations.values()):
            raise PlatformValidationError("investor allocations must not be negative")
        if any(float(amount) < 0 for amount in self.cio_recommendation.values()):
            raise PlatformValidationError("CIO recommendation values must not be negative")
        if sum(float(value) for value in self.investor_allocations.values()) > self.report_unassigned_cash:
            raise PlatformValidationError("investor approval exceeds cash shown in the CIO report")


@dataclass(frozen=True)
class CapitalWorkflowResult:
    approval: CapitalApprovalRecord
    instruction: InvestorCapitalInstruction
    ledger_entries: tuple[CapitalLedgerEntry, ...]

    def validate(self) -> None:
        self.approval.validate()
        self.instruction.validate()
        if self.approval.status is not CapitalApprovalStatus.APPLIED:
            raise PlatformValidationError("completed capital workflow must have APPLIED status")
        if dict(self.approval.investor_allocations) != dict(self.instruction.strategy_allocations):
            raise PlatformValidationError("approval and investor instruction allocations must match")
        if self.approval.investor_id != self.instruction.investor_id:
            raise PlatformValidationError("approval and instruction investor_id must match")


class EnterpriseCapitalApprovalWorkflow:
    """Apply investor-approved capital instructions while preserving an append-only audit trail."""

    def __init__(self, capital_manager: EnterpriseCapitalManager) -> None:
        self._capital_manager = capital_manager
        self._history: list[CapitalApprovalRecord] = []

    def history(self) -> tuple[CapitalApprovalRecord, ...]:
        return tuple(self._history)

    def approve_and_apply(
        self,
        report: EnterpriseCapitalReport,
        *,
        investor_id: str,
        strategy_allocations: Mapping[str, float],
        reason: str,
        approved_at: datetime | None = None,
    ) -> CapitalWorkflowResult:
        report.validate()
        if report.investor_action_required is not True:
            raise PlatformValidationError("capital report must require investor action")
        if abs(report.unassigned_cash - self._capital_manager.unassigned_cash) > 1e-9:
            raise PlatformValidationError("capital report is stale; unassigned cash has changed")

        report_rows = {row.strategy_id: row for row in report.strategies}
        resolved_allocations = {key: float(value) for key, value in strategy_allocations.items()}
        for strategy_id, amount in resolved_allocations.items():
            row = report_rows.get(strategy_id)
            if row is None:
                raise PlatformValidationError(f"investor instruction references unreported strategy: {strategy_id}")
            if amount > 0 and not row.ready_for_allocation:
                raise PlatformValidationError(f"investor instruction references unready strategy: {strategy_id}")
            if abs(row.current_allocation - self._capital_manager.strategy_balance(strategy_id)) > 1e-9:
                raise PlatformValidationError(f"capital report is stale for strategy allocation: {strategy_id}")

        resolved_approved_at = approved_at or utc_now()
        cio_recommendation = {
            row.strategy_id: float(row.recommended_new_allocation)
            for row in report.strategies
            if row.recommended_new_allocation > 0
        }
        approval = CapitalApprovalRecord(
            approval_id=uuid4(),
            investor_id=investor_id,
            report_generated_at=report.generated_at,
            report_unassigned_cash=report.unassigned_cash,
            cio_recommendation=MappingProxyType(cio_recommendation),
            cio_rationale=report.recommendation_rationale,
            investor_allocations=MappingProxyType(dict(resolved_allocations)),
            investor_reason=reason,
            approved_at=resolved_approved_at,
        )
        approval.validate()

        instruction = InvestorCapitalInstruction(
            investor_id=investor_id,
            strategy_allocations=MappingProxyType(dict(resolved_allocations)),
            reason=reason,
            approved_at=resolved_approved_at,
        )
        instruction.validate()
        entries = self._capital_manager.apply_investor_instruction(instruction)

        applied = CapitalApprovalRecord(
            approval_id=approval.approval_id,
            investor_id=approval.investor_id,
            report_generated_at=approval.report_generated_at,
            report_unassigned_cash=approval.report_unassigned_cash,
            cio_recommendation=approval.cio_recommendation,
            cio_rationale=approval.cio_rationale,
            investor_allocations=approval.investor_allocations,
            investor_reason=approval.investor_reason,
            approved_at=approval.approved_at,
            status=CapitalApprovalStatus.APPLIED,
        )
        applied.validate()
        self._history.append(applied)

        result = CapitalWorkflowResult(applied, instruction, entries)
        result.validate()
        return result
