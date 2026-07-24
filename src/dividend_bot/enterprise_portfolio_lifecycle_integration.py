"""Append-only lifecycle integration for governed paper portfolio records.

This module records review, mark, dividend accrual, exit, closure, and archival lifecycle
intent. It never mutates holdings, moves capital, calls brokers, or places orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from .enterprise_portfolio_integration import EnterprisePortfolioIntegrationRecord
from .platform_foundation import IdentifierFactory, JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_portfolio_lifecycle_integration"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Preserve governed paper portfolio lifecycle transitions without mutating holdings."


class PortfolioLifecycleAction(str, Enum):
    REVIEW = "REVIEW"
    MARK = "MARK"
    DIVIDEND_ACCRUAL = "DIVIDEND_ACCRUAL"
    EXIT_REVIEW = "EXIT_REVIEW"
    CLOSE = "CLOSE"
    ARCHIVE = "ARCHIVE"


_ALLOWED_TRANSITIONS = {
    None: {PortfolioLifecycleAction.REVIEW, PortfolioLifecycleAction.MARK, PortfolioLifecycleAction.DIVIDEND_ACCRUAL, PortfolioLifecycleAction.EXIT_REVIEW},
    PortfolioLifecycleAction.REVIEW: {PortfolioLifecycleAction.REVIEW, PortfolioLifecycleAction.MARK, PortfolioLifecycleAction.DIVIDEND_ACCRUAL, PortfolioLifecycleAction.EXIT_REVIEW, PortfolioLifecycleAction.CLOSE},
    PortfolioLifecycleAction.MARK: {PortfolioLifecycleAction.REVIEW, PortfolioLifecycleAction.MARK, PortfolioLifecycleAction.DIVIDEND_ACCRUAL, PortfolioLifecycleAction.EXIT_REVIEW, PortfolioLifecycleAction.CLOSE},
    PortfolioLifecycleAction.DIVIDEND_ACCRUAL: {PortfolioLifecycleAction.REVIEW, PortfolioLifecycleAction.MARK, PortfolioLifecycleAction.DIVIDEND_ACCRUAL, PortfolioLifecycleAction.EXIT_REVIEW, PortfolioLifecycleAction.CLOSE},
    PortfolioLifecycleAction.EXIT_REVIEW: {PortfolioLifecycleAction.REVIEW, PortfolioLifecycleAction.MARK, PortfolioLifecycleAction.CLOSE},
    PortfolioLifecycleAction.CLOSE: {PortfolioLifecycleAction.ARCHIVE},
    PortfolioLifecycleAction.ARCHIVE: set(),
}


@dataclass(frozen=True)
class EnterprisePortfolioLifecycleRecord:
    lifecycle_record_id: UUID
    sequence: int
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
    action: PortfolioLifecycleAction
    reason: str
    recorded_at: datetime = field(default_factory=utc_now)
    amount: float | None = None
    price: float | None = None
    supersedes_lifecycle_record_id: UUID | None = None
    metadata: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if self.sequence < 1:
            raise PlatformValidationError("lifecycle sequence must be positive")
        if not self.workflow_id.strip() or not self.correlation_id.strip() or not self.decision_public_id.strip():
            raise PlatformValidationError("workflow, correlation, and decision IDs are required")
        if self.strategy_id != "DIVIDEND":
            raise PlatformValidationError("portfolio lifecycle integration currently supports DIVIDEND only")
        if not self.evidence_ids:
            raise PlatformValidationError("lifecycle record requires evidence links")
        if not self.reason.strip():
            raise PlatformValidationError("lifecycle reason is required")
        if self.recorded_at.tzinfo is None:
            raise PlatformValidationError("recorded_at must be timezone-aware")
        if self.amount is not None and self.amount < 0:
            raise PlatformValidationError("lifecycle amount must not be negative")
        if self.price is not None and self.price <= 0:
            raise PlatformValidationError("lifecycle price must be greater than zero")
        if self.action is PortfolioLifecycleAction.DIVIDEND_ACCRUAL and self.amount is None:
            raise PlatformValidationError("dividend accrual requires an amount")
        if self.action in {PortfolioLifecycleAction.MARK, PortfolioLifecycleAction.CLOSE} and self.price is None:
            raise PlatformValidationError("mark and close actions require a price")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterprisePortfolioLifecycleLedger:
    def __init__(self) -> None:
        self._records: list[EnterprisePortfolioLifecycleRecord] = []
        self._ids: set[UUID] = set()

    def append(self, record: EnterprisePortfolioLifecycleRecord) -> None:
        record.validate()
        if record.sequence != len(self._records) + 1:
            raise PlatformValidationError("lifecycle sequence must be append-only")
        if record.lifecycle_record_id in self._ids:
            raise PlatformValidationError("lifecycle record already exists")
        prior = self.for_portfolio(record.portfolio_integration_id)
        previous = prior[-1] if prior else None
        expected_previous_id = previous.lifecycle_record_id if previous else None
        if record.supersedes_lifecycle_record_id != expected_previous_id:
            raise PlatformValidationError("lifecycle record must link to the immediately previous record")
        previous_action = previous.action if previous else None
        if record.action not in _ALLOWED_TRANSITIONS[previous_action]:
            raise PlatformValidationError("invalid portfolio lifecycle transition")
        self._records.append(record)
        self._ids.add(record.lifecycle_record_id)

    def all(self) -> tuple[EnterprisePortfolioLifecycleRecord, ...]:
        return tuple(self._records)

    def for_portfolio(self, portfolio_integration_id: UUID) -> tuple[EnterprisePortfolioLifecycleRecord, ...]:
        return tuple(item for item in self._records if item.portfolio_integration_id == portfolio_integration_id)

    def latest_for_portfolio(self, portfolio_integration_id: UUID) -> EnterprisePortfolioLifecycleRecord | None:
        records = self.for_portfolio(portfolio_integration_id)
        return records[-1] if records else None


@dataclass(frozen=True)
class EnterprisePortfolioLifecycleResult:
    record: EnterprisePortfolioLifecycleRecord
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


class EnterprisePortfolioLifecycleIntegration:
    def __init__(self, ledger: EnterprisePortfolioLifecycleLedger | None = None) -> None:
        self._ledger = ledger or EnterprisePortfolioLifecycleLedger()
        self._history: list[EnterprisePortfolioLifecycleResult] = []

    @property
    def ledger(self) -> EnterprisePortfolioLifecycleLedger:
        return self._ledger

    def history(self) -> tuple[EnterprisePortfolioLifecycleResult, ...]:
        return tuple(self._history)

    def record(
        self,
        portfolio: EnterprisePortfolioIntegrationRecord,
        *,
        action: PortfolioLifecycleAction,
        reason: str,
        amount: float | None = None,
        price: float | None = None,
        completed_at: datetime | None = None,
    ) -> EnterprisePortfolioLifecycleResult:
        portfolio.validate()
        timestamp = completed_at or utc_now()
        if timestamp.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        previous = self._ledger.latest_for_portfolio(portfolio.integration_id)
        record = EnterprisePortfolioLifecycleRecord(
            lifecycle_record_id=IdentifierFactory.new_internal_id(),
            sequence=len(self._ledger.all()) + 1,
            portfolio_integration_id=portfolio.integration_id,
            ledger_entry_id=portfolio.ledger_entry_id,
            workflow_id=portfolio.workflow_id,
            correlation_id=portfolio.correlation_id,
            decision_internal_id=portfolio.decision_internal_id,
            decision_public_id=portfolio.decision_public_id,
            company_id=portfolio.company_id,
            profile_id=portfolio.profile_id,
            strategy_id=portfolio.strategy_id,
            evidence_ids=portfolio.evidence_ids,
            action=action,
            reason=reason,
            recorded_at=timestamp,
            amount=amount,
            price=price,
            supersedes_lifecycle_record_id=previous.lifecycle_record_id if previous else None,
            metadata=MappingProxyType({"module_version": MODULE_VERSION, "portfolio_mutated": False, "append_only": True}),
        )
        self._ledger.append(record)
        result = EnterprisePortfolioLifecycleResult(record=record, completed_at=timestamp)
        result.validate()
        self._history.append(result)
        return result

    @staticmethod
    def render_json(result: EnterprisePortfolioLifecycleResult) -> str:
        result.validate()
        return JsonSerializer.dumps(result)

    @staticmethod
    def render_markdown(result: EnterprisePortfolioLifecycleResult) -> str:
        result.validate()
        item = result.record
        return "\n".join([
            "# Enterprise Portfolio Lifecycle Integration", "",
            f"- Sequence: {item.sequence}",
            f"- Decision ID: {item.decision_public_id}",
            f"- Strategy: {item.strategy_id}",
            f"- Action: {item.action.value}",
            f"- Reason: {item.reason}",
            f"- Evidence Count: {len(item.evidence_ids)}",
            f"- Portfolio Mutated: {'YES' if item.metadata['portfolio_mutated'] else 'NO'}",
            f"- Paper Trade Mode: {'YES' if item.paper_trade_mode else 'NO'}", "",
            "## Safety Boundary", "",
            "This lifecycle integration records paper-only lifecycle intent. It does not mutate holdings, move capital, call brokers, or place orders.", ""
        ])
