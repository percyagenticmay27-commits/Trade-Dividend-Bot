"""Append-only dividend lifecycle integration for governed Dividend portfolio records.

This module records dividend announcements, key dates, paper receipts, policy changes, and
review requirements. It never mutates holdings, moves cash, calls brokers, or places orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from .enterprise_portfolio_lifecycle_integration import EnterprisePortfolioLifecycleRecord
from .platform_foundation import IdentifierFactory, JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_dividend_lifecycle_integration"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Preserve governed Dividend lifecycle events without mutating holdings or cash."


class DividendLifecycleEvent(str, Enum):
    ANNOUNCED = "ANNOUNCED"
    EX_DATE = "EX_DATE"
    RECORD_DATE = "RECORD_DATE"
    PAYMENT_DATE = "PAYMENT_DATE"
    RECEIVED = "RECEIVED"
    INCREASED = "INCREASED"
    CUT = "CUT"
    SUSPENDED = "SUSPENDED"
    REINSTATED = "REINSTATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


_DATE_EVENTS = frozenset({
    DividendLifecycleEvent.ANNOUNCED,
    DividendLifecycleEvent.EX_DATE,
    DividendLifecycleEvent.RECORD_DATE,
    DividendLifecycleEvent.PAYMENT_DATE,
})
_AMOUNT_EVENTS = frozenset({
    DividendLifecycleEvent.ANNOUNCED,
    DividendLifecycleEvent.RECEIVED,
    DividendLifecycleEvent.INCREASED,
    DividendLifecycleEvent.CUT,
    DividendLifecycleEvent.REINSTATED,
})
_ALLOWED_TRANSITIONS = {
    None: {DividendLifecycleEvent.ANNOUNCED, DividendLifecycleEvent.REVIEW_REQUIRED},
    DividendLifecycleEvent.ANNOUNCED: {
        DividendLifecycleEvent.EX_DATE,
        DividendLifecycleEvent.INCREASED,
        DividendLifecycleEvent.CUT,
        DividendLifecycleEvent.SUSPENDED,
        DividendLifecycleEvent.REVIEW_REQUIRED,
    },
    DividendLifecycleEvent.EX_DATE: {
        DividendLifecycleEvent.RECORD_DATE,
        DividendLifecycleEvent.CUT,
        DividendLifecycleEvent.SUSPENDED,
        DividendLifecycleEvent.REVIEW_REQUIRED,
    },
    DividendLifecycleEvent.RECORD_DATE: {
        DividendLifecycleEvent.PAYMENT_DATE,
        DividendLifecycleEvent.CUT,
        DividendLifecycleEvent.SUSPENDED,
        DividendLifecycleEvent.REVIEW_REQUIRED,
    },
    DividendLifecycleEvent.PAYMENT_DATE: {
        DividendLifecycleEvent.RECEIVED,
        DividendLifecycleEvent.REVIEW_REQUIRED,
    },
    DividendLifecycleEvent.RECEIVED: {
        DividendLifecycleEvent.ANNOUNCED,
        DividendLifecycleEvent.INCREASED,
        DividendLifecycleEvent.CUT,
        DividendLifecycleEvent.SUSPENDED,
        DividendLifecycleEvent.REVIEW_REQUIRED,
    },
    DividendLifecycleEvent.INCREASED: {
        DividendLifecycleEvent.ANNOUNCED,
        DividendLifecycleEvent.EX_DATE,
        DividendLifecycleEvent.REVIEW_REQUIRED,
    },
    DividendLifecycleEvent.CUT: {
        DividendLifecycleEvent.ANNOUNCED,
        DividendLifecycleEvent.EX_DATE,
        DividendLifecycleEvent.SUSPENDED,
        DividendLifecycleEvent.REVIEW_REQUIRED,
    },
    DividendLifecycleEvent.SUSPENDED: {
        DividendLifecycleEvent.REINSTATED,
        DividendLifecycleEvent.REVIEW_REQUIRED,
    },
    DividendLifecycleEvent.REINSTATED: {
        DividendLifecycleEvent.ANNOUNCED,
        DividendLifecycleEvent.EX_DATE,
        DividendLifecycleEvent.REVIEW_REQUIRED,
    },
    DividendLifecycleEvent.REVIEW_REQUIRED: set(DividendLifecycleEvent),
}


@dataclass(frozen=True)
class EnterpriseDividendLifecycleRecord:
    dividend_record_id: UUID
    sequence: int
    portfolio_lifecycle_record_id: UUID
    portfolio_integration_id: UUID
    ledger_entry_id: UUID
    workflow_id: str
    correlation_id: str
    decision_internal_id: UUID
    decision_public_id: str
    company_id: UUID
    profile_id: UUID
    strategy_id: str
    evidence_ids: tuple[UUID, ...]
    event: DividendLifecycleEvent
    reason: str
    recorded_at: datetime = field(default_factory=utc_now)
    effective_date: date | None = None
    amount_per_share: float | None = None
    total_amount: float | None = None
    supersedes_dividend_record_id: UUID | None = None
    metadata: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if self.sequence < 1:
            raise PlatformValidationError("dividend lifecycle sequence must be positive")
        if not self.workflow_id.strip() or not self.correlation_id.strip() or not self.decision_public_id.strip():
            raise PlatformValidationError("workflow, correlation, and decision IDs are required")
        if self.strategy_id != "DIVIDEND":
            raise PlatformValidationError("dividend lifecycle integration supports DIVIDEND only")
        if not self.evidence_ids:
            raise PlatformValidationError("dividend lifecycle record requires evidence links")
        if not self.reason.strip():
            raise PlatformValidationError("dividend lifecycle reason is required")
        if self.recorded_at.tzinfo is None:
            raise PlatformValidationError("recorded_at must be timezone-aware")
        if self.event in _DATE_EVENTS and self.effective_date is None:
            raise PlatformValidationError("dated dividend lifecycle events require effective_date")
        if self.event in _AMOUNT_EVENTS and self.amount_per_share is None:
            raise PlatformValidationError("amount-bearing dividend lifecycle events require amount_per_share")
        if self.amount_per_share is not None and self.amount_per_share < 0:
            raise PlatformValidationError("amount_per_share must not be negative")
        if self.total_amount is not None and self.total_amount < 0:
            raise PlatformValidationError("total_amount must not be negative")
        if self.event is DividendLifecycleEvent.RECEIVED and self.total_amount is None:
            raise PlatformValidationError("received dividend events require total_amount")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterpriseDividendLifecycleLedger:
    def __init__(self) -> None:
        self._records: list[EnterpriseDividendLifecycleRecord] = []
        self._ids: set[UUID] = set()

    def append(self, record: EnterpriseDividendLifecycleRecord) -> None:
        record.validate()
        if record.sequence != len(self._records) + 1:
            raise PlatformValidationError("dividend lifecycle sequence must be append-only")
        if record.dividend_record_id in self._ids:
            raise PlatformValidationError("dividend lifecycle record already exists")
        previous = self.latest_for_portfolio(record.portfolio_integration_id)
        expected_previous = previous.dividend_record_id if previous else None
        if record.supersedes_dividend_record_id != expected_previous:
            raise PlatformValidationError("dividend lifecycle record must link to the immediately previous record")
        previous_event = previous.event if previous else None
        if record.event not in _ALLOWED_TRANSITIONS[previous_event]:
            raise PlatformValidationError("invalid dividend lifecycle transition")
        self._records.append(record)
        self._ids.add(record.dividend_record_id)

    def all(self) -> tuple[EnterpriseDividendLifecycleRecord, ...]:
        return tuple(self._records)

    def for_portfolio(self, portfolio_integration_id: UUID) -> tuple[EnterpriseDividendLifecycleRecord, ...]:
        return tuple(item for item in self._records if item.portfolio_integration_id == portfolio_integration_id)

    def latest_for_portfolio(self, portfolio_integration_id: UUID) -> EnterpriseDividendLifecycleRecord | None:
        rows = self.for_portfolio(portfolio_integration_id)
        return rows[-1] if rows else None


@dataclass(frozen=True)
class EnterpriseDividendLifecycleResult:
    record: EnterpriseDividendLifecycleRecord
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


class EnterpriseDividendLifecycleIntegration:
    def __init__(self, ledger: EnterpriseDividendLifecycleLedger | None = None) -> None:
        self._ledger = ledger or EnterpriseDividendLifecycleLedger()
        self._history: list[EnterpriseDividendLifecycleResult] = []

    @property
    def ledger(self) -> EnterpriseDividendLifecycleLedger:
        return self._ledger

    def history(self) -> tuple[EnterpriseDividendLifecycleResult, ...]:
        return tuple(self._history)

    def record(
        self,
        portfolio_lifecycle: EnterprisePortfolioLifecycleRecord,
        *,
        event: DividendLifecycleEvent,
        reason: str,
        effective_date: date | None = None,
        amount_per_share: float | None = None,
        total_amount: float | None = None,
        completed_at: datetime | None = None,
    ) -> EnterpriseDividendLifecycleResult:
        portfolio_lifecycle.validate()
        if portfolio_lifecycle.strategy_id != "DIVIDEND":
            raise PlatformValidationError("only DIVIDEND portfolio lifecycle records may be integrated")
        timestamp = completed_at or utc_now()
        if timestamp.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        previous = self._ledger.latest_for_portfolio(portfolio_lifecycle.portfolio_integration_id)
        record = EnterpriseDividendLifecycleRecord(
            dividend_record_id=IdentifierFactory.new_internal_id(),
            sequence=len(self._ledger.all()) + 1,
            portfolio_lifecycle_record_id=portfolio_lifecycle.lifecycle_record_id,
            portfolio_integration_id=portfolio_lifecycle.portfolio_integration_id,
            ledger_entry_id=portfolio_lifecycle.ledger_entry_id,
            workflow_id=portfolio_lifecycle.workflow_id,
            correlation_id=portfolio_lifecycle.correlation_id,
            decision_internal_id=portfolio_lifecycle.decision_internal_id,
            decision_public_id=portfolio_lifecycle.decision_public_id,
            company_id=portfolio_lifecycle.company_id,
            profile_id=portfolio_lifecycle.profile_id,
            strategy_id=portfolio_lifecycle.strategy_id,
            evidence_ids=portfolio_lifecycle.evidence_ids,
            event=event,
            reason=reason,
            recorded_at=timestamp,
            effective_date=effective_date,
            amount_per_share=amount_per_share,
            total_amount=total_amount,
            supersedes_dividend_record_id=previous.dividend_record_id if previous else None,
            metadata=MappingProxyType({
                "module_version": MODULE_VERSION,
                "portfolio_mutated": False,
                "cash_moved": False,
                "append_only": True,
            }),
        )
        self._ledger.append(record)
        result = EnterpriseDividendLifecycleResult(record=record, completed_at=timestamp)
        result.validate()
        self._history.append(result)
        return result

    @staticmethod
    def render_json(result: EnterpriseDividendLifecycleResult) -> str:
        result.validate()
        return JsonSerializer.dumps(result)

    @staticmethod
    def render_markdown(result: EnterpriseDividendLifecycleResult) -> str:
        result.validate()
        item = result.record
        return "\n".join([
            "# Enterprise Dividend Lifecycle Integration", "",
            f"- Sequence: {item.sequence}",
            f"- Decision ID: {item.decision_public_id}",
            f"- Strategy: {item.strategy_id}",
            f"- Event: {item.event.value}",
            f"- Effective Date: {item.effective_date or 'N/A'}",
            f"- Amount Per Share: {item.amount_per_share if item.amount_per_share is not None else 'N/A'}",
            f"- Total Amount: {item.total_amount if item.total_amount is not None else 'N/A'}",
            f"- Evidence Count: {len(item.evidence_ids)}",
            f"- Portfolio Mutated: {'YES' if item.metadata['portfolio_mutated'] else 'NO'}",
            f"- Cash Moved: {'YES' if item.metadata['cash_moved'] else 'NO'}",
            f"- Paper Trade Mode: {'YES' if item.paper_trade_mode else 'NO'}", "",
            "## Safety Boundary", "",
            "This integration records paper-only dividend lifecycle events. It does not mutate holdings, move cash, call brokers, or place orders.", "",
        ])
