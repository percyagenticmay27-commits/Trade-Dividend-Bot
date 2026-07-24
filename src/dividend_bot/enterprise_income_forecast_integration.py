"""Append-only paper dividend income forecasting from governed income summaries.

This module creates immutable forecasts only. It does not move cash, alter balances, mutate
holdings, call brokers, or place orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from .enterprise_dividend_income_integration import EnterpriseDividendIncomeRecord
from .platform_foundation import IdentifierFactory, JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_income_forecast_integration"
MODULE_VERSION = "1.0.1"
MODULE_DESCRIPTION = "Create immutable paper Dividend income forecasts from governed income summaries."


class IncomeForecastStatus(str, Enum):
    ACTIVE = "ACTIVE"
    UPDATED = "UPDATED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    SUSPENDED = "SUSPENDED"


@dataclass(frozen=True)
class EnterpriseIncomeForecastRecord:
    forecast_id: UUID
    sequence: int
    source_income_record_id: UUID
    portfolio_integration_id: UUID
    workflow_id: str
    correlation_id: str
    decision_internal_id: UUID
    decision_public_id: str
    company_id: UUID
    profile_id: UUID
    strategy_id: str
    evidence_ids: tuple[UUID, ...]
    status: IncomeForecastStatus
    share_count: float
    payments_per_year: int
    market_value: float
    projected_next_payment: float
    projected_annual_income: float
    projected_yield_percent: float
    confidence: float
    next_payment_date: date | None
    forecasted_at: datetime = field(default_factory=utc_now)
    supersedes_forecast_id: UUID | None = None
    metadata: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if self.sequence < 1:
            raise PlatformValidationError("forecast sequence must be positive")
        if not self.workflow_id.strip() or not self.correlation_id.strip() or not self.decision_public_id.strip():
            raise PlatformValidationError("workflow, correlation, and decision IDs are required")
        if self.strategy_id != "DIVIDEND":
            raise PlatformValidationError("income forecast integration supports DIVIDEND only")
        if not self.evidence_ids:
            raise PlatformValidationError("income forecast requires evidence links")
        if self.share_count <= 0:
            raise PlatformValidationError("share_count must be greater than zero")
        if self.payments_per_year <= 0:
            raise PlatformValidationError("payments_per_year must be greater than zero")
        if self.market_value <= 0:
            raise PlatformValidationError("market_value must be greater than zero")
        if min(self.projected_next_payment, self.projected_annual_income, self.projected_yield_percent) < 0:
            raise PlatformValidationError("forecast values must not be negative")
        expected_annual = round(self.projected_next_payment * self.payments_per_year, 8)
        if abs(self.projected_annual_income - expected_annual) > 1e-6:
            raise PlatformValidationError("projected annual income must equal next payment times payment frequency")
        expected_yield = round((self.projected_annual_income / self.market_value) * 100.0, 8)
        if abs(self.projected_yield_percent - expected_yield) > 1e-6:
            raise PlatformValidationError("projected yield must equal annual income divided by market value")
        if not 0 <= self.confidence <= 100:
            raise PlatformValidationError("confidence must be between 0 and 100")
        if self.status is IncomeForecastStatus.UPDATED and self.supersedes_forecast_id is None:
            raise PlatformValidationError("updated forecasts must supersede a prior forecast")
        if self.status is IncomeForecastStatus.SUSPENDED:
            if self.projected_next_payment != 0 or self.projected_annual_income != 0 or self.projected_yield_percent != 0:
                raise PlatformValidationError("suspended forecasts must contain zero projected income")
        elif self.next_payment_date is None:
            raise PlatformValidationError("active forecast states require next_payment_date")
        if self.forecasted_at.tzinfo is None:
            raise PlatformValidationError("forecasted_at must be timezone-aware")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterpriseIncomeForecastLedger:
    """Append-only forecast ledger with source-state and chain validation."""

    def __init__(self) -> None:
        self._records: list[EnterpriseIncomeForecastRecord] = []
        self._source_income_ids: set[UUID] = set()
        self._forecast_ids: set[UUID] = set()

    def append(self, record: EnterpriseIncomeForecastRecord) -> None:
        record.validate()
        if record.sequence != len(self._records) + 1:
            raise PlatformValidationError("forecast sequence must be append-only")
        if record.forecast_id in self._forecast_ids:
            raise PlatformValidationError("forecast record already exists")
        if record.source_income_record_id in self._source_income_ids:
            raise PlatformValidationError("income summary has already been forecast")
        previous = self.latest_for_portfolio(record.portfolio_integration_id)
        expected_previous = previous.forecast_id if previous else None
        if record.supersedes_forecast_id != expected_previous:
            raise PlatformValidationError("forecast must link to the immediately previous portfolio forecast")
        if previous is None and record.status is IncomeForecastStatus.UPDATED:
            raise PlatformValidationError("first portfolio forecast cannot use UPDATED status")
        if previous is not None:
            if previous.company_id != record.company_id or previous.profile_id != record.profile_id:
                raise PlatformValidationError("forecast chain must preserve company and profile scope")
            if previous.strategy_id != record.strategy_id:
                raise PlatformValidationError("forecast chain must preserve strategy scope")
        self._records.append(record)
        self._source_income_ids.add(record.source_income_record_id)
        self._forecast_ids.add(record.forecast_id)

    def all(self) -> tuple[EnterpriseIncomeForecastRecord, ...]:
        return tuple(self._records)

    def for_portfolio(self, portfolio_integration_id: UUID) -> tuple[EnterpriseIncomeForecastRecord, ...]:
        return tuple(item for item in self._records if item.portfolio_integration_id == portfolio_integration_id)

    def latest_for_portfolio(self, portfolio_integration_id: UUID) -> EnterpriseIncomeForecastRecord | None:
        rows = self.for_portfolio(portfolio_integration_id)
        return rows[-1] if rows else None


@dataclass(frozen=True)
class EnterpriseIncomeForecastResult:
    record: EnterpriseIncomeForecastRecord
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


class EnterpriseIncomeForecastIntegration:
    def __init__(self, ledger: EnterpriseIncomeForecastLedger | None = None) -> None:
        self._ledger = ledger or EnterpriseIncomeForecastLedger()
        self._history: list[EnterpriseIncomeForecastResult] = []

    @property
    def ledger(self) -> EnterpriseIncomeForecastLedger:
        return self._ledger

    def history(self) -> tuple[EnterpriseIncomeForecastResult, ...]:
        return tuple(self._history)

    def forecast(
        self,
        income: EnterpriseDividendIncomeRecord,
        *,
        share_count: float,
        payments_per_year: int,
        market_value: float,
        next_payment_date: date | None,
        confidence: float,
        status: IncomeForecastStatus = IncomeForecastStatus.ACTIVE,
        completed_at: datetime | None = None,
    ) -> EnterpriseIncomeForecastResult:
        income.validate()
        if income.strategy_id != "DIVIDEND":
            raise PlatformValidationError("only DIVIDEND income records may be forecast")

        resolved_share_count = float(share_count)
        resolved_payments_per_year = int(payments_per_year)
        resolved_market_value = float(market_value)
        if resolved_share_count <= 0:
            raise PlatformValidationError("share_count must be greater than zero")
        if resolved_payments_per_year <= 0:
            raise PlatformValidationError("payments_per_year must be greater than zero")
        if resolved_market_value <= 0:
            raise PlatformValidationError("market_value must be greater than zero")

        timestamp = completed_at or utc_now()
        if timestamp.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        previous = self._ledger.latest_for_portfolio(income.portfolio_integration_id)
        resolved_status = status
        if previous is not None and status is IncomeForecastStatus.ACTIVE:
            resolved_status = IncomeForecastStatus.UPDATED

        amount_per_share = float(income.latest_amount_per_share or 0.0)
        next_payment = 0.0 if resolved_status is IncomeForecastStatus.SUSPENDED else round(amount_per_share * resolved_share_count, 8)
        annual_income = round(next_payment * resolved_payments_per_year, 8)
        projected_yield = round((annual_income / resolved_market_value) * 100.0, 8)
        record = EnterpriseIncomeForecastRecord(
            forecast_id=IdentifierFactory.new_internal_id(),
            sequence=len(self._ledger.all()) + 1,
            source_income_record_id=income.income_record_id,
            portfolio_integration_id=income.portfolio_integration_id,
            workflow_id=income.workflow_id,
            correlation_id=income.correlation_id,
            decision_internal_id=income.decision_internal_id,
            decision_public_id=income.decision_public_id,
            company_id=income.company_id,
            profile_id=income.profile_id,
            strategy_id=income.strategy_id,
            evidence_ids=income.evidence_ids,
            status=resolved_status,
            share_count=resolved_share_count,
            payments_per_year=resolved_payments_per_year,
            market_value=resolved_market_value,
            projected_next_payment=next_payment,
            projected_annual_income=annual_income,
            projected_yield_percent=projected_yield,
            confidence=float(confidence),
            next_payment_date=None if resolved_status is IncomeForecastStatus.SUSPENDED else next_payment_date,
            forecasted_at=timestamp,
            supersedes_forecast_id=previous.forecast_id if previous else None,
            metadata=MappingProxyType({
                "module_version": MODULE_VERSION,
                "cash_moved": False,
                "portfolio_mutated": False,
                "predictive_only": True,
                "append_only": True,
            }),
        )
        self._ledger.append(record)
        result = EnterpriseIncomeForecastResult(record=record, completed_at=timestamp)
        result.validate()
        self._history.append(result)
        return result

    @staticmethod
    def render_json(result: EnterpriseIncomeForecastResult) -> str:
        result.validate()
        return JsonSerializer.dumps(result)

    @staticmethod
    def render_markdown(result: EnterpriseIncomeForecastResult) -> str:
        result.validate()
        item = result.record
        return "\n".join([
            "# Enterprise Income Forecast Integration", "",
            f"- Sequence: {item.sequence}",
            f"- Decision ID: {item.decision_public_id}",
            f"- Strategy: {item.strategy_id}",
            f"- Status: {item.status.value}",
            f"- Next Payment Date: {item.next_payment_date or 'N/A'}",
            f"- Projected Next Payment: ${item.projected_next_payment:,.2f}",
            f"- Projected Annual Income: ${item.projected_annual_income:,.2f}",
            f"- Projected Yield: {item.projected_yield_percent:.4f}%",
            f"- Confidence: {item.confidence:.2f}%",
            f"- Cash Moved: {'YES' if item.metadata['cash_moved'] else 'NO'}",
            f"- Portfolio Mutated: {'YES' if item.metadata['portfolio_mutated'] else 'NO'}",
            f"- Paper Trade Mode: {'YES' if item.paper_trade_mode else 'NO'}", "",
            "## Safety Boundary", "",
            "This integration creates predictive paper-income records only. It does not move cash, alter balances, mutate holdings, call brokers, or place orders.", "",
        ])
