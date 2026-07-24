"""Read-only executive dashboard snapshots from governed Dividend reports."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from .enterprise_dividend_reporting_integration import EnterpriseDividendReportRecord
from .platform_foundation import IdentifierFactory, JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_dividend_dashboard_integration"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Create immutable read-only Dividend dashboard snapshots from governed reports."


@dataclass(frozen=True)
class EnterpriseDividendDashboardRecord:
    dashboard_id: UUID
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
    source_report_ids: tuple[UUID, ...]
    report_scopes: tuple[str, ...]
    trailing_received_income: float
    forward_annual_income: float
    projected_monthly_income: float
    projected_yield_percent: float
    payment_consistency_percent: float
    forecast_confidence: float
    review_flags: tuple[str, ...]
    dashboard_status: str
    generated_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if self.sequence < 1:
            raise PlatformValidationError("dashboard sequence must be positive")
        if self.strategy_id != "DIVIDEND":
            raise PlatformValidationError("dividend dashboard supports DIVIDEND only")
        if not self.workflow_id.strip() or not self.correlation_id.strip() or not self.decision_public_id.strip():
            raise PlatformValidationError("workflow, correlation, and decision IDs are required")
        if not self.evidence_ids or not self.source_report_ids or not self.report_scopes:
            raise PlatformValidationError("dashboard requires evidence, report, and scope links")
        if len(set(self.source_report_ids)) != len(self.source_report_ids):
            raise PlatformValidationError("source report IDs must be unique")
        if len(set(self.report_scopes)) != len(self.report_scopes):
            raise PlatformValidationError("report scopes must be unique")
        if min(self.trailing_received_income, self.forward_annual_income, self.projected_monthly_income, self.projected_yield_percent) < 0:
            raise PlatformValidationError("dashboard income and yield values must not be negative")
        if abs(self.projected_monthly_income - round(self.forward_annual_income / 12.0, 8)) > 1e-6:
            raise PlatformValidationError("monthly projection must equal annual income divided by 12")
        if not 0 <= self.payment_consistency_percent <= 100 or not 0 <= self.forecast_confidence <= 100:
            raise PlatformValidationError("consistency and confidence must be between 0 and 100")
        if len(set(self.review_flags)) != len(self.review_flags):
            raise PlatformValidationError("review flags must be unique")
        expected = "REVIEW_REQUIRED" if self.review_flags else "CLEAR"
        if self.dashboard_status != expected:
            raise PlatformValidationError("dashboard_status must reflect review flags")
        if self.generated_at.tzinfo is None:
            raise PlatformValidationError("generated_at must be timezone-aware")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterpriseDividendDashboardLedger:
    def __init__(self) -> None:
        self._records: list[EnterpriseDividendDashboardRecord] = []
        self._source_states: set[tuple[UUID, ...]] = set()

    def append(self, record: EnterpriseDividendDashboardRecord) -> None:
        record.validate()
        if record.sequence != len(self._records) + 1:
            raise PlatformValidationError("dashboard sequence must be append-only")
        if record.source_report_ids in self._source_states:
            raise PlatformValidationError("report state has already been dashboarded")
        self._records.append(record)
        self._source_states.add(record.source_report_ids)

    def all(self) -> tuple[EnterpriseDividendDashboardRecord, ...]:
        return tuple(self._records)


@dataclass(frozen=True)
class EnterpriseDividendDashboardResult:
    record: EnterpriseDividendDashboardRecord
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


class EnterpriseDividendDashboardIntegration:
    def __init__(self, ledger: EnterpriseDividendDashboardLedger | None = None) -> None:
        self._ledger = ledger or EnterpriseDividendDashboardLedger()
        self._history: list[EnterpriseDividendDashboardResult] = []

    @property
    def ledger(self) -> EnterpriseDividendDashboardLedger:
        return self._ledger

    def history(self) -> tuple[EnterpriseDividendDashboardResult, ...]:
        return tuple(self._history)

    def build_dashboard(self, reports: tuple[EnterpriseDividendReportRecord, ...], *, completed_at: datetime | None = None) -> EnterpriseDividendDashboardResult:
        if not reports:
            raise PlatformValidationError("at least one report is required")
        for item in reports:
            item.validate()
        first = reports[0]
        identity = (first.portfolio_integration_id, first.workflow_id, first.correlation_id, first.decision_internal_id, first.decision_public_id, first.company_id, first.profile_id, first.strategy_id)
        for item in reports:
            candidate = (item.portfolio_integration_id, item.workflow_id, item.correlation_id, item.decision_internal_id, item.decision_public_id, item.company_id, item.profile_id, item.strategy_id)
            if candidate != identity:
                raise PlatformValidationError("dashboard reports must preserve governed identity")
        sequences = tuple(item.sequence for item in reports)
        if sequences != tuple(sorted(sequences)) or len(set(sequences)) != len(sequences):
            raise PlatformValidationError("reports must be unique and ordered")
        timestamp = completed_at or utc_now()
        if timestamp.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        latest = reports[-1]
        evidence_ids = tuple(dict.fromkeys(eid for item in reports for eid in item.evidence_ids))
        flags = tuple(dict.fromkeys(flag for item in reports for flag in item.review_flags))
        scopes = tuple(dict.fromkeys(item.scope.value for item in reports))
        record = EnterpriseDividendDashboardRecord(
            dashboard_id=IdentifierFactory.new_internal_id(), sequence=len(self._ledger.all()) + 1,
            portfolio_integration_id=first.portfolio_integration_id, workflow_id=first.workflow_id,
            correlation_id=first.correlation_id, decision_internal_id=first.decision_internal_id,
            decision_public_id=first.decision_public_id, company_id=first.company_id,
            profile_id=first.profile_id, strategy_id=first.strategy_id, evidence_ids=evidence_ids,
            source_report_ids=tuple(item.report_id for item in reports), report_scopes=scopes,
            trailing_received_income=latest.trailing_received_income,
            forward_annual_income=latest.forward_annual_income,
            projected_monthly_income=round(latest.forward_annual_income / 12.0, 8),
            projected_yield_percent=latest.projected_yield_percent,
            payment_consistency_percent=latest.payment_consistency_percent,
            forecast_confidence=latest.latest_forecast_confidence,
            review_flags=flags, dashboard_status="REVIEW_REQUIRED" if flags else "CLEAR",
            generated_at=timestamp,
            metadata=MappingProxyType({"module_version": MODULE_VERSION, "presentation_only": True, "cash_moved": False, "portfolio_mutated": False, "append_only": True}),
        )
        self._ledger.append(record)
        result = EnterpriseDividendDashboardResult(record=record, completed_at=timestamp)
        result.validate()
        self._history.append(result)
        return result

    @staticmethod
    def render_json(result: EnterpriseDividendDashboardResult) -> str:
        result.validate()
        return JsonSerializer.dumps(result)

    @staticmethod
    def render_markdown(result: EnterpriseDividendDashboardResult) -> str:
        result.validate()
        item = result.record
        flags = ", ".join(item.review_flags) if item.review_flags else "NONE"
        return "\n".join([
            "# Enterprise Dividend Dashboard", "",
            f"- Decision ID: {item.decision_public_id}", f"- Strategy: {item.strategy_id}",
            f"- Dashboard Status: {item.dashboard_status}", f"- Report Scopes: {', '.join(item.report_scopes)}",
            f"- Trailing Received Income: ${item.trailing_received_income:,.2f}",
            f"- Forward Annual Income: ${item.forward_annual_income:,.2f}",
            f"- Projected Monthly Income: ${item.projected_monthly_income:,.2f}",
            f"- Projected Yield: {item.projected_yield_percent:.4f}%",
            f"- Payment Consistency: {item.payment_consistency_percent:.2f}%",
            f"- Forecast Confidence: {item.forecast_confidence:.2f}%", f"- Review Flags: {flags}", "",
            "## Safety Boundary", "",
            "This dashboard is read-only and paper-only. It does not approve investments, move cash, alter balances, mutate holdings, call brokers, or place orders.", "",
        ])
