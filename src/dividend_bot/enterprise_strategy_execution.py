"""Governed routing of approved enterprise decisions to isolated paper strategies.

This module creates immutable paper-execution requests and strategy responses. It does
not create investment decisions, reserve or move capital, place orders, or call brokers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from .enterprise_capital_manager import EnterpriseCapitalManager
from .enterprise_decision_governance import DecisionGovernanceSnapshot, InvestorDecision
from .platform_entities import DecisionState
from .platform_foundation import JsonSerializer, PlatformValidationError, utc_now
from .strategy_framework import StrategyRegistry, StrategyStatus

MODULE_NAME = "enterprise_strategy_execution"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Route governed enterprise decisions to isolated paper-only strategy adapters."


class ExecutionRequestStatus(str, Enum):
    ROUTED = "ROUTED"
    RESPONDED = "RESPONDED"


class StrategyResponseStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    DEFERRED = "DEFERRED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class StrategyCapabilityView:
    strategy_id: str
    name: str
    version: str
    status: StrategyStatus
    module_entry_point: str
    supported_asset_types: tuple[str, ...]
    required_intelligence: tuple[str, ...]
    allocated_capital: float
    ready_for_execution: bool

    def validate(self) -> None:
        if not self.strategy_id or self.strategy_id != self.strategy_id.upper():
            raise PlatformValidationError("strategy_id must be non-empty uppercase text")
        if not self.name.strip() or not self.version.strip() or not self.module_entry_point.strip():
            raise PlatformValidationError("strategy capability display fields are required")
        if self.allocated_capital < 0:
            raise PlatformValidationError("allocated_capital must not be negative")


@dataclass(frozen=True)
class StrategyExecutionRequest:
    request_id: UUID
    decision_id: UUID
    decision_public_id: str
    strategy_id: str
    effective_action: str
    requested_capital: float
    available_strategy_capital: float
    rationale: str
    routed_at: datetime = field(default_factory=utc_now)
    status: ExecutionRequestStatus = ExecutionRequestStatus.ROUTED
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if not self.strategy_id or self.strategy_id != self.strategy_id.upper():
            raise PlatformValidationError("strategy_id must be non-empty uppercase text")
        if not self.decision_public_id.strip() or not self.effective_action.strip() or not self.rationale.strip():
            raise PlatformValidationError("execution request decision, action, and rationale are required")
        if self.requested_capital <= 0:
            raise PlatformValidationError("requested_capital must be greater than zero")
        if self.available_strategy_capital <= 0:
            raise PlatformValidationError("available_strategy_capital must be greater than zero")
        if self.requested_capital > self.available_strategy_capital:
            raise PlatformValidationError("requested_capital exceeds isolated strategy allocation")
        if self.routed_at.tzinfo is None:
            raise PlatformValidationError("routed_at must be timezone-aware")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


@dataclass(frozen=True)
class StrategyExecutionResponse:
    response_id: UUID
    request_id: UUID
    strategy_id: str
    status: StrategyResponseStatus
    explanation: str
    responded_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        if not self.strategy_id or self.strategy_id != self.strategy_id.upper():
            raise PlatformValidationError("strategy_id must be non-empty uppercase text")
        if not self.explanation.strip():
            raise PlatformValidationError("strategy response explanation is required")
        if self.responded_at.tzinfo is None:
            raise PlatformValidationError("responded_at must be timezone-aware")


@dataclass(frozen=True)
class StrategyExecutionSnapshot:
    request: StrategyExecutionRequest
    response: StrategyExecutionResponse | None

    def validate(self) -> None:
        self.request.validate()
        if self.response is not None:
            self.response.validate()
            if self.response.request_id != self.request.request_id:
                raise PlatformValidationError("strategy response request_id must match request")
            if self.response.strategy_id != self.request.strategy_id:
                raise PlatformValidationError("strategy response must preserve strategy isolation")


class EnterpriseStrategyExecutionCoordinator:
    """Route only governed investor-approved decisions to funded, ready strategies."""

    _READY_STATUSES = frozenset({StrategyStatus.PAPER_VALIDATION, StrategyStatus.OPERATIONAL})
    _APPROVED_STATES = frozenset({DecisionState.IMPLEMENTED, DecisionState.OVERRIDDEN_BY_INVESTOR})

    def __init__(self, registry: StrategyRegistry, capital_manager: EnterpriseCapitalManager) -> None:
        self._registry = registry
        self._capital_manager = capital_manager
        self._requests: list[StrategyExecutionRequest] = []
        self._responses: list[StrategyExecutionResponse] = []

    def discover_capabilities(self) -> tuple[StrategyCapabilityView, ...]:
        rows: list[StrategyCapabilityView] = []
        for definition in self._registry.list_definitions():
            status = self._registry.status(definition.strategy_id)
            allocation = self._capital_manager.strategy_balance(definition.strategy_id)
            row = StrategyCapabilityView(
                strategy_id=definition.strategy_id,
                name=definition.name,
                version=definition.version,
                status=status,
                module_entry_point=definition.module_entry_point,
                supported_asset_types=definition.supported_asset_types,
                required_intelligence=definition.required_intelligence,
                allocated_capital=allocation,
                ready_for_execution=status in self._READY_STATUSES and allocation > 0,
            )
            row.validate()
            rows.append(row)
        return tuple(rows)

    def route(
        self,
        governance: DecisionGovernanceSnapshot,
        *,
        strategy_id: str,
        requested_capital: float,
        rationale: str,
        routed_at: datetime | None = None,
    ) -> StrategyExecutionRequest:
        governance.validate()
        definition = self._registry.get(strategy_id)
        status = self._registry.status(strategy_id)
        if status not in self._READY_STATUSES:
            raise PlatformValidationError(f"strategy is not ready for paper execution: {strategy_id} ({status.value})")
        if governance.current_state not in self._APPROVED_STATES:
            raise PlatformValidationError("only investor-approved governed decisions may be routed")
        if not governance.investor_decisions:
            raise PlatformValidationError("governed decision has no investor approval record")
        last_investor = governance.investor_decisions[-1]
        if last_investor.decision not in {InvestorDecision.APPROVE, InvestorDecision.OVERRIDE}:
            raise PlatformValidationError("investor rejected the enterprise decision")
        advisory_strategy_ids = {item.strategy_id for item in governance.decision.strategy_advisories}
        if strategy_id not in advisory_strategy_ids:
            raise PlatformValidationError("decision does not contain an advisory for the target strategy")
        allocation = self._capital_manager.strategy_balance(strategy_id)
        if allocation <= 0:
            raise PlatformValidationError("target strategy has no assigned enterprise capital")
        request = StrategyExecutionRequest(
            request_id=uuid4(),
            decision_id=governance.decision.identity.internal_id,
            decision_public_id=governance.decision.identity.public_id,
            strategy_id=definition.strategy_id,
            effective_action=governance.effective_action.value,
            requested_capital=float(requested_capital),
            available_strategy_capital=allocation,
            rationale=rationale,
            routed_at=routed_at or utc_now(),
        )
        request.validate()
        self._requests.append(request)
        return request

    def respond(
        self,
        request_id: UUID,
        *,
        strategy_id: str,
        status: StrategyResponseStatus,
        explanation: str,
        responded_at: datetime | None = None,
    ) -> StrategyExecutionResponse:
        request = self._get_request(request_id)
        if request.strategy_id != strategy_id:
            raise PlatformValidationError("strategy cannot respond to another strategy's execution request")
        if any(item.request_id == request_id for item in self._responses):
            raise PlatformValidationError("execution request already has a strategy response")
        response = StrategyExecutionResponse(
            response_id=uuid4(),
            request_id=request_id,
            strategy_id=strategy_id,
            status=status,
            explanation=explanation,
            responded_at=responded_at or utc_now(),
        )
        response.validate()
        self._responses.append(response)
        return response

    def requests(self, strategy_id: str | None = None) -> tuple[StrategyExecutionRequest, ...]:
        if strategy_id is None:
            return tuple(self._requests)
        self._registry.get(strategy_id)
        return tuple(item for item in self._requests if item.strategy_id == strategy_id)

    def responses(self, strategy_id: str | None = None) -> tuple[StrategyExecutionResponse, ...]:
        if strategy_id is None:
            return tuple(self._responses)
        self._registry.get(strategy_id)
        return tuple(item for item in self._responses if item.strategy_id == strategy_id)

    def snapshot(self, request_id: UUID) -> StrategyExecutionSnapshot:
        request = self._get_request(request_id)
        response = next((item for item in self._responses if item.request_id == request_id), None)
        snapshot = StrategyExecutionSnapshot(request=request, response=response)
        snapshot.validate()
        return snapshot

    @staticmethod
    def render_json(snapshot: StrategyExecutionSnapshot) -> str:
        snapshot.validate()
        return JsonSerializer.dumps(snapshot)

    @staticmethod
    def render_markdown(snapshot: StrategyExecutionSnapshot) -> str:
        snapshot.validate()
        response_status = snapshot.response.status.value if snapshot.response else "PENDING"
        lines = [
            "# Enterprise Strategy Execution",
            "",
            f"- Decision ID: {snapshot.request.decision_public_id}",
            f"- Strategy: {snapshot.request.strategy_id}",
            f"- Effective Action: {snapshot.request.effective_action}",
            f"- Requested Capital: ${snapshot.request.requested_capital:,.2f}",
            f"- Available Strategy Capital: ${snapshot.request.available_strategy_capital:,.2f}",
            f"- Strategy Response: {response_status}",
            f"- Paper Trade Mode: {'YES' if snapshot.request.paper_trade_mode else 'NO'}",
            "",
            "## Execution Boundary",
            "",
            "This record routes a governed paper decision to an isolated strategy. It does not reserve capital, place orders, or call broker APIs.",
            "",
        ]
        return "\n".join(lines)

    def _get_request(self, request_id: UUID) -> StrategyExecutionRequest:
        for item in self._requests:
            if item.request_id == request_id:
                return item
        raise PlatformValidationError("strategy execution request is not registered")
