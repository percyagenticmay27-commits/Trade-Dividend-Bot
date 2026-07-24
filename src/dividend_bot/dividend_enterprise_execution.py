"""Dividend-specific paper execution integration for governed enterprise requests.

This module consumes only routed DIVIDEND execution requests, evaluates the shared MCIP
through the existing Dividend Strategy adapter, records an isolated paper result, and
submits one audited strategy response. It never reserves capital, places orders, or calls
broker APIs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from .dividend_strategy_adapter import (
    DIVIDEND_STRATEGY_ID,
    DividendEvaluationResult,
    DividendStrategyAdapter,
)
from .enterprise_strategy_execution import (
    EnterpriseStrategyExecutionCoordinator,
    StrategyExecutionRequest,
    StrategyExecutionResponse,
    StrategyResponseStatus,
)
from .platform_entities import MasterCompanyIntelligenceProfile
from .platform_foundation import JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "dividend_enterprise_execution"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Process governed enterprise requests through the isolated Dividend paper strategy."


class DividendPaperDisposition(str, Enum):
    PAPER_BUY_REVIEW = "PAPER_BUY_REVIEW"
    HOLD_REVIEW = "HOLD_REVIEW"
    WATCHLIST = "WATCHLIST"
    EXIT_REVIEW = "EXIT_REVIEW"
    DEFERRED = "DEFERRED"


@dataclass(frozen=True)
class DividendPaperExecutionRecord:
    record_id: UUID
    request: StrategyExecutionRequest
    evaluation_result: DividendEvaluationResult
    response: StrategyExecutionResponse
    disposition: DividendPaperDisposition
    processed_at: datetime = field(default_factory=utc_now)
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        self.request.validate()
        self.evaluation_result.evaluation.validate()
        self.evaluation_result.recommendation.validate()
        self.response.validate()
        if self.request.strategy_id != DIVIDEND_STRATEGY_ID:
            raise PlatformValidationError("Dividend execution requires a DIVIDEND request")
        if self.response.strategy_id != DIVIDEND_STRATEGY_ID:
            raise PlatformValidationError("Dividend response must preserve strategy isolation")
        if self.response.request_id != self.request.request_id:
            raise PlatformValidationError("Dividend response must reference the routed request")
        if self.evaluation_result.evaluation.strategy_id != DIVIDEND_STRATEGY_ID:
            raise PlatformValidationError("Dividend evaluation must preserve strategy isolation")
        if self.processed_at.tzinfo is None:
            raise PlatformValidationError("processed_at must be timezone-aware")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class DividendEnterpriseExecutionService:
    """Translate a governed enterprise request into an isolated Dividend paper record."""

    _BUY_ACTIONS = frozenset({"BUY", "ACCUMULATE", "ADD"})
    _HOLD_ACTIONS = frozenset({"HOLD", "WATCH", "REVIEW", "DO_NOT_BUY"})
    _EXIT_ACTIONS = frozenset({"SELL", "EXIT"})

    def __init__(
        self,
        coordinator: EnterpriseStrategyExecutionCoordinator,
        adapter: DividendStrategyAdapter | None = None,
    ) -> None:
        self._coordinator = coordinator
        self._adapter = adapter or DividendStrategyAdapter()
        self._records: list[DividendPaperExecutionRecord] = []

    def records(self) -> tuple[DividendPaperExecutionRecord, ...]:
        return tuple(self._records)

    def process(
        self,
        request: StrategyExecutionRequest,
        profile: MasterCompanyIntelligenceProfile,
        *,
        processed_at: datetime | None = None,
    ) -> DividendPaperExecutionRecord:
        request.validate()
        profile.validate()
        if request.strategy_id != DIVIDEND_STRATEGY_ID:
            raise PlatformValidationError("Dividend service cannot process another strategy's request")
        if any(item.request.request_id == request.request_id for item in self._records):
            raise PlatformValidationError("Dividend execution request has already been processed")

        evaluation = self._adapter.evaluate(profile)
        disposition, response_status, explanation = self._resolve_outcome(request, evaluation)
        response = self._coordinator.respond(
            request.request_id,
            strategy_id=DIVIDEND_STRATEGY_ID,
            status=response_status,
            explanation=explanation,
            responded_at=processed_at,
        )
        record = DividendPaperExecutionRecord(
            record_id=uuid4(),
            request=request,
            evaluation_result=evaluation,
            response=response,
            disposition=disposition,
            processed_at=processed_at or utc_now(),
        )
        record.validate()
        self._records.append(record)
        return record

    def _resolve_outcome(
        self,
        request: StrategyExecutionRequest,
        evaluation: DividendEvaluationResult,
    ) -> tuple[DividendPaperDisposition, StrategyResponseStatus, str]:
        action = request.effective_action.upper()
        recommendation = evaluation.recommendation.paper_action.upper()
        if action in self._BUY_ACTIONS:
            if recommendation == "REVIEW_FOR_PAPER_BUY":
                return (
                    DividendPaperDisposition.PAPER_BUY_REVIEW,
                    StrategyResponseStatus.ACCEPTED,
                    "Dividend strategy accepted the governed request for paper-buy review.",
                )
            return (
                DividendPaperDisposition.DEFERRED,
                StrategyResponseStatus.DEFERRED,
                "Dividend strategy deferred the governed buy because current Dividend suitability is insufficient.",
            )
        if action in self._EXIT_ACTIONS:
            return (
                DividendPaperDisposition.EXIT_REVIEW,
                StrategyResponseStatus.ACCEPTED,
                "Dividend strategy accepted the governed request for paper exit review.",
            )
        if action in self._HOLD_ACTIONS:
            disposition = (
                DividendPaperDisposition.WATCHLIST
                if recommendation == "WATCHLIST"
                else DividendPaperDisposition.HOLD_REVIEW
            )
            return (
                disposition,
                StrategyResponseStatus.ACCEPTED,
                "Dividend strategy accepted the governed request for non-transactional paper monitoring.",
            )
        raise PlatformValidationError(f"unsupported enterprise action for Dividend: {action}")

    @staticmethod
    def render_json(record: DividendPaperExecutionRecord) -> str:
        record.validate()
        return JsonSerializer.dumps(record)

    @staticmethod
    def render_markdown(record: DividendPaperExecutionRecord) -> str:
        record.validate()
        return "\n".join(
            [
                "# Dividend Enterprise Paper Execution",
                "",
                f"- Decision ID: {record.request.decision_public_id}",
                f"- Request ID: {record.request.request_id}",
                f"- Strategy: {record.request.strategy_id}",
                f"- Enterprise Action: {record.request.effective_action}",
                f"- Dividend Disposition: {record.disposition.value}",
                f"- Strategy Response: {record.response.status.value}",
                f"- Requested Capital: ${record.request.requested_capital:,.2f}",
                f"- Dividend Evaluation Score: {record.evaluation_result.evaluation.score:.1f}",
                f"- Paper Trade Mode: {'YES' if record.paper_trade_mode else 'NO'}",
                "",
                "## Dividend Rationale",
                "",
                record.evaluation_result.evaluation.rationale,
                "",
                "## Execution Boundary",
                "",
                "This is an isolated Dividend paper-execution record. It does not reserve capital, place orders, or call broker APIs.",
                "",
            ]
        )
