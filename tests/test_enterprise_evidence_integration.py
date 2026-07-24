from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from types import MappingProxyType
from uuid import uuid4

import pytest

from src.dividend_bot.enterprise_event_bus import EnterpriseEventBus, EnterpriseEventType
from src.dividend_bot.enterprise_event_integration import EventIntegrationRecord
from src.dividend_bot.enterprise_evidence_integration import (
    EnterpriseEvidenceEntry,
    EnterpriseEvidenceIntegration,
    EnterpriseEvidenceRepository,
    EvidenceEntryType,
)
from src.dividend_bot.platform_foundation import PlatformValidationError, utc_now


def _record(workflow_id: str = "WF-DEC-2026-000001") -> EventIntegrationRecord:
    bus = EnterpriseEventBus()
    correlation = workflow_id
    definitions = (
        (EnterpriseEventType.INTELLIGENCE_UPDATED, "ENTERPRISE_INTELLIGENCE_SERVICE", "MCIP-1"),
        (EnterpriseEventType.CIO_ADVISORY_CREATED, "ENTERPRISE_INTELLIGENCE_CIO_PIPELINE", correlation),
        (EnterpriseEventType.DECISION_CREATED, "ENTERPRISE_DECISION_ENGINE", correlation.replace("WF-", "")),
        (EnterpriseEventType.DECISION_GOVERNANCE_UPDATED, "ENTERPRISE_WORKFLOW_ORCHESTRATOR", correlation.replace("WF-", "")),
    )
    publications = []
    cause = None
    for event_type, source, aggregate in definitions:
        event = bus.create_event(
            event_type,
            source,
            aggregate,
            {"workflow_id": correlation},
            strategy_id="DIVIDEND",
            correlation_id=correlation,
            causation_id=cause,
        )
        publications.append(bus.publish(event))
        cause = event.event_id
    record = EventIntegrationRecord(
        integration_id=publications[0].event.event_id,
        workflow_id=correlation,
        correlation_id=correlation,
        publications=tuple(publications),
        completed_at=utc_now(),
        metadata=MappingProxyType({"investor_review_required": True}),
    )
    record.validate()
    return record


def test_preserve_creates_four_append_only_entries() -> None:
    result = EnterpriseEvidenceIntegration().preserve(_record())
    assert len(result.entries) == 4
    assert tuple(item.entry_type for item in result.entries) == (
        EvidenceEntryType.INTELLIGENCE,
        EvidenceEntryType.CIO_ADVISORY,
        EvidenceEntryType.DECISION,
        EvidenceEntryType.GOVERNANCE,
    )


def test_entries_preserve_workflow_and_correlation() -> None:
    result = EnterpriseEvidenceIntegration().preserve(_record())
    assert all(item.workflow_id == result.workflow_id for item in result.entries)
    assert all(item.correlation_id == result.correlation_id for item in result.entries)


def test_entries_preserve_source_event_links() -> None:
    record = _record()
    result = EnterpriseEvidenceIntegration().preserve(record)
    assert tuple(item.source_event_id for item in result.entries) == tuple(p.event.event_id for p in record.publications)


def test_strategy_scope_is_preserved() -> None:
    result = EnterpriseEvidenceIntegration().preserve(_record())
    assert all(item.strategy_id == "DIVIDEND" for item in result.entries)


def test_repository_is_append_only_tuple_snapshot() -> None:
    integration = EnterpriseEvidenceIntegration()
    integration.preserve(_record())
    assert isinstance(integration.repository.all(), tuple)
    assert len(integration.repository.all()) == 4


def test_repository_filters_by_workflow() -> None:
    integration = EnterpriseEvidenceIntegration()
    result = integration.preserve(_record())
    assert integration.repository.for_workflow(result.workflow_id) == result.entries


def test_successive_workflows_preserve_global_contiguous_sequence() -> None:
    integration = EnterpriseEvidenceIntegration()
    first = integration.preserve(_record("WF-DEC-2026-000001"))
    second = integration.preserve(_record("WF-DEC-2026-000002"))
    assert tuple(item.sequence for item in first.entries) == (1, 2, 3, 4)
    assert tuple(item.sequence for item in second.entries) == (5, 6, 7, 8)
    second.validate()


def test_duplicate_workflow_is_rejected() -> None:
    integration = EnterpriseEvidenceIntegration()
    record = _record()
    integration.preserve(record)
    with pytest.raises(PlatformValidationError):
        integration.preserve(record)


def test_duplicate_source_event_is_rejected() -> None:
    repository = EnterpriseEvidenceRepository()
    event_id = uuid4()
    entry = EnterpriseEvidenceEntry(
        evidence_id=uuid4(), sequence=1, entry_type=EvidenceEntryType.FOLLOW_UP,
        workflow_id="WF-1", correlation_id="WF-1", source_event_id=event_id,
        source_service_id="TEST_SERVICE", aggregate_id="A", payload=MappingProxyType({"x": 1}),
    )
    repository.append(entry)
    with pytest.raises(PlatformValidationError):
        repository.append(replace(entry, evidence_id=uuid4(), sequence=2))


def test_repository_rejects_out_of_order_sequence() -> None:
    repository = EnterpriseEvidenceRepository()
    entry = EnterpriseEvidenceEntry(
        evidence_id=uuid4(), sequence=2, entry_type=EvidenceEntryType.FOLLOW_UP,
        workflow_id="WF-1", correlation_id="WF-1", source_event_id=uuid4(),
        source_service_id="TEST_SERVICE", aggregate_id="A", payload=MappingProxyType({}),
    )
    with pytest.raises(PlatformValidationError):
        repository.append(entry)


def test_preserve_rejects_naive_completed_at() -> None:
    with pytest.raises(PlatformValidationError):
        EnterpriseEvidenceIntegration().preserve(_record(), completed_at=datetime(2026, 7, 24))


def test_entry_rejects_unsafe_flags() -> None:
    result = EnterpriseEvidenceIntegration().preserve(_record())
    with pytest.raises(PlatformValidationError):
        replace(result.entries[0], paper_trade_mode=False).validate()


def test_entry_payload_is_immutable_mapping() -> None:
    result = EnterpriseEvidenceIntegration().preserve(_record())
    assert isinstance(result.entries[0].payload, MappingProxyType)
    with pytest.raises(TypeError):
        result.entries[0].payload["new"] = True


def test_json_and_markdown_preserve_boundaries() -> None:
    integration = EnterpriseEvidenceIntegration()
    result = integration.preserve(_record())
    json_output = integration.render_json(result)
    markdown = integration.render_markdown(result)
    assert '"append_only": true' in json_output
    assert "No approval, capital movement, portfolio mutation, broker call, or order placement" in markdown


def test_history_is_append_only_tuple_snapshot() -> None:
    integration = EnterpriseEvidenceIntegration()
    integration.preserve(_record())
    assert isinstance(integration.history(), tuple)
    assert len(integration.history()) == 1


def test_integration_has_no_execution_interfaces() -> None:
    integration = EnterpriseEvidenceIntegration()
    assert not hasattr(integration, "approve")
    assert not hasattr(integration, "assign_capital")
    assert not hasattr(integration, "place_order")
