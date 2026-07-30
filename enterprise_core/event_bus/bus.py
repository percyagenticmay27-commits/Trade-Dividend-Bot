"""Synchronous in-process Version 1 Enterprise Event Bus."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from .models import EnterpriseEvent

EventHandler = Callable[[EnterpriseEvent], None]


@dataclass(frozen=True)
class DeliveryFailure:
    event_id: str
    event_type: str
    handler_name: str
    error: str


@dataclass(frozen=True)
class PublishResult:
    event_id: str
    delivered: int
    failures: tuple[DeliveryFailure, ...]


class EnterpriseEventBus:
    """Validated publish/subscribe bus with isolated subscriber failures."""

    paper_trade_mode = True
    live_trading_enabled = False
    broker_execution_enabled = False

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_subscribers: list[EventHandler] = []

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        if not event_type or not event_type.strip():
            raise ValueError("event_type is required")
        if not callable(handler):
            raise TypeError("handler must be callable")
        target = self._wildcard_subscribers if event_type == "*" else self._subscribers[event_type]
        if handler not in target:
            target.append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> bool:
        target = self._wildcard_subscribers if event_type == "*" else self._subscribers.get(event_type, [])
        if handler not in target:
            return False
        target.remove(handler)
        return True

    def publish(self, event: EnterpriseEvent) -> PublishResult:
        event.validate()
        handlers = tuple(self._subscribers.get(event.event_type, ())) + tuple(self._wildcard_subscribers)
        delivered = 0
        failures: list[DeliveryFailure] = []
        for handler in handlers:
            try:
                handler(event)
                delivered += 1
            except Exception as exc:
                failures.append(
                    DeliveryFailure(
                        event_id=event.event_id,
                        event_type=event.event_type,
                        handler_name=getattr(handler, "__name__", handler.__class__.__name__),
                        error=str(exc),
                    )
                )
        return PublishResult(event.event_id, delivered, tuple(failures))

    def subscriber_count(self, event_type: str | None = None) -> int:
        if event_type is None:
            return len(self._wildcard_subscribers) + sum(len(items) for items in self._subscribers.values())
        if event_type == "*":
            return len(self._wildcard_subscribers)
        return len(self._subscribers.get(event_type, ()))
