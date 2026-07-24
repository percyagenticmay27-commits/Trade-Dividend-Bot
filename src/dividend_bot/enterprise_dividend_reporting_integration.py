"""Governed paper-only reporting for Dividend analytics records.

This module creates immutable weekly, monthly, and investor-facing report snapshots. It never
moves cash, changes balances, mutates holdings, calls brokers, or places orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from .enterprise_dividend_analytics_integration import EnterpriseDividendAnalyticsRecord
from .platform_foundation import IdentifierFactory, JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_dividend_reporting_integration"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Create immutable Dividend reports from governed analytics records."


class DividendReportScope(str, Enum):
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    INVESTOR = "INVESTOR"


@dataclass(frozen=True)
class EnterpriseDividendReportRecord:
    report_id: UUID
    sequence: int
    scope: DividendReportScope
    period_start: date
    period_end: date
    portfolio_integration_id: UUID
    workflow_id: str
    correlation_id: str
    decision_internal_id: UUID
    decision_public_id: str
    company_id: UUID
    profile_id: UUID
    strategy_id: str
    evidence_ids: tuple[UUID, ...]
    source_analytics_ids: tuple[UUID, ...]
    trailing_received_income: float
    forward_annual_income: float
    projected_yield_percent: float
    payment_consistency_percent: float
    latest_forecast_confidence: float
    review_flags: tuple[str, ...]
    report_status: str
    generated_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if self.sequence < 1:
            raise PlatformValidationError("report sequence must be positive")
        if self.period_end < self.period_start:
            raise PlatformValidationError("report period_end must not precede period_start")
        if self.strategy_id != "DIVIDEND":
            raise PlatformValidationError("dividend reporting integration supports DIVIDEND only")
        if not self.workflow_id.strip() or not self.correlation_id.strip() or not self.decision_public_id.strip():
            raise PlatformValidationError("workflow, correlation, and decision IDs are required")
        if not self.evidence_ids or not self.source_analytics_ids:
            raise PlatformValidationError("reports require evidence and analytics source links")
        if min(self.trailing_received_income, self.forward_annual_income, self.projected_yield_percent) < 0:
            raise PlatformValidationError("report income and yield values must not be negative")
        if not 0 <= self.payment_consistency_percent <= 100:
            raise PlatformValidationError("payment consistency must be between 0 and 100")
        if not 0 <= self.latest_forecast_confidence <= 100:
            raise PlatformValidationError("forecast confidence must be between 0 and 100")
        if len(set(self.review_flags)) != len(self.review_flags):
            raise PlatformValidationError("review flags must be unique")
        expected_status = "REVIEW_REQUIRED" if self.review_flags else "CLEAR"
        if self.report_status != expected_status:
            raise PlatformValidationError("report_status must reflect review flags")
        if self.generated_at.tzinfo is None:
            raise PlatformValidationError("generated_at must be timezone-aware")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterpriseDividendReportLedger:
    def __init__(self) -> None:
        self._records: list[EnterpriseDividendReportRecord] = []
        self._source_states: set[tuple[DividendReportScope, date, date, tuple[UUID, ...]]] = set()

    def append(self, record: EnterpriseDividendReportRecord) -> None:
        record.validate()
        if record.sequence != len(self._records) + 1:
            raise PlatformValidationError("report sequence must be append-only")
        state = (record.scope, record.period_start, record.period_end, record.source_analytics_ids)
        if state in self._source_states:
            raise PlatformValidationError("analytics state has already been reported for this scope and period")
        self._records.append(record)
        self._source_states.add(state)

    def all(self) -> tuple[EnterpriseDividendReportRecord, ...]:
        return tuple(self._records)


@dataclass(frozen=True)
class EnterpriseDividendReportingResult:
    record: EnterpriseDividendReportRecord
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


class EnterpriseDividendReportingIntegration:
    def __init__(self, ledger: EnterpriseDividendReportLedger | None = None) -> None:
        self._ledger = ledger or EnterpriseDividendReportLedger()
        self._history: list[EnterpriseDividendReportingResult] = []

    @property
    def ledger(self) -> EnterpriseDividendReportLedger:
        return self._ledger

    def history(self) -> tuple[EnterpriseDividendReportingResult, ...]:
        return tuple(self._history)

    def build_report(
        self,
        analytics_records: tuple[EnterpriseDividendAnalyticsRecord, ...],
        *,
        scope: DividendReportScope,
        period_start: date,
        period_end: date,
        completed_at: datetime | None = None,
    ) -> EnterpriseDividendReportingResult:
        if not analytics_records:
            raise PlatformValidationError("at least one analytics record is required")
        for item in analytics_records:
            item.validate()
        first = analytics_records[0]
        identity = (
            first.portfolio_integration_id, first.workflow_id, first.correlation_id,
            first.decision_internal_id, first.decision_public_id, first.company_id,
            first.profile_id, first.strategy_id,
        )
        for item in analytics_records:
            candidate = (
                item.portfolio_integration_id, item.workflow_id, item.correlation_id,
                item.decision_internal_id, item.decision_public_id, item.company_id,
                item.profile_id, item.strategy_id,
            )
            if candidate != identity:
                raise PlatformValidationError("report analytics records must preserve governed identity")
        sequences = tuple(item.sequence for item in analytics_records)
        if sequences != tuple(sorted(sequences)) or len(set(sequences)) != len(sequences):
            raise PlatformValidationError("analytics records must be unique and ordered")
        if period_end < period_start:
            raise PlatformValidationError("report period_end must not precede period_start")
        timestamp = completed_at or utc_now()
        if timestamp.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        latest = analytics_records[-1]
        evidence_ids = tuple(dict.fromkeys(eid for item in analytics_records for eid in item.evidence_ids))
        flags = tuple(dict.fromkeys(flag for item in analytics_records for flag in item.review_flags))
        record = EnterpriseDividendReportRecord(
            report_id=IdentifierFactory.new_internal_id(),
            sequence=len(self._ledger.all()) + 1,
            scope=scope,
            period_start=period_start,
            period_end=period_end,
            portfolio_integration_id=first.portfolio_integration_id,
            workflow_id=first.workflow_id,
            correlation_id=first.correlation_id,
            decision_internal_id=first.decision_internal_id,
            decision_public_id=first.decision_public_id,
            company_id=first.company_id,
            profile_id=first.profile_id,
            strategy_id=first.strategy_id,
            evidence_ids=evidence_ids,
            source_analytics_ids=tuple(item.analytics_id for item in analytics_records),
            trailing_received_income=latest.trailing_received_income,
            forward_annual_income=latest.forward_annual_income,
            projected_yield_percent=latest.projected_yield_percent,
            payment_consistency_percent=latest.payment_consistency_percent,
            latest_forecast_confidence=latest.latest_forecast_confidence,
            review_flags=flags,
            report_status="REVIEW_REQUIRED" if flags else "CLEAR",
            generated_at=timestamp,
            metadata=MappingProxyType({
                "module_version": MODULE_VERSION,
                "reporting_only": True,
                "investor_facing": scope is DividendReportScope.INVESTOR,
                "cash_moved": False,
                "portfolio_mutated": False,
                "append_only": True,
            }),
        )
        self._ledger.append(record)
        result = EnterpriseDividendReportingResult(record=record, completed_at=timestamp)
        result.validate()
        self._history.append(result)
        return result

    @staticmethod
    def render_json(result: EnterpriseDividendReportingResult) -> str:
        result.validate()
        return JsonSerializer.dumps(result)

    @staticmethod
    def render_markdown(result: EnterpriseDividendReportingResult) -> str:
        result.validate()
        item = result.record
        flags = ", ".join(item.review_flags) if item.review_flags else "NONE"
        return "\n".join([
            "# Enterprise Dividend Reporting Integration", "",
            f"- Scope: {item.scope.value}",
            f"- Period: {item.period_start} through {item.period_end}",
            f"- Decision ID: {item.decision_public_id}",
            f"- Strategy: {item.strategy_id}",
            f"- Report Status: {item.report_status}",
            f"- Trailing Received Income: ${item.trailing_received_income:,.2f}",
            f"- Forward Annual Income: ${item.forward_annual_income:,.2f}",
            f"- Projected Yield: {item.projected_yield_percent:.4f}%",
            f"- Payment Consistency: {item.payment_consistency_percent:.2f}%",
            f"- Forecast Confidence: {item.latest_forecast_confidence:.2f}%",
            f"- Review Flags: {flags}",
            f"- Cash Moved: {'YES' if item.metadata['cash_moved'] else 'NO'}",
            f"- Portfolio Mutated: {'YES' if item.metadata['portfolio_mutated'] else 'NO'}", "",
            "## Safety Boundary", "",
            "This report is paper-only and informational. It does not approve investments, move cash, alter balances, mutate holdings, call brokers, or place orders.", "",
        ])
