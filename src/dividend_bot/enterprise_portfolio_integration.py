"""Governed bridge from the enterprise decision ledger to paper portfolio intent.

This module records portfolio integration intent only. It does not reserve capital, open or close
positions, mutate holdings, call brokers, or place orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from .enterprise_decision_ledger_integration import EnterpriseDecisionLedgerIntegrationResult
from .enterprise_strategy_execution import StrategyExecutionRequest
from .platform_foundation import IdentifierFactory, JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_portfolio_integration"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Preserve governed ledger-to-portfolio intent without mutating portfolio state."

_ALLOWED_ACTIONS = frozenset({"BUY", "ACCUMULATE", "ADD", "HOLD", "WATCH", "REVIEW", "SELL", "EXIT"})


@dataclass(frozen=True)
class EnterprisePortfolioIntegrationRecord:
    integration_id: UUID
    sequence: int
    ledger_entry_id: UUID
    workflow_id: str
    correlation_id: str
    decision_internal_id: UUID
    decision_public_id: str
    company_id: UUID
    profile_id: UUID
    strategy_id: str
    execution_request_id: UUID
    effective_action: str
    requested_capital: float
    evidence_ids: tuple[UUID, ...]
    constitution_version: str
    integrated_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if self.sequence < 1:
            raise PlatformValidationError("portfolio integration sequence must be positive")
        if not self.workflow_id.strip() or not self.correlation_id.strip():
            raise PlatformValidationError("workflow_id and correlation_id are required")
        if not self.decision_public_id.strip() or not self.constitution_version.strip():
            raise PlatformValidationError("decision_public_id and constitution_version are required")
        if self.strategy_id != "DIVIDEND":
            raise PlatformValidationError("enterprise portfolio integration currently supports DIVIDEND only")
        if self.effective_action.upper() not in _ALLOWED_ACTIONS:
            raise PlatformValidationError("unsupported portfolio integration action")
        if self.requested_capital <= 0:
            raise PlatformValidationError("requested_capital must be greater than zero")
        if not self.evidence_ids:
            raise PlatformValidationError("portfolio integration requires evidence links")
        if self.integrated_at.tzinfo is None:
            raise PlatformValidationError("integrated_at must be timezone-aware")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


class EnterprisePortfolioIntegrationLedger:
    """Append-only portfolio integration intent ledger."""

    def __init__(self) -> None:
        self._records: list[EnterprisePortfolioIntegrationRecord] = []
        self._request_ids: set[UUID] = set()
        self._ledger_entry_ids: set[UUID] = set()

    def append(self, record: EnterprisePortfolioIntegrationRecord) -> None:
        record.validate()
        if record.sequence != len(self._records) + 1:
            raise PlatformValidationError("portfolio integration sequence must be append-only")
        if record.execution_request_id in self._request_ids:
            raise PlatformValidationError("execution request has already been integrated")
        if record.ledger_entry_id in self._ledger_entry_ids:
            raise PlatformValidationError("ledger decision has already been integrated")
        self._records.append(record)
        self._request_ids.add(record.execution_request_id)
        self._ledger_entry_ids.add(record.ledger_entry_id)

    def all(self) -> tuple[EnterprisePortfolioIntegrationRecord, ...]:
        return tuple(self._records)

    def for_strategy(self, strategy_id: str) -> tuple[EnterprisePortfolioIntegrationRecord, ...]:
        return tuple(item for item in self._records if item.strategy_id == strategy_id)


@dataclass(frozen=True)
class EnterprisePortfolioIntegrationResult:
    record: EnterprisePortfolioIntegrationRecord
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


class EnterprisePortfolioIntegration:
    """Validate and preserve governed portfolio intent without changing holdings."""

    def __init__(self, ledger: EnterprisePortfolioIntegrationLedger | None = None) -> None:
        self._ledger = ledger or EnterprisePortfolioIntegrationLedger()
        self._history: list[EnterprisePortfolioIntegrationResult] = []

    @property
    def ledger(self) -> EnterprisePortfolioIntegrationLedger:
        return self._ledger

    def history(self) -> tuple[EnterprisePortfolioIntegrationResult, ...]:
        return tuple(self._history)

    def integrate(
        self,
        decision_result: EnterpriseDecisionLedgerIntegrationResult,
        request: StrategyExecutionRequest,
        *,
        completed_at: datetime | None = None,
    ) -> EnterprisePortfolioIntegrationResult:
        decision_result.validate()
        request.validate()
        entry = decision_result.entry
        if request.strategy_id != "DIVIDEND":
            raise PlatformValidationError("only DIVIDEND requests may enter the Dividend portfolio integration")
        if request.strategy_id not in entry.strategy_ids:
            raise PlatformValidationError("execution request strategy is not present in the ledger decision")
        if request.decision_id != entry.decision_internal_id:
            raise PlatformValidationError("execution request decision ID must match the ledger decision")
        if request.decision_public_id != entry.decision_public_id:
            raise PlatformValidationError("execution request public decision ID must match the ledger decision")
        if entry.supersedes_decision_id is not None and entry.metadata.get("investor_status") == "PENDING":
            raise PlatformValidationError("superseding decisions require completed investor governance before portfolio integration")
        timestamp = completed_at or utc_now()
        if timestamp.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        record = EnterprisePortfolioIntegrationRecord(
            integration_id=IdentifierFactory.new_internal_id(),
            sequence=len(self._ledger.all()) + 1,
            ledger_entry_id=entry.ledger_entry_id,
            workflow_id=entry.workflow_id,
            correlation_id=entry.correlation_id,
            decision_internal_id=entry.decision_internal_id,
            decision_public_id=entry.decision_public_id,
            company_id=entry.company_id,
            profile_id=entry.profile_id,
            strategy_id=request.strategy_id,
            execution_request_id=request.request_id,
            effective_action=request.effective_action.upper(),
            requested_capital=request.requested_capital,
            evidence_ids=entry.evidence_ids,
            constitution_version=str(entry.metadata["constitution_version"]),
            integrated_at=timestamp,
            metadata=MappingProxyType(
                {
                    "module_version": MODULE_VERSION,
                    "ledger_sequence": entry.sequence,
                    "investor_status": entry.metadata.get("investor_status", "UNKNOWN"),
                    "portfolio_mutated": False,
                    "append_only": True,
                }
            ),
        )
        self._ledger.append(record)
        result = EnterprisePortfolioIntegrationResult(record=record, completed_at=timestamp)
        result.validate()
        self._history.append(result)
        return result

    @staticmethod
    def render_json(result: EnterprisePortfolioIntegrationResult) -> str:
        result.validate()
        return JsonSerializer.dumps(result)

    @staticmethod
    def render_markdown(result: EnterprisePortfolioIntegrationResult) -> str:
        result.validate()
        record = result.record
        return "\n".join(
            [
                "# Enterprise Portfolio Integration",
                "",
                f"- Sequence: {record.sequence}",
                f"- Workflow ID: {record.workflow_id}",
                f"- Correlation ID: {record.correlation_id}",
                f"- Decision ID: {record.decision_public_id}",
                f"- Strategy: {record.strategy_id}",
                f"- Action: {record.effective_action}",
                f"- Requested Capital: ${record.requested_capital:,.2f}",
                f"- Evidence Count: {len(record.evidence_ids)}",
                f"- Portfolio Mutated: {'YES' if record.metadata['portfolio_mutated'] else 'NO'}",
                f"- Paper Trade Mode: {'YES' if record.paper_trade_mode else 'NO'}",
                "",
                "## Safety Boundary",
                "",
                "This integration records governed paper portfolio intent only. It does not reserve capital, mutate holdings, call brokers, or place orders.",
                "",
            ]
        )
