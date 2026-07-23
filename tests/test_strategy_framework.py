from __future__ import annotations

import pytest

from src.dividend_bot.platform_foundation import PlatformValidationError
from src.dividend_bot.strategy_framework import (
    StrategyConfiguration,
    StrategyDefinition,
    StrategyRegistry,
    StrategyStatus,
)


def make_definition(strategy_id: str = "DIVIDEND", version: str = "1.0.0") -> StrategyDefinition:
    return StrategyDefinition(
        strategy_id=strategy_id,
        name=f"{strategy_id.title()} Strategy",
        version=version,
        supported_asset_types=("EQUITY", "ETF"),
        required_intelligence=("fundamentals", "risk", "income"),
        supported_report_types=("WEEKLY", "MONTHLY", "AUDIT"),
        supported_audit_types=("PERFORMANCE", "CONSTITUTIONAL"),
        module_entry_point="src.dividend_bot.strategies.dividend",
    )


def test_strategy_definition_is_paper_only() -> None:
    unsafe = make_definition()
    object.__setattr__(unsafe, "live_trading_enabled", True)
    with pytest.raises(PlatformValidationError):
        unsafe.validate()


def test_registry_registers_and_lists_definitions() -> None:
    registry = StrategyRegistry()
    registry.register(make_definition("DIVIDEND"))
    registry.register(make_definition("SWING"))
    assert [item.strategy_id for item in registry.list_definitions()] == ["DIVIDEND", "SWING"]


def test_conflicting_registration_is_rejected() -> None:
    registry = StrategyRegistry()
    registry.register(make_definition())
    with pytest.raises(PlatformValidationError):
        registry.register(make_definition(version="1.1.0"))


def test_configuration_must_match_registered_version() -> None:
    registry = StrategyRegistry()
    registry.register(make_definition())
    with pytest.raises(PlatformValidationError):
        registry.configure(StrategyConfiguration("DIVIDEND", "2.0.0", {}))


def test_unsafe_configuration_is_rejected() -> None:
    configuration = StrategyConfiguration(
        "DIVIDEND", "1.0.0", {"broker_execution_enabled": True}
    )
    with pytest.raises(PlatformValidationError):
        configuration.validate()


def test_strategy_requires_configuration_before_configured_status() -> None:
    registry = StrategyRegistry()
    registry.register(make_definition())
    with pytest.raises(PlatformValidationError):
        registry.transition("DIVIDEND", StrategyStatus.CONFIGURED, "ready")


def test_valid_lifecycle_reaches_operational() -> None:
    registry = StrategyRegistry()
    registry.register(make_definition())
    registry.configure(StrategyConfiguration("DIVIDEND", "1.0.0", {"yield_floor": 3.0}))
    registry.transition("DIVIDEND", StrategyStatus.CONFIGURED, "configuration validated")
    registry.transition("DIVIDEND", StrategyStatus.PAPER_VALIDATION, "start paper validation")
    registry.transition("DIVIDEND", StrategyStatus.OPERATIONAL, "paper validation passed")
    assert registry.status("DIVIDEND") is StrategyStatus.OPERATIONAL
    assert len(registry.history("DIVIDEND")) == 3


def test_invalid_lifecycle_transition_is_rejected() -> None:
    registry = StrategyRegistry()
    registry.register(make_definition())
    with pytest.raises(PlatformValidationError):
        registry.transition("DIVIDEND", StrategyStatus.OPERATIONAL, "skip validation")


def test_archived_strategy_cannot_transition() -> None:
    registry = StrategyRegistry()
    registry.register(make_definition())
    registry.transition("DIVIDEND", StrategyStatus.ARCHIVED, "retired")
    with pytest.raises(PlatformValidationError):
        registry.transition("DIVIDEND", StrategyStatus.CONFIGURED, "restore")


def test_strategy_histories_remain_isolated() -> None:
    registry = StrategyRegistry()
    for strategy_id in ("DIVIDEND", "SWING"):
        registry.register(make_definition(strategy_id))
        registry.configure(StrategyConfiguration(strategy_id, "1.0.0", {}))
        registry.transition(strategy_id, StrategyStatus.CONFIGURED, "configured")
    assert all(event.strategy_id == "DIVIDEND" for event in registry.history("DIVIDEND"))
    assert all(event.strategy_id == "SWING" for event in registry.history("SWING"))
