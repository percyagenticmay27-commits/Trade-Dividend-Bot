"""Governed paper-only analytics for Dividend income and forecast records.

This module produces immutable analytical snapshots only. It does not move cash, alter balances,
mutate holdings, call brokers, or place orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from .enterprise_dividend_income_integration import EnterpriseDividendIncomeRecord
from .enterprise_income_forecast_integration import EnterpriseIncomeForecastRecord, IncomeForecastStatus
from .platform_foundation import IdentifierFactory, JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_dividend_analytics_integration"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Create immutable Dividend analytics from governed income and forecast records."


@dataclass(frozen=True)
class EnterpriseDividendAnalyticsRecord:
    analytics_id: UUID
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
    source_income_record_ids: tuple[UUID, ...]
    source_forecast_ids: tuple[UUID, ...]
    trailing_received_income: float
    forward_annual_income: float
    income_growth_percent: float | None
    projected_yield_percent: float
    forecast_variance: float
    payment_consistency_percent: float
    latest_forecast_confidence: float
    review_flags: tuple[str, ...]
    calculated_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if self.sequence < 1:
            raise PlatformValidationError("analytics sequence must be positive")
        if not self.workflow_id.strip() or not self.correlation_id.strip() or not self.decision_public_id.strip():
            raise PlatformValidationError("workflow, correlation, and decision IDs are required")
        if self.strategy_id != "DIVIDEND":
            raise PlatformValidationError("dividend analytics integration supports DIVIDEND only")
        if not self.evidence_ids or not self.source_income_record_ids or not self.source_forecast_ids:
            raise PlatformValidationError("analytics requires evidence, income, and forecast source links")
        if min(self.trailing_received_income, self.forward_annual_income, self.projected_yield_percent) < 0:
            raise PlatformValidationError("analytics income and yield values must not be negative")
        expected_variance = round(self.forward_annual_income - self.trailing_received_income, 8)
        if abs(self.forecast_variance - expected_variance) > 1e-6:
            raise PlatformValidationError("forecast_variance must equal forward income minus trailing income")
        if self.income_growth_percent is not None and self.trailing_received_income <= 0:
            raise PlatformValidationError("income growth requires positive trailing income")
        if not 0 <= self.payment_consistency_percent <= 100:
            raise PlatformValidationError("payment consistency must be between 0 and 100")
        if not 0 <= self.latest_forecast_confidence <= 100:
            raise PlatformValidationError("forecast confidence must be between 0 and 100")
        if len(set(self.review_flags)) != len(self.review_flags):
            raise PlatformValidationError("review flags must be unique")
        if self.calculated_at.tzinfo is None:
            raise PlatformValidationError("calculated_at must be timezone-aware")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterpriseDividendAnalyticsLedger:
    def __init__(self) -> None:
        self._records: list[EnterpriseDividendAnalyticsRecord] = []
        self._source_states: set[tuple[tuple[UUID, ...], tuple[UUID, ...]]] = set()

    def append(self, record: EnterpriseDividendAnalyticsRecord) -> None:
        record.validate()
        if record.sequence != len(self._records) + 1:
            raise PlatformValidationError("analytics sequence must be append-only")
        state = (record.source_income_record_ids, record.source_forecast_ids)
        if state in self._source_states:
            raise PlatformValidationError("income and forecast state has already been analyzed")
        self._records.append(record)
        self._source_states.add(state)

    def all(self) -> tuple[EnterpriseDividendAnalyticsRecord, ...]:
        return tuple(self._records)

    def for_portfolio(self, portfolio_integration_id: UUID) -> tuple[EnterpriseDividendAnalyticsRecord, ...]:
        return tuple(item for item in self._records if item.portfolio_integration_id == portfolio_integration_id)


@dataclass(frozen=True)
class EnterpriseDividendAnalyticsResult:
    record: EnterpriseDividendAnalyticsRecord
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


class EnterpriseDividendAnalyticsIntegration:
    def __init__(self, ledger: EnterpriseDividendAnalyticsLedger | None = None) -> None:
        self._ledger = ledger or EnterpriseDividendAnalyticsLedger()
        self._history: list[EnterpriseDividendAnalyticsResult] = []

    @property
    def ledger(self) -> EnterpriseDividendAnalyticsLedger:
        return self._ledger

    def history(self) -> tuple[EnterpriseDividendAnalyticsResult, ...]:
        return tuple(self._history)

    def analyze(self, income_records: tuple[EnterpriseDividendIncomeRecord, ...], forecast_records: tuple[EnterpriseIncomeForecastRecord, ...], *, expected_payments: int, completed_at: datetime | None = None) -> EnterpriseDividendAnalyticsResult:
        if not income_records or not forecast_records:
            raise PlatformValidationError("income and forecast records are required")
        if expected_payments <= 0:
            raise PlatformValidationError("expected_payments must be positive")
        for item in income_records:
            item.validate()
        for item in forecast_records:
            item.validate()
        first_income = income_records[0]
        first_forecast = forecast_records[0]
        if first_income.strategy_id != "DIVIDEND" or first_forecast.strategy_id != "DIVIDEND":
            raise PlatformValidationError("analytics supports DIVIDEND only")
        identity = (first_income.portfolio_integration_id, first_income.workflow_id, first_income.correlation_id, first_income.decision_internal_id, first_income.decision_public_id, first_income.company_id, first_income.profile_id, first_income.strategy_id)
        for item in income_records:
            candidate = (item.portfolio_integration_id, item.workflow_id, item.correlation_id, item.decision_internal_id, item.decision_public_id, item.company_id, item.profile_id, item.strategy_id)
            if candidate != identity:
                raise PlatformValidationError("income analytics records must preserve governed identity")
        for item in forecast_records:
            candidate = (item.portfolio_integration_id, item.workflow_id, item.correlation_id, item.decision_internal_id, item.decision_public_id, item.company_id, item.profile_id, item.strategy_id)
            if candidate != identity:
                raise PlatformValidationError("forecast analytics records must preserve governed identity")
        income_sequences = tuple(item.sequence for item in income_records)
        forecast_sequences = tuple(item.sequence for item in forecast_records)
        if income_sequences != tuple(sorted(income_sequences)) or len(set(income_sequences)) != len(income_sequences):
            raise PlatformValidationError("income records must be unique and ordered")
        if forecast_sequences != tuple(sorted(forecast_sequences)) or len(set(forecast_sequences)) != len(forecast_sequences):
            raise PlatformValidationError("forecast records must be unique and ordered")
        timestamp = completed_at or utc_now()
        if timestamp.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        latest_income = income_records[-1]
        latest_forecast = forecast_records[-1]
        trailing = round(float(latest_income.received_income), 8)
        forward = round(float(latest_forecast.projected_annual_income), 8)
        growth = None if trailing <= 0 else round(((forward - trailing) / trailing) * 100.0, 8)
        variance = round(forward - trailing, 8)
        consistency = round(min((latest_income.payment_count / expected_payments) * 100.0, 100.0), 8)
        flags: list[str] = []
        if latest_income.payment_count == 0:
            flags.append("NO_RECEIVED_PAYMENTS")
        if latest_income.pending_income > 0:
            flags.append("PENDING_INCOME")
        if latest_forecast.confidence < 70:
            flags.append("LOW_FORECAST_CONFIDENCE")
        if latest_forecast.status in {IncomeForecastStatus.REVIEW_REQUIRED, IncomeForecastStatus.SUSPENDED}:
            flags.append(latest_forecast.status.value)
        if growth is not None and growth < 0:
            flags.append("NEGATIVE_INCOME_GROWTH")
        evidence_ids = tuple(dict.fromkeys(evidence_id for item in (*income_records, *forecast_records) for evidence_id in item.evidence_ids))
        record = EnterpriseDividendAnalyticsRecord(
            analytics_id=IdentifierFactory.new_internal_id(), sequence=len(self._ledger.all()) + 1,
            portfolio_integration_id=first_income.portfolio_integration_id, workflow_id=first_income.workflow_id,
            correlation_id=first_income.correlation_id, decision_internal_id=first_income.decision_internal_id,
            decision_public_id=first_income.decision_public_id, company_id=first_income.company_id,
            profile_id=first_income.profile_id, strategy_id=first_income.strategy_id, evidence_ids=evidence_ids,
            source_income_record_ids=tuple(item.income_record_id for item in income_records),
            source_forecast_ids=tuple(item.forecast_id for item in forecast_records),
            trailing_received_income=trailing, forward_annual_income=forward, income_growth_percent=growth,
            projected_yield_percent=latest_forecast.projected_yield_percent, forecast_variance=variance,
            payment_consistency_percent=consistency, latest_forecast_confidence=latest_forecast.confidence,
            review_flags=tuple(flags), calculated_at=timestamp,
            metadata=MappingProxyType({"module_version": MODULE_VERSION, "analytical_only": True, "cash_moved": False, "portfolio_mutated": False, "append_only": True}),
        )
        self._ledger.append(record)
        result = EnterpriseDividendAnalyticsResult(record=record, completed_at=timestamp)
        result.validate()
        self._history.append(result)
        return result

    @staticmethod
    def render_json(result: EnterpriseDividendAnalyticsResult) -> str:
        result.validate()
        return JsonSerializer.dumps(result)

    @staticmethod
    def render_markdown(result: EnterpriseDividendAnalyticsResult) -> str:
        result.validate()
        item = result.record
        growth = "N/A" if item.income_growth_percent is None else f"{item.income_growth_percent:.2f}%"
        flags = ", ".join(item.review_flags) if item.review_flags else "NONE"
        return "\n".join([
            "# Enterprise Dividend Analytics Integration", "", f"- Sequence: {item.sequence}",
            f"- Decision ID: {item.decision_public_id}", f"- Strategy: {item.strategy_id}",
            f"- Trailing Received Income: ${item.trailing_received_income:,.2f}",
            f"- Forward Annual Income: ${item.forward_annual_income:,.2f}", f"- Income Growth: {growth}",
            f"- Projected Yield: {item.projected_yield_percent:.4f}%", f"- Forecast Variance: ${item.forecast_variance:,.2f}",
            f"- Payment Consistency: {item.payment_consistency_percent:.2f}%", f"- Forecast Confidence: {item.latest_forecast_confidence:.2f}%",
            f"- Review Flags: {flags}", f"- Cash Moved: {'YES' if item.metadata['cash_moved'] else 'NO'}",
            f"- Portfolio Mutated: {'YES' if item.metadata['portfolio_mutated'] else 'NO'}", "", "## Safety Boundary", "",
            "This integration calculates paper-only Dividend analytics. It does not move cash, alter balances, mutate holdings, call brokers, or place orders.", "",
        ])
