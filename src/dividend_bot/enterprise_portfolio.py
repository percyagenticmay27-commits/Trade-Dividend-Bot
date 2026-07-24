"""Enterprise-owned, multi-strategy paper portfolio with strict strategy isolation.

The portfolio records paper positions linked to governed decisions and strategy execution
requests. It never places broker orders, moves real cash, or enables live trading.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from .enterprise_capital_manager import EnterpriseCapitalManager
from .enterprise_strategy_execution import StrategyExecutionRequest
from .platform_foundation import JsonSerializer, PlatformValidationError, utc_now
from .strategy_framework import StrategyRegistry, StrategyStatus

MODULE_NAME = "enterprise_portfolio"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Enterprise-owned paper positions across isolated strategy allocations."


class EnterprisePositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class PortfolioEventType(str, Enum):
    OPENED = "OPENED"
    MARKED = "MARKED"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class EnterprisePosition:
    position_id: UUID
    strategy_id: str
    asset_symbol: str
    asset_type: str
    decision_id: UUID
    decision_public_id: str
    execution_request_id: UUID
    quantity: float
    entry_price: float
    current_price: float
    allocated_cost: float
    status: EnterprisePositionStatus
    opened_at: datetime
    closed_at: datetime | None = None
    realized_profit_loss: float = 0.0
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if not self.strategy_id or self.strategy_id != self.strategy_id.upper():
            raise PlatformValidationError("position strategy_id must be non-empty uppercase text")
        if not self.asset_symbol or self.asset_symbol != self.asset_symbol.upper():
            raise PlatformValidationError("asset_symbol must be non-empty uppercase text")
        if not self.asset_type.strip() or not self.decision_public_id.strip():
            raise PlatformValidationError("asset_type and decision_public_id are required")
        if self.quantity <= 0 or self.entry_price <= 0 or self.current_price <= 0:
            raise PlatformValidationError("position quantity and prices must be greater than zero")
        expected_cost = round(self.quantity * self.entry_price, 8)
        if abs(self.allocated_cost - expected_cost) > 1e-6:
            raise PlatformValidationError("allocated_cost must equal quantity multiplied by entry_price")
        if self.opened_at.tzinfo is None:
            raise PlatformValidationError("opened_at must be timezone-aware")
        if self.status is EnterprisePositionStatus.OPEN and self.closed_at is not None:
            raise PlatformValidationError("open positions must not have closed_at")
        if self.status is EnterprisePositionStatus.CLOSED:
            if self.closed_at is None or self.closed_at.tzinfo is None:
                raise PlatformValidationError("closed positions require timezone-aware closed_at")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")

    @property
    def current_value(self) -> float:
        return round(self.quantity * self.current_price, 8)

    @property
    def unrealized_profit_loss(self) -> float:
        if self.status is EnterprisePositionStatus.CLOSED:
            return 0.0
        return round(self.current_value - self.allocated_cost, 8)


@dataclass(frozen=True)
class PortfolioEvent:
    event_id: UUID
    event_type: PortfolioEventType
    position_id: UUID
    strategy_id: str
    previous_price: float | None
    new_price: float
    reason: str
    occurred_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        if not self.strategy_id or self.strategy_id != self.strategy_id.upper():
            raise PlatformValidationError("portfolio event strategy_id must be uppercase")
        if self.previous_price is not None and self.previous_price <= 0:
            raise PlatformValidationError("previous_price must be greater than zero")
        if self.new_price <= 0 or not self.reason.strip():
            raise PlatformValidationError("new_price and reason are required")
        if self.occurred_at.tzinfo is None:
            raise PlatformValidationError("portfolio event timestamp must be timezone-aware")


@dataclass(frozen=True)
class StrategyPortfolioSummary:
    strategy_id: str
    allocated_capital: float
    open_cost_basis: float
    remaining_allocated_capital: float
    current_value: float
    unrealized_profit_loss: float
    realized_profit_loss: float
    open_position_count: int
    closed_position_count: int

    def validate(self) -> None:
        if not self.strategy_id or self.strategy_id != self.strategy_id.upper():
            raise PlatformValidationError("summary strategy_id must be uppercase")
        if self.allocated_capital < 0 or self.open_cost_basis < 0 or self.current_value < 0:
            raise PlatformValidationError("portfolio summary capital values must not be negative")
        if self.remaining_allocated_capital < -1e-6:
            raise PlatformValidationError("remaining strategy capital must not be negative")
        if self.open_position_count < 0 or self.closed_position_count < 0:
            raise PlatformValidationError("position counts must not be negative")


@dataclass(frozen=True)
class EnterprisePortfolioSnapshot:
    strategy_summaries: tuple[StrategyPortfolioSummary, ...]
    positions: tuple[EnterprisePosition, ...]
    generated_at: datetime = field(default_factory=utc_now)
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if self.generated_at.tzinfo is None:
            raise PlatformValidationError("generated_at must be timezone-aware")
        for summary in self.strategy_summaries:
            summary.validate()
        for position in self.positions:
            position.validate()
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterprisePortfolio:
    """Own all paper positions while preserving strategy-level capital boundaries."""

    _READY_STATUSES = frozenset({StrategyStatus.PAPER_VALIDATION, StrategyStatus.OPERATIONAL})

    def __init__(self, registry: StrategyRegistry, capital_manager: EnterpriseCapitalManager) -> None:
        self._registry = registry
        self._capital_manager = capital_manager
        self._positions: list[EnterprisePosition] = []
        self._events: list[PortfolioEvent] = []
        self._processed_request_ids: set[UUID] = set()

    def positions(self, strategy_id: str | None = None) -> tuple[EnterprisePosition, ...]:
        if strategy_id is None:
            return tuple(self._positions)
        self._registry.get(strategy_id)
        return tuple(item for item in self._positions if item.strategy_id == strategy_id)

    def events(self, strategy_id: str | None = None) -> tuple[PortfolioEvent, ...]:
        if strategy_id is None:
            return tuple(self._events)
        self._registry.get(strategy_id)
        return tuple(item for item in self._events if item.strategy_id == strategy_id)

    def open_position(
        self,
        request: StrategyExecutionRequest,
        *,
        asset_symbol: str,
        asset_type: str,
        quantity: float,
        entry_price: float,
        reason: str,
        opened_at: datetime | None = None,
    ) -> EnterprisePosition:
        request.validate()
        strategy_id = request.strategy_id
        self._require_ready(strategy_id)
        if request.request_id in self._processed_request_ids:
            raise PlatformValidationError("execution request already created a portfolio position")
        if request.effective_action.upper() not in {"BUY", "ACCUMULATE", "ADD"}:
            raise PlatformValidationError("only governed entry actions may open a position")
        resolved_quantity = float(quantity)
        resolved_price = float(entry_price)
        cost = round(resolved_quantity * resolved_price, 8)
        if cost > request.requested_capital + 1e-6:
            raise PlatformValidationError("position cost exceeds execution request capital")
        if cost > self.remaining_capital(strategy_id) + 1e-6:
            raise PlatformValidationError("position cost exceeds remaining isolated strategy capital")
        if not reason.strip():
            raise PlatformValidationError("position opening reason is required")
        position = EnterprisePosition(
            position_id=uuid4(),
            strategy_id=strategy_id,
            asset_symbol=asset_symbol.upper(),
            asset_type=asset_type.upper(),
            decision_id=request.decision_id,
            decision_public_id=request.decision_public_id,
            execution_request_id=request.request_id,
            quantity=resolved_quantity,
            entry_price=resolved_price,
            current_price=resolved_price,
            allocated_cost=cost,
            status=EnterprisePositionStatus.OPEN,
            opened_at=opened_at or utc_now(),
        )
        position.validate()
        event = PortfolioEvent(
            uuid4(), PortfolioEventType.OPENED, position.position_id, strategy_id, None, resolved_price, reason,
            opened_at or position.opened_at,
        )
        event.validate()
        self._positions.append(position)
        self._events.append(event)
        self._processed_request_ids.add(request.request_id)
        return position

    def mark_position(
        self,
        position_id: UUID,
        *,
        strategy_id: str,
        current_price: float,
        reason: str,
        marked_at: datetime | None = None,
    ) -> EnterprisePosition:
        index, position = self._locate(position_id)
        self._require_owner(position, strategy_id)
        if position.status is not EnterprisePositionStatus.OPEN:
            raise PlatformValidationError("only open positions may be marked")
        updated = replace(position, current_price=float(current_price))
        updated.validate()
        event = PortfolioEvent(
            uuid4(), PortfolioEventType.MARKED, position_id, strategy_id, position.current_price,
            updated.current_price, reason, marked_at or utc_now(),
        )
        event.validate()
        self._positions[index] = updated
        self._events.append(event)
        return updated

    def close_position(
        self,
        position_id: UUID,
        *,
        strategy_id: str,
        exit_price: float,
        reason: str,
        closed_at: datetime | None = None,
    ) -> EnterprisePosition:
        index, position = self._locate(position_id)
        self._require_owner(position, strategy_id)
        if position.status is not EnterprisePositionStatus.OPEN:
            raise PlatformValidationError("position is already closed")
        resolved_exit = float(exit_price)
        realized = round(position.quantity * resolved_exit - position.allocated_cost, 8)
        updated = replace(
            position,
            current_price=resolved_exit,
            status=EnterprisePositionStatus.CLOSED,
            closed_at=closed_at or utc_now(),
            realized_profit_loss=realized,
        )
        updated.validate()
        event = PortfolioEvent(
            uuid4(), PortfolioEventType.CLOSED, position_id, strategy_id, position.current_price,
            resolved_exit, reason, closed_at or updated.closed_at,
        )
        event.validate()
        self._positions[index] = updated
        self._events.append(event)
        return updated

    def remaining_capital(self, strategy_id: str) -> float:
        allocation = self._capital_manager.strategy_balance(strategy_id)
        open_cost = sum(
            item.allocated_cost
            for item in self._positions
            if item.strategy_id == strategy_id and item.status is EnterprisePositionStatus.OPEN
        )
        return round(allocation - open_cost, 8)

    def strategy_summary(self, strategy_id: str) -> StrategyPortfolioSummary:
        self._registry.get(strategy_id)
        positions = self.positions(strategy_id)
        open_positions = tuple(item for item in positions if item.status is EnterprisePositionStatus.OPEN)
        closed_positions = tuple(item for item in positions if item.status is EnterprisePositionStatus.CLOSED)
        allocation = self._capital_manager.strategy_balance(strategy_id)
        open_cost = round(sum(item.allocated_cost for item in open_positions), 8)
        summary = StrategyPortfolioSummary(
            strategy_id=strategy_id,
            allocated_capital=allocation,
            open_cost_basis=open_cost,
            remaining_allocated_capital=round(allocation - open_cost, 8),
            current_value=round(sum(item.current_value for item in open_positions), 8),
            unrealized_profit_loss=round(sum(item.unrealized_profit_loss for item in open_positions), 8),
            realized_profit_loss=round(sum(item.realized_profit_loss for item in closed_positions), 8),
            open_position_count=len(open_positions),
            closed_position_count=len(closed_positions),
        )
        summary.validate()
        return summary

    def snapshot(self) -> EnterprisePortfolioSnapshot:
        summaries = tuple(self.strategy_summary(item.strategy_id) for item in self._registry.list_definitions())
        snapshot = EnterprisePortfolioSnapshot(summaries, self.positions())
        snapshot.validate()
        return snapshot

    @staticmethod
    def render_json(snapshot: EnterprisePortfolioSnapshot) -> str:
        snapshot.validate()
        return JsonSerializer.dumps(snapshot)

    @staticmethod
    def render_markdown(snapshot: EnterprisePortfolioSnapshot) -> str:
        snapshot.validate()
        lines = ["# Enterprise Paper Portfolio", ""]
        for summary in snapshot.strategy_summaries:
            lines.extend(
                [
                    f"## {summary.strategy_id}",
                    "",
                    f"- Allocated Capital: ${summary.allocated_capital:,.2f}",
                    f"- Open Cost Basis: ${summary.open_cost_basis:,.2f}",
                    f"- Remaining Capital: ${summary.remaining_allocated_capital:,.2f}",
                    f"- Current Value: ${summary.current_value:,.2f}",
                    f"- Unrealized P/L: ${summary.unrealized_profit_loss:,.2f}",
                    f"- Realized P/L: ${summary.realized_profit_loss:,.2f}",
                    f"- Open Positions: {summary.open_position_count}",
                    f"- Closed Positions: {summary.closed_position_count}",
                    "",
                ]
            )
        lines.extend(
            [
                "## Portfolio Boundary",
                "",
                "This enterprise portfolio owns paper records only. It does not move cash, place orders, or call broker APIs.",
                "",
            ]
        )
        return "\n".join(lines)

    def _require_ready(self, strategy_id: str) -> None:
        self._registry.get(strategy_id)
        status = self._registry.status(strategy_id)
        if status not in self._READY_STATUSES:
            raise PlatformValidationError(f"strategy is not ready for portfolio activity: {strategy_id} ({status.value})")

    def _locate(self, position_id: UUID) -> tuple[int, EnterprisePosition]:
        for index, position in enumerate(self._positions):
            if position.position_id == position_id:
                return index, position
        raise PlatformValidationError("enterprise position is not registered")

    @staticmethod
    def _require_owner(position: EnterprisePosition, strategy_id: str) -> None:
        if position.strategy_id != strategy_id:
            raise PlatformValidationError("strategy cannot modify another strategy's position")
