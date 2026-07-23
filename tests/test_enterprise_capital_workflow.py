from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import pytest

from src.dividend_bot.enterprise_capital_manager import (
    CapitalRecommendation,
    EnterpriseCapitalManager,
)
from src.dividend_bot.enterprise_capital_workflow import (
    CapitalApprovalStatus,
    EnterpriseCapitalApprovalWorkflow,
)
from src.dividend_bot.enterprise_cio_capital_report import EnterpriseCIOCapitalReporter
from src.dividend_bot.platform_foundation import PlatformValidationError
from src.dividend_bot.strategy_framework import (
    StrategyConfiguration,
    StrategyDefinition,
    StrategyRegistry,
    StrategyStatus,
)


def _registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    for strategy_id in ("DIVIDEND", "SWING"):
        registry.register(
            StrategyDefinition(
                strategy_id=strategy_id,
                name=f"{strategy_id.title()} Strategy",
                version="1.0.0",
                supported_asset_types=("EQUITY",),
                required_intelligence=("risk",),
                supported_report_types=("WEEKLY",),
                supported_audit_types=("WEEKLY_AUDIT",),
                module_entry_point=f"src.dividend_bot.{strategy_id.lower()}",
            )
        )
        registry.configure(StrategyConfiguration(strategy_id, "1.0.0", {}))
        registry.transition(strategy_id, StrategyStatus.CONFIGURED, "Configured")
        registry.transition(strategy_id, StrategyStatus.PAPER_VALIDATION, "Ready for paper capital")
    return registry


def _manager_and_report():
    manager = EnterpriseCapitalManager(_registry())
    manager.record_deposit(100_000.0)
    recommendation = CapitalRecommendation(
        strategy_allocations={"DIVIDEND": 60_000.0, "SWING": 40_000.0},
        rationale="Balance income and growth opportunities.",
    )
    report = EnterpriseCIOCapitalReporter(manager).build_report(recommendation=recommendation)
    return manager, report


def test_approved_instruction_applies_strategy_allocations() -> None:
    manager, report = _manager_and_report()
    result = EnterpriseCapitalApprovalWorkflow(manager).approve_and_apply(
        report,
        investor_id="INVESTOR-001",
        strategy_allocations={"DIVIDEND": 70_000.0, "SWING": 30_000.0},
        reason="Investor prefers a larger income allocation.",
    )
    assert result.approval.status is CapitalApprovalStatus.APPLIED
    assert manager.strategy_balance("DIVIDEND") == 70_000.0
    assert manager.strategy_balance("SWING") == 30_000.0
    assert manager.unassigned_cash == 0.0


def test_cio_recommendation_and_investor_choice_remain_separate() -> None:
    manager, report = _manager_and_report()
    result = EnterpriseCapitalApprovalWorkflow(manager).approve_and_apply(
        report,
        investor_id="INVESTOR-001",
        strategy_allocations={"DIVIDEND": 80_000.0, "SWING": 20_000.0},
        reason="Investor override of advisory mix.",
    )
    assert dict(result.approval.cio_recommendation) == {"DIVIDEND": 60_000.0, "SWING": 40_000.0}
    assert dict(result.approval.investor_allocations) == {"DIVIDEND": 80_000.0, "SWING": 20_000.0}


def test_workflow_history_is_append_only_snapshot() -> None:
    manager, report = _manager_and_report()
    workflow = EnterpriseCapitalApprovalWorkflow(manager)
    workflow.approve_and_apply(
        report,
        investor_id="INVESTOR-001",
        strategy_allocations={"DIVIDEND": 50_000.0},
        reason="Initial assignment.",
    )
    snapshot = workflow.history()
    assert len(snapshot) == 1
    assert isinstance(snapshot, tuple)


def test_stale_report_is_rejected_after_cash_change() -> None:
    manager, report = _manager_and_report()
    manager.record_deposit(1_000.0)
    with pytest.raises(PlatformValidationError, match="stale"):
        EnterpriseCapitalApprovalWorkflow(manager).approve_and_apply(
            report,
            investor_id="INVESTOR-001",
            strategy_allocations={"DIVIDEND": 50_000.0},
            reason="Should fail.",
        )


def test_unreported_strategy_is_rejected() -> None:
    manager, report = _manager_and_report()
    with pytest.raises(PlatformValidationError, match="unreported"):
        EnterpriseCapitalApprovalWorkflow(manager).approve_and_apply(
            report,
            investor_id="INVESTOR-001",
            strategy_allocations={"OPTIONS": 10_000.0},
            reason="Should fail.",
        )


def test_unready_strategy_is_rejected() -> None:
    manager, report = _manager_and_report()
    unready_rows = tuple(
        replace(row, ready_for_allocation=False) if row.strategy_id == "SWING" else row
        for row in report.strategies
    )
    unready_report = replace(report, strategies=unready_rows)
    with pytest.raises(PlatformValidationError, match="unready"):
        EnterpriseCapitalApprovalWorkflow(manager).approve_and_apply(
            unready_report,
            investor_id="INVESTOR-001",
            strategy_allocations={"SWING": 10_000.0},
            reason="Should fail.",
        )


def test_approval_exceeding_report_cash_is_rejected() -> None:
    manager, report = _manager_and_report()
    with pytest.raises(PlatformValidationError, match="exceeds cash"):
        EnterpriseCapitalApprovalWorkflow(manager).approve_and_apply(
            report,
            investor_id="INVESTOR-001",
            strategy_allocations={"DIVIDEND": 100_001.0},
            reason="Should fail.",
        )


def test_report_must_require_investor_action() -> None:
    manager, report = _manager_and_report()
    with pytest.raises(PlatformValidationError, match="require investor action"):
        EnterpriseCapitalApprovalWorkflow(manager).approve_and_apply(
            replace(report, investor_action_required=False),
            investor_id="INVESTOR-001",
            strategy_allocations={"DIVIDEND": 50_000.0},
            reason="Should fail.",
        )


def test_approval_mappings_are_immutable() -> None:
    manager, report = _manager_and_report()
    result = EnterpriseCapitalApprovalWorkflow(manager).approve_and_apply(
        report,
        investor_id="INVESTOR-001",
        strategy_allocations={"DIVIDEND": 50_000.0},
        reason="Preserve audit record.",
    )
    assert isinstance(result.approval.investor_allocations, MappingProxyType)
    with pytest.raises(TypeError):
        result.approval.investor_allocations["DIVIDEND"] = 1.0


def test_no_broker_or_order_interface_exists() -> None:
    manager, report = _manager_and_report()
    result = EnterpriseCapitalApprovalWorkflow(manager).approve_and_apply(
        report,
        investor_id="INVESTOR-001",
        strategy_allocations={"DIVIDEND": 50_000.0},
        reason="Paper-only assignment.",
    )
    assert not hasattr(result, "order")
    assert not hasattr(result, "broker_request")
