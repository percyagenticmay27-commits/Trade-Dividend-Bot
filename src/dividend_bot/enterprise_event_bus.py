"""Governed synchronous event bus for the paper-only enterprise platform.

The bus provides deterministic, append-only in-process event delivery. It does not create
threads, queues, network connections, OS jobs, capital movements, broker requests, or orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Callable, Mapping
from uuid import UUID

from .platform_foundation import IdentifierFactory, JsonSerializer, PlatformValidationError, utc_now

MODULE_NAME = "enterprise_event_bus"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Publish immutable governed platform events in deterministic subscriber order."


class EnterpriseEventType(str, Enum):
    COMPANY_DISCOVERED = "COMPANY_DISCOVERED"
    INTELLIGENCE_UPDATED = "INTELLIGENCE_UPDATED"
    EVIDENCE_APPENDED = "EVIDENCE_APPENDED"
    CIO_ADVISORY_CREATED = "CIO_ADVISORY_CREATED"
    DECISION_CREATED = "DECISION_CREATED"
    DECISION_GOVERNANCE_UPDATED = "DECISION_GOVERNANCE_UPDATED"
    INVESTOR_ACTION_RECORDED = "INVESTOR_ACTION_RECORDED"
    CAPITAL_ALLOCATION_UPDATED = "CAPITAL_ALLOCATION_UPDATED"
    STRATEGY_EXECUTION_RECORDED = "STRATEGY_EXECUTION_RECORDED"
    PORTFOLIO_POSITION_UPDATED = "PORTFOLIO_POSITION_UPDATED"
    REPORT_CREATED = "REPORT_CREATED"
    LEARNING_RECORDED = "LEARNING_RECORDED"


@dataclass(frozen=True)
class EnterpriseEvent:
    event_id: UUID
    event_type: EnterpriseEventType
    source_service_id: str
    aggregate_id: str
    payload: Mapping[str, object]
    occurred_at: datetime = field(default_factory=utc_now)
    event_version: str = "1.0.0"
    strategy_id: str | None = None
    correlation_id: str | None = None
    causation_id: UUID | None = None
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    def validate(self) -> None:
        if not self.source_service_id or self.source_service_id != self.source_service_id.upper():
            raise PlatformValidationError("source_service_id must be non-empty uppercase text")
        if not self.aggregate_id.strip():
            raise PlatformValidationError("aggregate_id is required")
        if not isinstance(self.payload, Mapping):
            raise PlatformValidationError("event payload must be a mapping")
        if self.occurred_at.tzinfo is None:
            raise PlatformValidationError("occurred_at must be timezone-aware")
        parts = self.event_version.split(".")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            raise PlatformValidationError("event_version must use semantic versioning")
        if self.strategy_id is not None and self.strategy_id != self.strategy_id.upper():
            raise PlatformValidationError("strategy_id must be uppercase when provided")
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False or self.broker_execution_enabled is not False:
            raise PlatformValidationError("live trading and broker execution must remain disabled")


@dataclass(frozen=True)
class EventDelivery:
    event_id: UUID
    subscriber_id: str
    sequence: int
    delivered_at: datetime
    accepted: bool
    detail: str

    def validate(self) -> None:
        if not self.subscriber_id or self.subscriber_id != self.subscriber_id.upper():
            raise PlatformValidationError("subscriber_id must be non-empty uppercase text")
        if self.sequence < 1:
            raise PlatformValidationError("delivery sequence must be positive")
        if self.delivered_at.tzinfo is None:
            raise PlatformValidationError("delivered_at must be timezone-aware")
        if not self.detail.strip():
            raise PlatformValidationError("delivery detail is required")


@dataclass(frozen=True)
class EventPublication:
    event: EnterpriseEvent
    deliveries: tuple[EventDelivery, ...]
    published_at: datetime

    def validate(self) -> None:
        self.event.validate()
        if self.published_at.tzinfo is None:
            raise PlatformValidationError("published_at must be timezone-aware")
        for index, delivery in enumerate(self.deliveries, start=1):
            delivery.validate()
            if delivery.event_id != self.event.event_id:
                raise PlatformValidationError("delivery must reference the published event")
            if delivery.sequence != index:
                raise PlatformValidationError("deliveries must preserve deterministic sequence")


EventHandler = Callable[[EnterpriseEvent], bool | None]


@dataclass(frozen=True)
class _Subscription:
    subscriber_id: str
    event_type: EnterpriseEventType
    handler: EventHandler
    strategy_id: str | None
    order: int


class EnterpriseEventBus:
    """Publish immutable events synchronously in deterministic subscription order."""

    def __init__(self) -> None:
        self._subscriptions: list[_Subscription] = []
        self._publications: list[EventPublication] = []
        self._published_ids: set[UUID] = set()
        self._frozen = False

    def subscribe(
        self,
        subscriber_id: str,
        event_type: EnterpriseEventType,
        handler: EventHandler,
        *,
        strategy_id: str | None = None,
    ) -> None:
        if self._frozen:
            raise PlatformValidationError("event bus subscriptions are frozen")
        if not subscriber_id or subscriber_id != subscriber_id.upper():
            raise PlatformValidationError("subscriber_id must be non-empty uppercase text")
        if not callable(handler):
            raise PlatformValidationError("event handler must be callable")
        if strategy_id is not None and strategy_id != strategy_id.upper():
            raise PlatformValidationError("strategy_id must be uppercase when provided")
        key = (subscriber_id, event_type, strategy_id)
        if any((item.subscriber_id, item.event_type, item.strategy_id) == key for item in self._subscriptions):
            raise PlatformValidationError("duplicate event subscription")
        self._subscriptions.append(
            _Subscription(subscriber_id, event_type, handler, strategy_id, len(self._subscriptions) + 1)
        )

    def freeze(self) -> None:
        self._frozen = True

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    def subscriptions(self) -> tuple[tuple[str, EnterpriseEventType, str | None], ...]:
        return tuple((item.subscriber_id, item.event_type, item.strategy_id) for item in self._subscriptions)

    def history(self) -> tuple[EventPublication, ...]:
        return tuple(self._publications)

    @staticmethod
    def create_event(
        event_type: EnterpriseEventType,
        source_service_id: str,
        aggregate_id: str,
        payload: Mapping[str, object],
        *,
        strategy_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: UUID | None = None,
        occurred_at: datetime | None = None,
    ) -> EnterpriseEvent:
        event = EnterpriseEvent(
            event_id=IdentifierFactory.new_internal_id(),
            event_type=event_type,
            source_service_id=source_service_id,
            aggregate_id=aggregate_id,
            payload=MappingProxyType(dict(payload)),
            occurred_at=occurred_at or utc_now(),
            strategy_id=strategy_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        event.validate()
        return event

    def publish(self, event: EnterpriseEvent, *, published_at: datetime | None = None) -> EventPublication:
        event.validate()
        if event.event_id in self._published_ids:
            raise PlatformValidationError("event has already been published")
        timestamp = published_at or utc_now()
        if timestamp.tzinfo is None:
            raise PlatformValidationError("published_at must be timezone-aware")

        matched = [
            item
            for item in self._subscriptions
            if item.event_type is event.event_type
            and (item.strategy_id is None or item.strategy_id == event.strategy_id)
        ]
        matched.sort(key=lambda item: item.order)
        deliveries: list[EventDelivery] = []
        for sequence, subscription in enumerate(matched, start=1):
            try:
                response = subscription.handler(event)
                accepted = response is not False
                detail = "Event accepted." if accepted else "Event explicitly declined."
            except Exception as exc:  # delivery failure is recorded; later subscribers still receive the event
                accepted = False
                detail = f"Handler failed: {type(exc).__name__}: {exc}"
            delivery = EventDelivery(
                event_id=event.event_id,
                subscriber_id=subscription.subscriber_id,
                sequence=sequence,
                delivered_at=timestamp,
                accepted=accepted,
                detail=detail,
            )
            delivery.validate()
            deliveries.append(delivery)

        publication = EventPublication(event=event, deliveries=tuple(deliveries), published_at=timestamp)
        publication.validate()
        self._publications.append(publication)
        self._published_ids.add(event.event_id)
        return publication

    @staticmethod
    def render_json(publication: EventPublication) -> str:
        publication.validate()
        return JsonSerializer.dumps(publication)

    @staticmethod
    def render_markdown(publication: EventPublication) -> str:
        publication.validate()
        lines = [
            "# Enterprise Event Publication",
            "",
            f"- Event ID: {publication.event.event_id}",
            f"- Event Type: {publication.event.event_type.value}",
            f"- Source Service: {publication.event.source_service_id}",
            f"- Aggregate ID: {publication.event.aggregate_id}",
            f"- Strategy ID: {publication.event.strategy_id or 'ENTERPRISE'}",
            f"- Deliveries: {len(publication.deliveries)}",
            f"- Paper Trade Mode: {'YES' if publication.event.paper_trade_mode else 'NO'}",
            "",
            "## Delivery Results",
            "",
        ]
        if publication.deliveries:
            lines.extend(
                f"- {item.sequence}. {item.subscriber_id}: {'ACCEPTED' if item.accepted else 'DECLINED'} — {item.detail}"
                for item in publication.deliveries
            )
        else:
            lines.append("- No subscribers matched this event.")
        lines.extend(
            [
                "",
                "## Safety Boundary",
                "",
                "This event bus performs synchronous in-process notification only. It does not move capital, mutate portfolios, call brokers, place orders, create threads, or install schedules.",
                "",
            ]
        )
        return "\n".join(lines)
