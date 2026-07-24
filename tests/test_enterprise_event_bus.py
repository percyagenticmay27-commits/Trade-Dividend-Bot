from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from dividend_bot.enterprise_event_bus import (
    EnterpriseEvent,
    EnterpriseEventBus,
    EnterpriseEventType,
)
from dividend_bot.platform_foundation import PlatformValidationError


def _event(*, strategy_id: str | None = None) -> EnterpriseEvent:
    return EnterpriseEventBus.create_event(
        EnterpriseEventType.DECISION_CREATED,
        "ENTERPRISE_DECISION_ENGINE",
        "DEC-2026-000001",
        {"action": "REVIEW"},
        strategy_id=strategy_id,
        correlation_id="WF-DEC-2026-000001",
        occurred_at=datetime(2026, 7, 24, 15, 30, tzinfo=timezone.utc),
    )


def test_create_event_is_immutable_and_paper_only() -> None:
    event = _event(strategy_id="DIVIDEND")
    event.validate()
    assert isinstance(event.payload, MappingProxyType)
    assert event.paper_trade_mode is True
    assert event.live_trading_enabled is False
    assert event.broker_execution_enabled is False


def test_invalid_source_service_is_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        EnterpriseEventBus.create_event(
            EnterpriseEventType.DECISION_CREATED,
            "bad-service",
            "DEC-1",
            {},
        )


def test_duplicate_subscription_is_rejected() -> None:
    bus = EnterpriseEventBus()
    bus.subscribe("REPORTING", EnterpriseEventType.DECISION_CREATED, lambda event: True)
    with pytest.raises(PlatformValidationError):
        bus.subscribe("REPORTING", EnterpriseEventType.DECISION_CREATED, lambda event: True)


def test_freeze_prevents_new_subscriptions() -> None:
    bus = EnterpriseEventBus()
    bus.freeze()
    assert bus.is_frozen is True
    with pytest.raises(PlatformValidationError):
        bus.subscribe("REPORTING", EnterpriseEventType.DECISION_CREATED, lambda event: True)


def test_publish_preserves_subscription_order() -> None:
    seen: list[str] = []
    bus = EnterpriseEventBus()
    bus.subscribe("FIRST", EnterpriseEventType.DECISION_CREATED, lambda event: seen.append("FIRST"))
    bus.subscribe("SECOND", EnterpriseEventType.DECISION_CREATED, lambda event: seen.append("SECOND"))
    result = bus.publish(_event(), published_at=datetime(2026, 7, 24, 15, 31, tzinfo=timezone.utc))
    assert seen == ["FIRST", "SECOND"]
    assert [item.sequence for item in result.deliveries] == [1, 2]


def test_strategy_subscription_is_isolated() -> None:
    bus = EnterpriseEventBus()
    seen: list[str] = []
    bus.subscribe(
        "DIVIDEND_REPORTING",
        EnterpriseEventType.DECISION_CREATED,
        lambda event: seen.append("DIVIDEND"),
        strategy_id="DIVIDEND",
    )
    bus.subscribe(
        "SWING_REPORTING",
        EnterpriseEventType.DECISION_CREATED,
        lambda event: seen.append("SWING"),
        strategy_id="SWING",
    )
    result = bus.publish(_event(strategy_id="DIVIDEND"))
    assert seen == ["DIVIDEND"]
    assert tuple(item.subscriber_id for item in result.deliveries) == ("DIVIDEND_REPORTING",)


def test_enterprise_subscription_receives_strategy_event() -> None:
    bus = EnterpriseEventBus()
    seen: list[str] = []
    bus.subscribe("ENTERPRISE_AUDIT", EnterpriseEventType.DECISION_CREATED, lambda event: seen.append("AUDIT"))
    bus.publish(_event(strategy_id="DIVIDEND"))
    assert seen == ["AUDIT"]


def test_handler_decline_is_recorded() -> None:
    bus = EnterpriseEventBus()
    bus.subscribe("REVIEWER", EnterpriseEventType.DECISION_CREATED, lambda event: False)
    result = bus.publish(_event())
    assert result.deliveries[0].accepted is False
    assert "declined" in result.deliveries[0].detail.lower()


def test_handler_failure_does_not_stop_later_delivery() -> None:
    bus = EnterpriseEventBus()
    seen: list[str] = []

    def fail(event: EnterpriseEvent) -> bool:
        raise RuntimeError("test failure")

    bus.subscribe("FAILURE", EnterpriseEventType.DECISION_CREATED, fail)
    bus.subscribe("LATER", EnterpriseEventType.DECISION_CREATED, lambda event: seen.append("LATER"))
    result = bus.publish(_event())
    assert result.deliveries[0].accepted is False
    assert result.deliveries[1].accepted is True
    assert seen == ["LATER"]


def test_event_without_subscribers_is_still_recorded() -> None:
    bus = EnterpriseEventBus()
    result = bus.publish(_event())
    assert result.deliveries == ()
    assert bus.history() == (result,)


def test_duplicate_event_publication_is_rejected() -> None:
    bus = EnterpriseEventBus()
    event = _event()
    bus.publish(event)
    with pytest.raises(PlatformValidationError):
        bus.publish(event)


def test_history_is_append_only_tuple_snapshot() -> None:
    bus = EnterpriseEventBus()
    first = bus.publish(_event())
    snapshot = bus.history()
    second = bus.publish(_event(strategy_id="DIVIDEND"))
    assert snapshot == (first,)
    assert bus.history() == (first, second)


def test_json_and_markdown_preserve_event_boundary() -> None:
    bus = EnterpriseEventBus()
    result = bus.publish(_event(strategy_id="DIVIDEND"))
    json_output = bus.render_json(result)
    markdown = bus.render_markdown(result)
    assert '"event_type": "DECISION_CREATED"' in json_output
    assert '"strategy_id": "DIVIDEND"' in json_output
    assert "# Enterprise Event Publication" in markdown
    assert "does not move capital" in markdown


def test_event_rejects_unsafe_flags() -> None:
    safe = _event()
    unsafe = EnterpriseEvent(
        event_id=safe.event_id,
        event_type=safe.event_type,
        source_service_id=safe.source_service_id,
        aggregate_id=safe.aggregate_id,
        payload=safe.payload,
        occurred_at=safe.occurred_at,
        paper_trade_mode=False,
    )
    with pytest.raises(PlatformValidationError):
        unsafe.validate()


def test_bus_has_no_broker_or_order_interface() -> None:
    forbidden = {"send_order", "place_order", "submit_order", "connect_broker", "move_capital"}
    assert forbidden.isdisjoint(set(dir(EnterpriseEventBus)))
