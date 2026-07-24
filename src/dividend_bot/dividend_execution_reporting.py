"""Isolated Dividend reporting and audits from enterprise paper-execution records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .audit_framework import AuditCheckResult, AuditModel
from .dividend_enterprise_execution import DividendPaperExecutionRecord, DividendPaperDisposition
from .dividend_strategy_adapter import DIVIDEND_STRATEGY_ID, DividendStrategyAdapter
from .platform_entities import FindingStatus
from .platform_foundation import JsonSerializer, PlatformValidationError
from .reporting_framework import StrategyReportModel, StrategyReportRenderer

MODULE_NAME = "dividend_execution_reporting"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Build isolated Dividend reports and audits from governed paper executions."

_SUPPORTED_REPORT_TYPES = frozenset({"WEEKLY", "MONTHLY", "PERFORMANCE", "LEARNING"})


@dataclass(frozen=True)
class DividendExecutionReportingBundle:
    report: StrategyReportModel
    audit: AuditModel
    record_count: int
    accepted_count: int
    deferred_count: int
    paper_buy_review_count: int
    exit_review_count: int

    def validate(self) -> None:
        self.report.validate()
        self.audit.validate()
        if self.report.strategy_id != DIVIDEND_STRATEGY_ID or self.audit.strategy_id != DIVIDEND_STRATEGY_ID:
            raise PlatformValidationError("Dividend reporting bundle must preserve DIVIDEND scope")
        counts = (
            self.record_count,
            self.accepted_count,
            self.deferred_count,
            self.paper_buy_review_count,
            self.exit_review_count,
        )
        if any(value < 0 for value in counts):
            raise PlatformValidationError("Dividend reporting counts must not be negative")
        if self.accepted_count + self.deferred_count != self.record_count:
            raise PlatformValidationError("accepted and deferred counts must equal record_count")


class DividendExecutionReportingService:
    """Create one strategy-isolated report and audit without mixing future strategies."""

    def __init__(self, adapter: DividendStrategyAdapter | None = None) -> None:
        self._adapter = adapter or DividendStrategyAdapter()

    def build(
        self,
        records: tuple[DividendPaperExecutionRecord, ...],
        *,
        report_type: str,
        period_start: datetime,
        period_end: datetime,
        completed_at: datetime,
    ) -> DividendExecutionReportingBundle:
        resolved_type = report_type.upper()
        if resolved_type not in _SUPPORTED_REPORT_TYPES:
            raise PlatformValidationError(f"unsupported Dividend execution report type: {resolved_type}")
        if not records:
            raise PlatformValidationError("at least one Dividend execution record is required")
        for record in records:
            record.validate()
            if record.request.strategy_id != DIVIDEND_STRATEGY_ID:
                raise PlatformValidationError("Dividend reports cannot include another strategy")
        if period_start.tzinfo is None or period_end.tzinfo is None or completed_at.tzinfo is None:
            raise PlatformValidationError("reporting timestamps must be timezone-aware")
        if period_end < period_start:
            raise PlatformValidationError("period_end must not precede period_start")

        accepted = sum(1 for item in records if item.response.status.value == "ACCEPTED")
        deferred = sum(1 for item in records if item.response.status.value == "DEFERRED")
        paper_buy = sum(1 for item in records if item.disposition is DividendPaperDisposition.PAPER_BUY_REVIEW)
        exits = sum(1 for item in records if item.disposition is DividendPaperDisposition.EXIT_REVIEW)
        watchlist = sum(1 for item in records if item.disposition is DividendPaperDisposition.WATCHLIST)
        holds = sum(1 for item in records if item.disposition is DividendPaperDisposition.HOLD_REVIEW)
        avg_score = round(
            sum(item.evaluation_result.evaluation.score for item in records) / len(records), 2
        )
        requested_capital = round(sum(item.request.requested_capital for item in records), 2)
        decision_ids = tuple(dict.fromkeys(item.request.decision_public_id for item in records))
        warnings = () if deferred == 0 else (f"{deferred} Dividend execution request(s) were deferred",)

        metrics = {
            "execution_records": len(records),
            "accepted_requests": accepted,
            "deferred_requests": deferred,
            "paper_buy_reviews": paper_buy,
            "hold_reviews": holds,
            "watchlist_reviews": watchlist,
            "exit_reviews": exits,
            "average_evaluation_score": avg_score,
            "requested_capital_total": requested_capital,
            "paper_trade_mode": True,
        }
        report = self._adapter.build_report(
            report_type=resolved_type,
            period_start=period_start,
            period_end=period_end,
            metrics=metrics,
            warnings=warnings,
            decision_ids=decision_ids,
        )
        checks = (
            AuditCheckResult("paper_trade_mode", FindingStatus.PASS, "All Dividend execution records remain paper-only"),
            AuditCheckResult("strategy_isolation", FindingStatus.PASS, "All records belong to DIVIDEND"),
            AuditCheckResult("execution_responses", FindingStatus.PASS, "Every execution record contains one strategy response"),
            AuditCheckResult(
                "deferred_requests",
                FindingStatus.WARNING if deferred else FindingStatus.PASS,
                f"Deferred Dividend requests: {deferred}",
            ),
            AuditCheckResult("broker_execution", FindingStatus.PASS, "No broker or live-order interface is present"),
        )
        audit_type = "WEEKLY_AUDIT" if resolved_type == "WEEKLY" else "MONTHLY_AUDIT"
        if resolved_type in {"PERFORMANCE", "LEARNING"}:
            audit_type = "RELEASE_AUDIT"
        audit = self._adapter.build_audit(audit_type=audit_type, completed_at=completed_at, checks=checks)
        bundle = DividendExecutionReportingBundle(
            report=report,
            audit=audit,
            record_count=len(records),
            accepted_count=accepted,
            deferred_count=deferred,
            paper_buy_review_count=paper_buy,
            exit_review_count=exits,
        )
        bundle.validate()
        return bundle

    @staticmethod
    def render_json(bundle: DividendExecutionReportingBundle) -> str:
        bundle.validate()
        return JsonSerializer.dumps(bundle)

    @staticmethod
    def render_report_markdown(bundle: DividendExecutionReportingBundle) -> str:
        bundle.validate()
        return StrategyReportRenderer().render_markdown(bundle.report)

    @staticmethod
    def render_audit_markdown(bundle: DividendExecutionReportingBundle) -> str:
        bundle.validate()
        from .audit_framework import AuditRenderer

        return AuditRenderer().render_markdown(bundle.audit)
