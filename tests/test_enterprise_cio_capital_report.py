from __future__ import annotations

from datetime import timedelta

import pytest

from src.dividend_bot.enterprise_capital_manager import CapitalRecommendation, EnterpriseCapitalManager
from src.dividend_bot.enterprise_cio_capital_report import EnterpriseCIOCapitalReporter
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now
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
        supported_audit_types=("RELEASE_AUDIT",),
        module_entry_point=f"example:{strategy_id.title()}",
    )


def _registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    for strategy_id in ("DIVIDEND", "SWING"):
        registry.register(_definition(strategy_id))
        registry.configure(StrategyConfiguration(strategy_id, "1.0.0", {"paper_trade_mode": True}))
        registry.transition(strategy_id, StrategyStatus.CONFIGURED, "Configured")
    registry.transition("DIVIDEND", StrategyStatus.PAPER_VALIDATION, "Validated")
    return registry


def test_report_lists_installed_strategies_and_readiness() -> None:
    manager = EnterpriseCapitalManager(_registry())
    manager.record_deposit(10000)
    report = EnterpriseCIOCapitalReporter(manager).build_report()
    rows = {row.strategy_id: row for row in report.strategies}
    assert rows["DIVIDEND"].ready_for_allocation is True
    assert rows["SWING"].ready_for_allocation is False
    assert report.unassigned_cash == 10000


def test_report_includes_minimums_and_current_allocations() -> None:
    manager = EnterpriseCapitalManager(_registry())
    manager.record_deposit(10000)
    report = EnterpriseCIOCapitalReporter(manager).build_report(
        minimum_capital_by_strategy={"DIVIDEND": 5000, "SWING": 3000}
    )
    rows = {row.strategy_id: row for row in report.strategies}
    assert rows["DIVIDEND"].minimum_capital == 5000
    assert rows["SWING"].minimum_capital == 3000


def test_valid_recommendation_is_advisory_only() -> None:
    manager = EnterpriseCapitalManager(_registry())
    manager.record_deposit(10000)
    recommendation = CapitalRecommendation({"DIVIDEND": 7000}, "Dividend is the only ready strategy")
    report = EnterpriseCIOCapitalReporter(manager).build_report(recommendation=recommendation)
    assert report.recommendation_total == 7000
    assert manager.unassigned_cash == 10000
    assert manager.strategy_balance("DIVIDEND") == 0


def test_recommendation_cannot_exceed_unassigned_cash() -> None:
    manager = EnterpriseCapitalManager(_registry())
    manager.record_deposit(1000)
    recommendation = CapitalRecommendation({"DIVIDEND": 2000}, "Too much")
    with pytest.raises(PlatformValidationError):
        EnterpriseCIOCapitalReporter(manager).build_report(recommendation=recommendation)


def test_recommendation_cannot_target_unready_strategy() -> None:
    manager = EnterpriseCapitalManager(_registry())
    manager.record_deposit(10000)
    recommendation = CapitalRecommendation({"SWING": 1000}, "Swing")
    with pytest.raises(PlatformValidationError):
        EnterpriseCIOCapitalReporter(manager).build_report(recommendation=recommendation)


def test_recommendation_cannot_target_unregistered_strategy() -> None:
    manager = EnterpriseCapitalManager(_registry())
    manager.record_deposit(10000)
    recommendation = CapitalRecommendation({"OPTIONS": 1000}, "Options")
    with pytest.raises(PlatformValidationError):
        EnterpriseCIOCapitalReporter(manager).build_report(recommendation=recommendation)


def test_report_requires_timezone_aware_timestamp() -> None:
    manager = EnterpriseCapitalManager(_registry())
    manager.record_deposit(10000)
    naive = (utc_now() + timedelta(days=1)).replace(tzinfo=None)
    with pytest.raises(PlatformValidationError):
        EnterpriseCIOCapitalReporter(manager).build_report(generated_at=naive)


def test_markdown_contains_investor_approval_notice() -> None:
    manager = EnterpriseCapitalManager(_registry())
    manager.record_deposit(10000)
    report = EnterpriseCIOCapitalReporter(manager).build_report()
    markdown = EnterpriseCIOCapitalReporter(manager).render_markdown(report)
    assert "Investor Approval Required: YES" in markdown
    assert "No capital is assigned by this report" in markdown
    assert "DIVIDEND" in markdown


def test_json_is_deterministic_and_paper_only() -> None:
    manager = EnterpriseCapitalManager(_registry())
    manager.record_deposit(10000)
    report = EnterpriseCIOCapitalReporter(manager).build_report()
    reporter = EnterpriseCIOCapitalReporter(manager)
    first = reporter.render_json(report)
    second = reporter.render_json(report)
    assert first == second
    assert '"paper_trade_mode": true' in first
    assert '"broker_execution_enabled": false' in first


def test_strategy_reasons_are_preserved() -> None:
    manager = EnterpriseCapitalManager(_registry())
    manager.record_deposit(10000)
    recommendation = CapitalRecommendation({"DIVIDEND": 5000}, "Preserve income exposure")
    report = EnterpriseCIOCapitalReporter(manager).build_report(
        recommendation=recommendation,
        recommendation_reasons={"DIVIDEND": "Income strategy is ready and within risk policy"},
    )
    assert report.strategies[0].recommendation_reason
