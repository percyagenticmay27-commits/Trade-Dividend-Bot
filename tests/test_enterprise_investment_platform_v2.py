from __future__ import annotations

import pytest

from src.dividend_bot.dividend_strategy_adapter import DIVIDEND_STRATEGY_ID
from src.dividend_bot.enterprise_investment_platform_v2 import EnterpriseInvestmentPlatformV2
from src.dividend_bot.platform_entities import MasterCompanyIntelligenceProfile, new_identity
from src.dividend_bot.platform_foundation import PlatformValidationError
from src.dividend_bot.platform_integration import ServiceDomain
from src.dividend_bot.strategy_framework import StrategyStatus


def _profile() -> MasterCompanyIntelligenceProfile:
    profile = MasterCompanyIntelligenceProfile(
        identity=new_identity("MCIP"),
        company_id=new_identity("COM").internal_id,
        income={"score": 40.0},
        risk={"score": 70.0},
        quality_score=40.0,
    )
    profile.validate()
    return profile


def _funded_platform(amount: float = 10000.0) -> EnterpriseInvestmentPlatformV2:
    platform = EnterpriseInvestmentPlatformV2()
    platform.record_deposit(amount)
    report = platform.build_capital_report()
    platform.approve_capital(
        report,
        investor_id="INVESTOR-001",
        strategy_allocations={DIVIDEND_STRATEGY_ID: amount},
        reason="Fund Dividend paper strategy",
    )
    return platform


def test_bootstrap_registers_dividend_for_paper_validation() -> None:
    platform = EnterpriseInvestmentPlatformV2()
    assert platform.strategy_registry.status(DIVIDEND_STRATEGY_ID) is StrategyStatus.PAPER_VALIDATION


def test_deposit_remains_unassigned_until_investor_approval() -> None:
    platform = EnterpriseInvestmentPlatformV2()
    platform.record_deposit(12000.0)
    assert platform.capital_manager.unassigned_cash == 12000.0
    assert platform.capital_manager.strategy_balance(DIVIDEND_STRATEGY_ID) == 0.0


def test_capital_report_lists_dividend_strategy() -> None:
    platform = EnterpriseInvestmentPlatformV2()
    platform.record_deposit(10000.0)
    report = platform.build_capital_report(minimum_capital_by_strategy={DIVIDEND_STRATEGY_ID: 5000.0})
    row = next(item for item in report.strategies if item.strategy_id == DIVIDEND_STRATEGY_ID)
    assert row.ready_for_allocation is True
    assert row.minimum_capital == 5000.0


def test_investor_approval_assigns_strategy_capital() -> None:
    platform = EnterpriseInvestmentPlatformV2()
    platform.record_deposit(10000.0)
    report = platform.build_capital_report()
    result = platform.approve_capital(
        report,
        investor_id="INVESTOR-001",
        strategy_allocations={DIVIDEND_STRATEGY_ID: 6000.0},
        reason="Investor selected Dividend",
    )
    assert result.approval.investor_allocations[DIVIDEND_STRATEGY_ID] == 6000.0
    assert platform.capital_manager.strategy_balance(DIVIDEND_STRATEGY_ID) == 6000.0
    assert platform.capital_manager.unassigned_cash == 4000.0


def test_investor_may_choose_different_amount_than_cio_recommendation() -> None:
    platform = EnterpriseInvestmentPlatformV2()
    platform.record_deposit(10000.0)
    report = platform.build_capital_report(
        recommended_allocations={DIVIDEND_STRATEGY_ID: 7000.0},
        recommendation_rationale="Enterprise CIO recommends a partial Dividend allocation",
    )
    result = platform.approve_capital(
        report,
        investor_id="INVESTOR-001",
        strategy_allocations={DIVIDEND_STRATEGY_ID: 5000.0},
        reason="Investor selected a smaller allocation",
    )
    assert result.approval.cio_recommendation[DIVIDEND_STRATEGY_ID] == 7000.0
    assert result.approval.investor_allocations[DIVIDEND_STRATEGY_ID] == 5000.0


def test_dividend_cycle_requires_assigned_capital() -> None:
    platform = EnterpriseInvestmentPlatformV2()
    with pytest.raises(PlatformValidationError):
        platform.run_dividend_paper_cycle(_profile(), {})


def test_funded_dividend_cycle_uses_shared_intelligence() -> None:
    platform = _funded_platform()
    result = platform.run_dividend_paper_cycle(
        _profile(),
        {
            ServiceDomain.INCOME: {"score": 85.0},
            ServiceDomain.RISK: {"score": 20.0},
        },
        quality_score=85.0,
    )
    assert result.profile.income["score"] == 85.0
    assert result.dividend_result.recommendation.strategy_id == DIVIDEND_STRATEGY_ID
    assert result.completed_steps[-1] == "PAPER_ONLY_COMPLETE"


def test_snapshot_preserves_total_managed_capital() -> None:
    platform = EnterpriseInvestmentPlatformV2()
    platform.record_deposit(15000.0)
    report = platform.build_capital_report()
    platform.approve_capital(
        report,
        investor_id="INVESTOR-001",
        strategy_allocations={DIVIDEND_STRATEGY_ID: 9000.0},
        reason="Initial capital assignment",
    )
    snapshot = platform.snapshot()
    assert snapshot.total_managed_capital == 15000.0
    assert snapshot.unassigned_cash == 6000.0
    assert snapshot.strategy_allocations[DIVIDEND_STRATEGY_ID] == 9000.0


def test_snapshot_permanently_enforces_paper_only_rules() -> None:
    snapshot = EnterpriseInvestmentPlatformV2().snapshot()
    assert snapshot.paper_trade_mode is True
    assert snapshot.live_trading_enabled is False
    assert snapshot.broker_execution_enabled is False


def test_no_broker_or_order_interface_exists() -> None:
    platform = EnterpriseInvestmentPlatformV2()
    assert not hasattr(platform, "place_order")
    assert not hasattr(platform, "broker_request")
    assert not hasattr(platform, "robinhood")
