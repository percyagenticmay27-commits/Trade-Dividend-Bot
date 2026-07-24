"""Governed paper-only aggregation of dividend lifecycle records into income summaries.

This module calculates immutable accrual and receipt summaries from existing dividend lifecycle
records. It never moves cash, changes balances, mutates holdings, calls brokers, or places orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from .enterprise_dividend_lifecycle_integration import (
    DividendLifecycleEvent,
    EnterpriseDividendLifecycleRecord,
)
from .platform_foundation import IdentifierFactory, JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_dividend_income_integration"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Aggregate governed Dividend lifecycle records into immutable paper income summaries."


@dataclass(frozen=True)
class EnterpriseDividendIncomeRecord:
    income_record_id: UUID
    sequence: int
    portfolio_integration_id: UUID
    workflow_id: str
    correlation_id: str
    decision_internal_id: UUID
    decision_public_id: str
    company_id: UUID
    profile_id: UUID
    strategy_id: str
    evidence_ids: tuple[UUID, ...]
    source_dividend_record_ids: tuple[UUID, ...]
    announced_income: float
    received_income: float
    pending_income: float
    payment_count: int
    latest_amount_per_share: float | None
    calculated_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if self.sequence < 1:
            raise PlatformValidationError("income sequence must be positive")
        if not self.workflow_id.strip() or not self.correlation_id.strip() or not self.decision_public_id.strip():
            raise PlatformValidationError("workflow, correlation, and decision IDs are required")
        if self.strategy_id != "DIVIDEND":
            raise PlatformValidationError("dividend income integration supports DIVIDEND only")
        if not self.evidence_ids or not self.source_dividend_record_ids:
            raise PlatformValidationError("income records require evidence and dividend source links")
        if min(self.announced_income, self.received_income, self.pending_income) < 0:
            raise PlatformValidationError("income amounts must not be negative")
        expected_pending = round(max(self.announced_income - self.received_income, 0.0), 8)
        if abs(self.pending_income - expected_pending) > 1e-6:
            raise PlatformValidationError("pending_income must equal announced minus received, floored at zero")
        if self.payment_count < 0:
            raise PlatformValidationError("payment_count must not be negative")
        if self.latest_amount_per_share is not None and self.latest_amount_per_share < 0:
            raise PlatformValidationError("latest_amount_per_share must not be negative")
        if self.calculated_at.tzinfo is None:
            raise PlatformValidationError("calculated_at must be timezone-aware")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterpriseDividendIncomeLedger:
    """Append-only income summary ledger, one summary per lifecycle state."""

    def __init__(self) -> None:
        self._records: list[EnterpriseDividendIncomeRecord] = []
        self._source_sets: set[tuple[UUID, ...]] = set()

    def append(self, record: EnterpriseDividendIncomeRecord) -> None:
        record.validate()
        if record.sequence != len(self._records) + 1:
            raise PlatformValidationError("income sequence must be append-only")
        if record.source_dividend_record_ids in self._source_sets:
            raise PlatformValidationError("dividend lifecycle state has already been summarized")
        self._records.append(record)
        self._source_sets.add(record.source_dividend_record_ids)

    def all(self) -> tuple[EnterpriseDividendIncomeRecord, ...]:
        return tuple(self._records)

    def for_portfolio(self, portfolio_integration_id: UUID) -> tuple[EnterpriseDividendIncomeRecord, ...]:
        return tuple(item for item in self._records if item.portfolio_integration_id == portfolio_integration_id)


@dataclass(frozen=True)
class EnterpriseDividendIncomeResult:
    record: EnterpriseDividendIncomeRecord
    completed_at: datetime
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        self.record.validate()
        if self.completed_at.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterpriseDividendIncomeIntegration:
    def __init__(self, ledger: EnterpriseDividendIncomeLedger | None = None) -> None:
        self._ledger = ledger or EnterpriseDividendIncomeLedger()
        self._history: list[EnterpriseDividendIncomeResult] = []

    @property
    def ledger(self) -> EnterpriseDividendIncomeLedger:
        return self._ledger

    def history(self) -> tuple[EnterpriseDividendIncomeResult, ...]:
        return tuple(self._history)

    def summarize(
        self,
        lifecycle_records: tuple[EnterpriseDividendLifecycleRecord, ...],
        *,
        completed_at: datetime | None = None,
    ) -> EnterpriseDividendIncomeResult:
        if not lifecycle_records:
            raise PlatformValidationError("at least one dividend lifecycle record is required")
        for item in lifecycle_records:
            item.validate()
        first = lifecycle_records[0]
        for item in lifecycle_records:
            if item.portfolio_integration_id != first.portfolio_integration_id:
                raise PlatformValidationError("income summary records must belong to one portfolio")
            if item.workflow_id != first.workflow_id or item.correlation_id != first.correlation_id:
                raise PlatformValidationError("income summary records must preserve workflow linkage")
            if item.decision_internal_id != first.decision_internal_id or item.decision_public_id != first.decision_public_id:
                raise PlatformValidationError("income summary records must preserve decision linkage")
            if item.company_id != first.company_id or item.profile_id != first.profile_id:
                raise PlatformValidationError("income summary records must preserve company and profile linkage")
            if item.strategy_id != "DIVIDEND":
                raise PlatformValidationError("income summary supports DIVIDEND only")
        sequences = tuple(item.sequence for item in lifecycle_records)
        if sequences != tuple(sorted(sequences)) or len(set(sequences)) != len(sequences):
            raise PlatformValidationError("dividend lifecycle records must be unique and ordered")

        timestamp = completed_at or utc_now()
        if timestamp.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")

        announced = round(sum(float(item.total_amount or 0.0) for item in lifecycle_records if item.event is DividendLifecycleEvent.ANNOUNCED), 8)
        received = round(sum(float(item.total_amount or 0.0) for item in lifecycle_records if item.event is DividendLifecycleEvent.RECEIVED), 8)
        pending = round(max(announced - received, 0.0), 8)
        amount_rows = [item.amount_per_share for item in lifecycle_records if item.amount_per_share is not None]
        evidence_ids = tuple(dict.fromkeys(evidence_id for item in lifecycle_records for evidence_id in item.evidence_ids))
        record = EnterpriseDividendIncomeRecord(
            income_record_id=IdentifierFactory.new_internal_id(),
            sequence=len(self._ledger.all()) + 1,
            portfolio_integration_id=first.portfolio_integration_id,
            workflow_id=first.workflow_id,
            correlation_id=first.correlation_id,
            decision_internal_id=first.decision_internal_id,
            decision_public_id=first.decision_public_id,
            company_id=first.company_id,
            profile_id=first.profile_id,
            strategy_id=first.strategy_id,
            evidence_ids=evidence_ids,
            source_dividend_record_ids=tuple(item.dividend_record_id for item in lifecycle_records),
            announced_income=announced,
            received_income=received,
            pending_income=pending,
            payment_count=sum(1 for item in lifecycle_records if item.event is DividendLifecycleEvent.RECEIVED),
            latest_amount_per_share=float(amount_rows[-1]) if amount_rows else None,
            calculated_at=timestamp,
            metadata=MappingProxyType({
                "module_version": MODULE_VERSION,
                "cash_moved": False,
                "portfolio_mutated": False,
                "append_only": True,
            }),
        )
        self._ledger.append(record)
        result = EnterpriseDividendIncomeResult(record=record, completed_at=timestamp)
        result.validate()
        self._history.append(result)
        return result

    @staticmethod
    def render_json(result: EnterpriseDividendIncomeResult) -> str:
        result.validate()
        return JsonSerializer.dumps(result)

    @staticmethod
    def render_markdown(result: EnterpriseDividendIncomeResult) -> str:
        result.validate()
        item = result.record
        return "\n".join([
            "# Enterprise Dividend Income Integration", "",
            f"- Sequence: {item.sequence}",
            f"- Decision ID: {item.decision_public_id}",
            f"- Strategy: {item.strategy_id}",
            f"- Announced Income: ${item.announced_income:,.2f}",
            f"- Received Income: ${item.received_income:,.2f}",
            f"- Pending Income: ${item.pending_income:,.2f}",
            f"- Payment Count: {item.payment_count}",
            f"- Source Records: {len(item.source_dividend_record_ids)}",
            f"- Cash Moved: {'YES' if item.metadata['cash_moved'] else 'NO'}",
            f"- Portfolio Mutated: {'YES' if item.metadata['portfolio_mutated'] else 'NO'}",
            f"- Paper Trade Mode: {'YES' if item.paper_trade_mode else 'NO'}", "",
            "## Safety Boundary", "",
            "This integration calculates paper dividend income summaries only. It does not move cash, alter balances, mutate holdings, call brokers, or place orders.", "",
        ])
