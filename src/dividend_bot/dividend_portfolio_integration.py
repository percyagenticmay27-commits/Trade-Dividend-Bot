"""Connect isolated Dividend paper-execution records to the Enterprise Portfolio.

Only accepted, governed Dividend paper records may create or close paper positions. The
integration preserves decision and request traceability, never moves cash, and exposes no
broker or live-order interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from .dividend_enterprise_execution import (
    DividendPaperDisposition,
    DividendPaperExecutionRecord,
)
from .dividend_strategy_adapter import DIVIDEND_STRATEGY_ID
from .enterprise_portfolio import EnterprisePortfolio, EnterprisePosition
from .enterprise_strategy_execution import StrategyResponseStatus
from .platform_foundation import JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "dividend_portfolio_integration"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Apply governed Dividend paper execution records to the Enterprise Portfolio."


class DividendPortfolioAction(str, Enum):
    OPENED = "OPENED"
    CLOSED = "CLOSED"
    NO_POSITION_CHANGE = "NO_POSITION_CHANGE"


@dataclass(frozen=True)
class DividendPortfolioIntegrationRecord:
    integration_id: UUID
    execution_record_id: UUID
    decision_id: UUID
    decision_public_id: str
    execution_request_id: UUID
    strategy_id: str
    action: DividendPortfolioAction
    position: EnterprisePosition | None
    explanation: str
    integrated_at: datetime = field(default_factory=utc_now)
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if self.strategy_id != DIVIDEND_STRATEGY_ID:
            raise PlatformValidationError("Dividend portfolio integration must preserve DIVIDEND scope")
        if not self.decision_public_id.strip() or not self.explanation.strip():
            raise PlatformValidationError("decision_public_id and explanation are required")
        if self.integrated_at.tzinfo is None:
            raise PlatformValidationError("integrated_at must be timezone-aware")
        if self.action in {DividendPortfolioAction.OPENED, DividendPortfolioAction.CLOSED}:
            if self.position is None:
                raise PlatformValidationError("position-changing integration requires a position")
            self.position.validate()
            if self.position.strategy_id != DIVIDEND_STRATEGY_ID:
                raise PlatformValidationError("integrated position must belong to DIVIDEND")
            if self.position.decision_id != self.decision_id:
                raise PlatformValidationError("position decision_id must match integration decision")
            if self.position.execution_request_id != self.execution_request_id and self.action is DividendPortfolioAction.OPENED:
                raise PlatformValidationError("opened position must link to the execution request")
        elif self.position is not None:
            raise PlatformValidationError("NO_POSITION_CHANGE must not carry a position")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class DividendPortfolioIntegrationService:
    """Apply Dividend paper dispositions to the shared Enterprise Portfolio."""

    def __init__(self, portfolio: EnterprisePortfolio) -> None:
        self._portfolio = portfolio
        self._records: list[DividendPortfolioIntegrationRecord] = []
        self._processed_execution_ids: set[UUID] = set()

    def records(self) -> tuple[DividendPortfolioIntegrationRecord, ...]:
        return tuple(self._records)

    def apply(
        self,
        execution: DividendPaperExecutionRecord,
        *,
        asset_symbol: str,
        asset_type: str = "EQUITY",
        quantity: float | None = None,
        price: float | None = None,
        position_id: UUID | None = None,
        explanation: str,
        integrated_at: datetime | None = None,
    ) -> DividendPortfolioIntegrationRecord:
        execution.validate()
        if execution.record_id in self._processed_execution_ids:
            raise PlatformValidationError("Dividend paper execution has already been integrated")
        if execution.request.strategy_id != DIVIDEND_STRATEGY_ID:
            raise PlatformValidationError("Dividend portfolio service cannot process another strategy")
        if execution.response.status is not StrategyResponseStatus.ACCEPTED:
            raise PlatformValidationError("only accepted Dividend execution records may reach the portfolio")
        if not explanation.strip():
            raise PlatformValidationError("integration explanation is required")

        disposition = execution.disposition
        position: EnterprisePosition | None = None
        action = DividendPortfolioAction.NO_POSITION_CHANGE

        if disposition is DividendPaperDisposition.PAPER_BUY_REVIEW:
            if quantity is None or price is None:
                raise PlatformValidationError("paper-buy integration requires quantity and price")
            position = self._portfolio.open_position(
                execution.request,
                asset_symbol=asset_symbol,
                asset_type=asset_type,
                quantity=float(quantity),
                entry_price=float(price),
                reason=explanation,
                opened_at=integrated_at,
            )
            action = DividendPortfolioAction.OPENED
        elif disposition is DividendPaperDisposition.EXIT_REVIEW:
            if position_id is None or price is None:
                raise PlatformValidationError("exit integration requires position_id and price")
            position = self._portfolio.close_position(
                position_id,
                strategy_id=DIVIDEND_STRATEGY_ID,
                exit_price=float(price),
                reason=explanation,
                closed_at=integrated_at,
            )
            action = DividendPortfolioAction.CLOSED
        elif disposition in {
            DividendPaperDisposition.HOLD_REVIEW,
            DividendPaperDisposition.WATCHLIST,
        }:
            action = DividendPortfolioAction.NO_POSITION_CHANGE
        else:
            raise PlatformValidationError("deferred Dividend execution cannot be applied to the portfolio")

        record = DividendPortfolioIntegrationRecord(
            integration_id=uuid4(),
            execution_record_id=execution.record_id,
            decision_id=execution.request.decision_id,
            decision_public_id=execution.request.decision_public_id,
            execution_request_id=execution.request.request_id,
            strategy_id=DIVIDEND_STRATEGY_ID,
            action=action,
            position=position,
            explanation=explanation,
            integrated_at=integrated_at or utc_now(),
        )
        record.validate()
        self._records.append(record)
        self._processed_execution_ids.add(execution.record_id)
        return record

    @staticmethod
    def render_json(record: DividendPortfolioIntegrationRecord) -> str:
        record.validate()
        return JsonSerializer.dumps(record)

    @staticmethod
    def render_markdown(record: DividendPortfolioIntegrationRecord) -> str:
        record.validate()
        position_id = str(record.position.position_id) if record.position else "NONE"
        return "\n".join(
            [
                "# Dividend Enterprise Portfolio Integration",
                "",
                f"- Decision ID: {record.decision_public_id}",
                f"- Execution Request ID: {record.execution_request_id}",
                f"- Strategy: {record.strategy_id}",
                f"- Portfolio Action: {record.action.value}",
                f"- Position ID: {position_id}",
                f"- Paper Trade Mode: {'YES' if record.paper_trade_mode else 'NO'}",
                "",
                "## Explanation",
                "",
                record.explanation,
                "",
                "## Portfolio Boundary",
                "",
                "This record updates only the paper Enterprise Portfolio. It does not move cash, place orders, or call broker APIs.",
                "",
            ]
        )
