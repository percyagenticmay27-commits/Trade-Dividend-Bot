from __future__ import annotations

import json
from pathlib import Path

import pytest

from enterprise_core.event_bus import EnterpriseEvent, EnterpriseEventBus, JsonLinesEventStore


def _event(event_type: str = "strategy.health.changed") -> EnterpriseEvent:
    return EnterpriseEvent(
        event_type=event_type,
        source="test-suite",
        strategy_id="strategy-001",
        correlation_id="cycle-001",
        payload={"status": "WARNING"},
    )


def test_event_round_trip() -> None:
    event = _event()
    restored = EnterpriseEvent.from_dict(event.to_dict())
    assert restored == event


def test_event_requires_type() -> None:
    with pytest.raises(ValueError, match="event_type is required"):
        EnterpriseEvent(event_type="", source="test", payload={}).validate()


def test_event_rejects_bad_severity() -> None:
    with pytest.raises(ValueError, match="unsupported severity"):
        EnterpriseEvent(event_type="x", source="test", payload={}, severity="LOUD").validate()


def test_event_rejects_live_trading() -> None:
    with pytest.raises(ValueError, match="live_trading_enabled must be false"):
        EnterpriseEvent(event_type="x", source="test", payload={}, live_trading_enabled=True).validate()


def test_publish_delivers_matching_subscriber() -> None:
    received: list[EnterpriseEvent] = []
    bus = EnterpriseEventBus()
    bus.subscribe("strategy.health.changed", received.append)
    result = bus.publish(_event())
    assert result.delivered == 1
    assert not result.failures
    assert received[0].strategy_id == "strategy-001"


def test_publish_does_not_deliver_other_type() -> None:
    received: list[EnterpriseEvent] = []
    bus = EnterpriseEventBus()
    bus.subscribe("other.event", received.append)
    result = bus.publish(_event())
    assert result.delivered == 0
    assert received == []


def test_wildcard_subscriber_receives_all_events() -> None:
    received: list[str] = []
    bus = EnterpriseEventBus()
    bus.subscribe("*", lambda event: received.append(event.event_type))
    bus.publish(_event("one"))
    bus.publish(_event("two"))
    assert received == ["one", "two"]


def test_duplicate_subscription_is_ignored() -> None:
    bus = EnterpriseEventBus()
    handler = lambda event: None
    bus.subscribe("x", handler)
    bus.subscribe("x", handler)
    assert bus.subscriber_count("x") == 1


def test_unsubscribe() -> None:
    bus = EnterpriseEventBus()
    handler = lambda event: None
    bus.subscribe("x", handler)
    assert bus.unsubscribe("x", handler) is True
    assert bus.unsubscribe("x", handler) is False


def test_subscriber_failure_is_isolated() -> None:
    received: list[str] = []
    bus = EnterpriseEventBus()

    def failing(event: EnterpriseEvent) -> None:
        raise RuntimeError("subscriber failed")

    bus.subscribe("x", failing)
    bus.subscribe("x", lambda event: received.append(event.event_id))
    result = bus.publish(_event("x"))
    assert result.delivered == 1
    assert len(result.failures) == 1
    assert "subscriber failed" in result.failures[0].error
    assert len(received) == 1


def test_store_append_and_read(tmp_path: Path) -> None:
    store = JsonLinesEventStore(tmp_path / "events" / "enterprise.jsonl")
    first = _event("one")
    second = _event("two")
    store.append(first)
    store.append(second)
    assert store.read_all() == (first, second)


def test_store_missing_file_is_empty(tmp_path: Path) -> None:
    assert JsonLinesEventStore(tmp_path / "missing.jsonl").read_all() == ()


def test_store_rejects_malformed_line(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps(_event().to_dict()) + "\nnot-json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid event at line 2"):
        JsonLinesEventStore(path).read_all()


def test_components_are_permanently_paper_only() -> None:
    for component in (EnterpriseEventBus(), JsonLinesEventStore("events.jsonl")):
        assert component.paper_trade_mode is True
        assert component.live_trading_enabled is False
        assert component.broker_execution_enabled is False
