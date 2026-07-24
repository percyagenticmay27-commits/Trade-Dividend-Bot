from __future__ import annotations

import json

import pytest

from dividend_bot.enterprise_service_registry import (
    EnterpriseServiceContainer,
    EnterpriseServiceRegistry,
    ServiceRegistration,
    ServiceScope,
)
from dividend_bot.platform_foundation import PlatformValidationError


class ExampleService:
    pass


def test_registration_requires_uppercase_service_id() -> None:
    registry = EnterpriseServiceRegistry()
    with pytest.raises(PlatformValidationError):
        registry.register(ServiceRegistration("bad_service", ExampleService()))


def test_duplicate_identical_registration_is_idempotent() -> None:
    registry = EnterpriseServiceRegistry()
    service = ExampleService()
    registration = ServiceRegistration("EXAMPLE", service)
    registry.register(registration)
    registry.register(registration)
    assert registry.resolve("EXAMPLE") is service


def test_conflicting_registration_is_rejected() -> None:
    registry = EnterpriseServiceRegistry()
    registry.register(ServiceRegistration("EXAMPLE", ExampleService()))
    with pytest.raises(PlatformValidationError):
        registry.register(ServiceRegistration("EXAMPLE", ExampleService()))


def test_missing_dependency_is_rejected_on_freeze() -> None:
    registry = EnterpriseServiceRegistry()
    registry.register(ServiceRegistration("CHILD", ExampleService(), dependencies=("MISSING",)))
    with pytest.raises(PlatformValidationError):
        registry.freeze()


def test_dependency_order_places_dependencies_first() -> None:
    registry = EnterpriseServiceRegistry()
    registry.register(ServiceRegistration("CHILD", ExampleService(), dependencies=("PARENT",)))
    registry.register(ServiceRegistration("PARENT", ExampleService()))
    assert registry.ordered_service_ids() == ("PARENT", "CHILD")


def test_cyclic_dependencies_are_rejected() -> None:
    registry = EnterpriseServiceRegistry()
    registry.register(ServiceRegistration("A_SERVICE", ExampleService(), dependencies=("B_SERVICE",)))
    registry.register(ServiceRegistration("B_SERVICE", ExampleService(), dependencies=("A_SERVICE",)))
    with pytest.raises(PlatformValidationError):
        registry.freeze()


def test_frozen_registry_rejects_new_registration() -> None:
    registry = EnterpriseServiceRegistry()
    registry.register(ServiceRegistration("EXAMPLE", ExampleService()))
    registry.freeze()
    with pytest.raises(PlatformValidationError):
        registry.register(ServiceRegistration("LATE", ExampleService()))


def test_strategy_scope_requires_strategy_id() -> None:
    with pytest.raises(PlatformValidationError):
        ServiceRegistration("DIVIDEND_REPORTING", ExampleService(), scope=ServiceScope.STRATEGY).validate()


def test_platform_scope_rejects_strategy_id() -> None:
    with pytest.raises(PlatformValidationError):
        ServiceRegistration("PLATFORM_SERVICE", ExampleService(), strategy_id="DIVIDEND").validate()


def test_strategy_services_remain_isolated() -> None:
    registry = EnterpriseServiceRegistry()
    dividend = ServiceRegistration(
        "DIVIDEND_REPORTING",
        ExampleService(),
        scope=ServiceScope.STRATEGY,
        strategy_id="DIVIDEND",
    )
    swing = ServiceRegistration(
        "SWING_REPORTING",
        ExampleService(),
        scope=ServiceScope.STRATEGY,
        strategy_id="SWING",
    )
    registry.register(dividend)
    registry.register(swing)
    assert registry.for_strategy("DIVIDEND") == (dividend,)
    assert registry.for_strategy("SWING") == (swing,)


def test_default_container_builds_and_freezes_registry() -> None:
    container = EnterpriseServiceContainer.build_default()
    container.validate()
    assert container.registry.frozen is True


def test_default_container_preserves_shared_service_identity() -> None:
    container = EnterpriseServiceContainer.build_default()
    assert container.registry.resolve("ENTERPRISE_DECISION_ENGINE") is container.decision_engine
    assert container.workflow_orchestrator.decision_engine is container.decision_engine


def test_default_dependency_order_is_deterministic() -> None:
    container = EnterpriseServiceContainer.build_default()
    order = container.registry.ordered_service_ids()
    assert order.index("ENTERPRISE_INTELLIGENCE_SERVICE") < order.index("ENTERPRISE_WORKFLOW_ORCHESTRATOR")
    assert order.index("ENTERPRISE_CIO_PIPELINE") < order.index("ENTERPRISE_WORKFLOW_ORCHESTRATOR")
    assert order.index("ENTERPRISE_DECISION_ENGINE") < order.index("ENTERPRISE_WORKFLOW_ORCHESTRATOR")
    assert order.index("ENTERPRISE_WORKFLOW_ORCHESTRATOR") < order.index("ENTERPRISE_DAILY_CYCLE")


def test_json_and_markdown_preserve_execution_boundary() -> None:
    container = EnterpriseServiceContainer.build_default()
    payload = json.loads(container.registry.render_json())
    markdown = container.registry.render_markdown()
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert "does not run workflows" in markdown
    assert "broker APIs" in markdown


def test_registry_has_no_execution_or_broker_interfaces() -> None:
    forbidden = {
        "run",
        "execute",
        "place_order",
        "submit_order",
        "broker_request",
        "allocate_capital",
        "mutate_portfolio",
    }
    assert forbidden.isdisjoint(set(dir(EnterpriseServiceRegistry)))
