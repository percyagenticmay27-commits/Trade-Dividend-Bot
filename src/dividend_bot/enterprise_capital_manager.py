"""Enterprise cash assignment for multiple isolated paper-only strategies."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping

from .platform_foundation import PlatformValidationError, utc_now
from .strategy_framework import StrategyDefinition, StrategyRegistry, StrategyStatus

MODULE_NAME = "enterprise_capital_manager"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Investor-approved capital assignment across registered paper-only strategies."


class CapitalEventType(str, Enum):
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    ASSIGNMENT = "ASSIGNMENT"
    TRANSFER = "TRANSFER"
    RELEASE = "RELEASE"


@dataclass(frozen=True)
class StrategyAvailability:
    strategy_id: str
    name: str
    version: str
    status: StrategyStatus
    ready_for_allocation: bool
    current_allocation: float
    minimum_capital: float = 0.0


@dataclass(frozen=True)
class CapitalRecommendation:
    strategy_allocations: Mapping[str, float]
    rationale: str
    created_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        if self.created_at.tzinfo is None:
            raise PlatformValidationError("recommendation timestamp must be timezone-aware")
        if not self.rationale.strip():
            raise PlatformValidationError("recommendation rationale must not be empty")
        if not self.strategy_allocations:
            raise PlatformValidationError("recommendation must include at least one strategy")
        if any(amount < 0 for amount in self.strategy_allocations.values()):
            raise PlatformValidationError("recommended allocations must not be negative")


@dataclass(frozen=True)
class InvestorCapitalInstruction:
    investor_id: str
    strategy_allocations: Mapping[str, float]
    reason: str
    approved_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        if not self.investor_id.strip() or not self.reason.strip():
            raise PlatformValidationError("investor_id and reason must not be empty")
        if self.approved_at.tzinfo is None:
            raise PlatformValidationError("approved_at must be timezone-aware")
        if not self.strategy_allocations:
            raise PlatformValidationError("instruction must include at least one strategy")
        if any(amount < 0 for amount in self.strategy_allocations.values()):
            raise PlatformValidationError("approved allocations must not be negative")


@dataclass(frozen=True)
class CapitalLedgerEntry:
    event_type: CapitalEventType
    amount: float
    strategy_id: str | None
    counterparty_strategy_id: str | None
    reason: str
    investor_id: str | None
    occurred_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        if self.amount <= 0:
            raise PlatformValidationError("capital ledger amount must be greater than zero")
        if not self.reason.strip():
            raise PlatformValidationError("capital ledger reason must not be empty")
        if self.occurred_at.tzinfo is None:
            raise PlatformValidationError("capital ledger timestamp must be timezone-aware")
        if self.event_type is CapitalEventType.TRANSFER:
            if not self.strategy_id or not self.counterparty_strategy_id:
                raise PlatformValidationError("transfers require source and destination strategies")
            if self.strategy_id == self.counterparty_strategy_id:
                raise PlatformValidationError("transfer strategies must differ")


class EnterpriseCapitalManager:
    """Maintain unassigned cash and append-only strategy capital assignments."""

    _READY_STATUSES = frozenset({StrategyStatus.PAPER_VALIDATION, StrategyStatus.OPERATIONAL})

    def __init__(self, strategy_registry: StrategyRegistry) -> None:
        self._registry = strategy_registry
        self._unassigned_cash = 0.0
        self._allocations: dict[str, float] = {}
        self._ledger: list[CapitalLedgerEntry] = []

    @property
    def unassigned_cash(self) -> float:
        return self._unassigned_cash

    def strategy_balance(self, strategy_id: str) -> float:
        self._registry.get(strategy_id)
        return self._allocations.get(strategy_id, 0.0)

    def ledger(self) -> tuple[CapitalLedgerEntry, ...]:
        return tuple(self._ledger)

    def record_deposit(self, amount: float, *, reason: str = "Investor cash deposit") -> CapitalLedgerEntry:
        entry = CapitalLedgerEntry(CapitalEventType.DEPOSIT, float(amount), None, None, reason, None)
        entry.validate()
        self._unassigned_cash += entry.amount
        self._ledger.append(entry)
        return entry

    def discover_available_strategies(
        self,
        minimum_capital_by_strategy: Mapping[str, float] | None = None,
    ) -> tuple[StrategyAvailability, ...]:
        minimums = minimum_capital_by_strategy or {}
        rows: list[StrategyAvailability] = []
        for definition in self._registry.list_definitions():
            status = self._registry.status(definition.strategy_id)
            minimum = float(minimums.get(definition.strategy_id, 0.0))
            if minimum < 0:
                raise PlatformValidationError("minimum strategy capital must not be negative")
            rows.append(
                StrategyAvailability(
                    strategy_id=definition.strategy_id,
                    name=definition.name,
                    version=definition.version,
                    status=status,
                    ready_for_allocation=status in self._READY_STATUSES,
                    current_allocation=self._allocations.get(definition.strategy_id, 0.0),
                    minimum_capital=minimum,
                )
            )
        return tuple(rows)

    def apply_investor_instruction(self, instruction: InvestorCapitalInstruction) -> tuple[CapitalLedgerEntry, ...]:
        instruction.validate()
        requested_total = sum(float(value) for value in instruction.strategy_allocations.values())
        if requested_total > self._unassigned_cash:
            raise PlatformValidationError("approved allocations exceed unassigned cash")

        for strategy_id, amount in instruction.strategy_allocations.items():
            definition = self._registry.get(strategy_id)
            self._require_ready(definition)
            if amount == 0:
                continue

        created: list[CapitalLedgerEntry] = []
        for strategy_id, amount in instruction.strategy_allocations.items():
            resolved_amount = float(amount)
            if resolved_amount == 0:
                continue
            entry = CapitalLedgerEntry(
                CapitalEventType.ASSIGNMENT,
                resolved_amount,
                strategy_id,
                None,
                instruction.reason,
                instruction.investor_id,
                instruction.approved_at,
            )
            entry.validate()
            self._allocations[strategy_id] = self._allocations.get(strategy_id, 0.0) + resolved_amount
            self._unassigned_cash -= resolved_amount
            self._ledger.append(entry)
            created.append(entry)
        return tuple(created)

    def transfer(
        self,
        *,
        investor_id: str,
        source_strategy_id: str,
        destination_strategy_id: str,
        amount: float,
        reason: str,
    ) -> CapitalLedgerEntry:
        source = self._registry.get(source_strategy_id)
        destination = self._registry.get(destination_strategy_id)
        self._require_ready(source)
        self._require_ready(destination)
        resolved_amount = float(amount)
        if resolved_amount > self.strategy_balance(source_strategy_id):
            raise PlatformValidationError("transfer exceeds source strategy balance")
        entry = CapitalLedgerEntry(
            CapitalEventType.TRANSFER,
            resolved_amount,
            source_strategy_id,
            destination_strategy_id,
            reason,
            investor_id,
        )
        entry.validate()
        self._allocations[source_strategy_id] -= resolved_amount
        self._allocations[destination_strategy_id] = self._allocations.get(destination_strategy_id, 0.0) + resolved_amount
        self._ledger.append(entry)
        return entry

    def release_to_unassigned_cash(
        self,
        *,
        investor_id: str,
        strategy_id: str,
        amount: float,
        reason: str,
    ) -> CapitalLedgerEntry:
        self._registry.get(strategy_id)
        resolved_amount = float(amount)
        if resolved_amount > self.strategy_balance(strategy_id):
            raise PlatformValidationError("release exceeds strategy balance")
        entry = CapitalLedgerEntry(
            CapitalEventType.RELEASE,
            resolved_amount,
            strategy_id,
            None,
            reason,
            investor_id,
        )
        entry.validate()
        self._allocations[strategy_id] -= resolved_amount
        self._unassigned_cash += resolved_amount
        self._ledger.append(entry)
        return entry

    def record_withdrawal(self, amount: float, *, investor_id: str, reason: str) -> CapitalLedgerEntry:
        resolved_amount = float(amount)
        if resolved_amount > self._unassigned_cash:
            raise PlatformValidationError("withdrawal exceeds unassigned cash")
        entry = CapitalLedgerEntry(
            CapitalEventType.WITHDRAWAL,
            resolved_amount,
            None,
            None,
            reason,
            investor_id,
        )
        entry.validate()
        self._unassigned_cash -= resolved_amount
        self._ledger.append(entry)
        return entry

    def _require_ready(self, definition: StrategyDefinition) -> None:
        status = self._registry.status(definition.strategy_id)
        if status not in self._READY_STATUSES:
            raise PlatformValidationError(
                f"strategy is not ready for capital allocation: {definition.strategy_id} ({status.value})"
            )
