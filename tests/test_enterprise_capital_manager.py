from __future__ import annotations

import pytest

from src.dividend_bot.enterprise_capital_manager import (
    EnterpriseCapitalManager,
    InvestorCapitalInstruction,
)
from src.dividend_bot.platform_foundation import PlatformValidationError
from src.dividend_bot.strategy_framework import (
    StrategyConfiguration,
    StrategyDefinition,
    StrategyRegistry,
    StrategyStatus,
)


def _definition(strategy_id: str) -> StrategyDefinition:
    return StrategyDefinition(
        strategy_id=strategy_id,
        name=f"{strategy_id.title()} Strategy",
        version="1.0.0",
        supported_asset_types=("EQUITY",),
        required_intelligence=("risk",),
        supported_report_types=("WEEKLY",),
        supported_audit_types=("WEEKLY_AUDIT",),
        module_entry_point=f"src.dividend_bot.{strategy_id.lower()}:Adapter",
    )


def _ready_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    for strategy_id in ("DIVIDEND", "SWING", "OPTIONS"):
        registry.register(_definition(strategy_id))
        registry.configure(StrategyConfiguration(strategy_id, "1.0.0", {}))
        registry.transition(strategy_id, StrategyStatus.CONFIGURED, "configured")
        registry.transition(strategy_id, StrategyStatus.PAPER_VALIDATION, "ready for paper capital")
    return registry


def test_deposit_remains_unassigned_until_investor_instruction() -> None:
    manager = EnterpriseCapitalManager(_ready_registry())
    manager.record_deposit(100000)
    assert manager.unassigned_cash == 100000
    assert manager.strategy_balance("DIVIDEND") == 0


def test_available_strategy_report_uses_registry_status() -> None:
    manager = EnterpriseCapitalManager(_ready_registry())
    rows = manager.discover_available_strategies({"DIVIDEND": 25000})
    dividend = next(row for row in rows if row.strategy_id == "DIVIDEND")
    assert dividend.ready_for_allocation is True
    assert dividend.minimum_capital == 25000


def test_investor_instruction_splits_cash_across_strategies() -> None:
    manager = EnterpriseCapitalManager(_ready_registry())
    manager.record_deposit(100000)
    entries = manager.apply_investor_instruction(
        InvestorCapitalInstruction(
            investor_id="INVESTOR-1",
            strategy_allocations={"DIVIDEND": 40000, "SWING": 35000, "OPTIONS": 25000},
            reason="Initial strategy allocation",
        )
    )
    assert len(entries) == 3
    assert manager.unassigned_cash == 0
    assert manager.strategy_balance("DIVIDEND") == 40000
    assert manager.strategy_balance("SWING") == 35000
    assert manager.strategy_balance("OPTIONS") == 25000


def test_allocation_rejects_unready_strategy() -> None:
    registry = StrategyRegistry()
    registry.register(_definition("FUTURES"))
    manager = EnterpriseCapitalManager(registry)
    manager.record_deposit(10000)
    with pytest.raises(PlatformValidationError):
        manager.apply_investor_instruction(
            InvestorCapitalInstruction("INVESTOR-1", {"FUTURES": 10000}, "Allocate to Futures")
        )


def test_allocation_cannot_exceed_unassigned_cash() -> None:
    manager = EnterpriseCapitalManager(_ready_registry())
    manager.record_deposit(5000)
    with pytest.raises(PlatformValidationError):
        manager.apply_investor_instruction(
            InvestorCapitalInstruction("INVESTOR-1", {"DIVIDEND": 6000}, "Too much")
        )


def test_transfer_preserves_total_assigned_capital() -> None:
    manager = EnterpriseCapitalManager(_ready_registry())
    manager.record_deposit(50000)
    manager.apply_investor_instruction(
        InvestorCapitalInstruction("INVESTOR-1", {"DIVIDEND": 30000, "SWING": 20000}, "Initial")
    )
    manager.transfer(
        investor_id="INVESTOR-1",
        source_strategy_id="DIVIDEND",
        destination_strategy_id="SWING",
        amount=5000,
        reason="Investor rebalance",
    )
    assert manager.strategy_balance("DIVIDEND") == 25000
    assert manager.strategy_balance("SWING") == 25000


def test_release_returns_cash_to_enterprise_pool() -> None:
    manager = EnterpriseCapitalManager(_ready_registry())
    manager.record_deposit(20000)
    manager.apply_investor_instruction(
        InvestorCapitalInstruction("INVESTOR-1", {"DIVIDEND": 20000}, "Initial")
    )
    manager.release_to_unassigned_cash(
        investor_id="INVESTOR-1",
        strategy_id="DIVIDEND",
        amount=5000,
        reason="Hold for reassignment",
    )
    assert manager.strategy_balance("DIVIDEND") == 15000
    assert manager.unassigned_cash == 5000


def test_withdrawal_requires_unassigned_cash() -> None:
    manager = EnterpriseCapitalManager(_ready_registry())
    manager.record_deposit(10000)
    manager.apply_investor_instruction(
        InvestorCapitalInstruction("INVESTOR-1", {"DIVIDEND": 10000}, "Initial")
    )
    with pytest.raises(PlatformValidationError):
        manager.record_withdrawal(1000, investor_id="INVESTOR-1", reason="Withdrawal")


def test_ledger_is_append_only_tuple_snapshot() -> None:
    manager = EnterpriseCapitalManager(_ready_registry())
    manager.record_deposit(1000)
    first = manager.ledger()
    manager.record_deposit(500)
    assert len(first) == 1
    assert len(manager.ledger()) == 2


def test_no_broker_or_order_interface_exists() -> None:
    manager = EnterpriseCapitalManager(_ready_registry())
    assert not hasattr(manager, "place_order")
    assert not hasattr(manager, "broker_request")
