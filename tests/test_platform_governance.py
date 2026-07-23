from dataclasses import replace

import pytest

from src.dividend_bot.platform_entities import (
    AICIODecision,
    DecisionState,
    EvidenceRecord,
    new_identity,
)
from src.dividend_bot.platform_foundation import IdentifierKind, PlatformValidationError, utc_now
from src.dividend_bot.platform_governance import (
    DecisionLedger,
    EvidenceAppendEntry,
    EvidenceAppendType,
    EvidenceRepository,
)


def make_evidence(subject_id):
    return EvidenceRecord(
        identity=new_identity(IdentifierKind.EVIDENCE),
        subject_type="COMPANY",
        subject_id=subject_id,
        evidence_type="EARNINGS",
        source="Company filing",
        summary="Revenue increased year over year.",
        quality_score=95.0,
        observed_at=utc_now(),
    )


def make_decision(strategy_id="dividend", state=DecisionState.DRAFT):
    return AICIODecision(
        identity=new_identity(IdentifierKind.DECISION),
        strategy_id=strategy_id,
        recommendation_id=new_identity("REC").internal_id,
        paper_action="HOLD",
        rationale="Income durability remains acceptable.",
        confidence=82.0,
        constitution_version="1.0.0",
        state=state,
    )


def test_evidence_repository_is_append_only():
    subject_id = new_identity(IdentifierKind.COMPANY).internal_id
    record = make_evidence(subject_id)
    repository = EvidenceRepository()
    repository.add(record)

    with pytest.raises(PlatformValidationError):
        repository.add(record)


def test_evidence_timeline_preserves_original_and_appends():
    subject_id = new_identity(IdentifierKind.COMPANY).internal_id
    record = make_evidence(subject_id)
    repository = EvidenceRepository()
    repository.add(record)
    repository.append(
        EvidenceAppendEntry(
            evidence_id=record.identity.internal_id,
            append_type=EvidenceAppendType.FOLLOW_UP,
            content="Management clarified forward guidance.",
            source="Earnings call",
        )
    )

    timeline = repository.timeline(record.identity.internal_id)
    assert timeline[0] is record
    assert timeline[1].append_type is EvidenceAppendType.FOLLOW_UP


def test_evidence_append_rejects_unknown_record():
    with pytest.raises(PlatformValidationError):
        EvidenceRepository().append(
            EvidenceAppendEntry(
                evidence_id=new_identity(IdentifierKind.EVIDENCE).internal_id,
                append_type=EvidenceAppendType.NEW_INFORMATION,
                content="New fact",
                source="Source",
            )
        )


def test_evidence_list_for_subject_is_scoped():
    first_subject = new_identity(IdentifierKind.COMPANY).internal_id
    second_subject = new_identity(IdentifierKind.COMPANY).internal_id
    repository = EvidenceRepository()
    repository.add(make_evidence(first_subject))
    repository.add(make_evidence(second_subject))
    assert len(repository.list_for_subject(first_subject)) == 1


def test_decision_ledger_rejects_duplicate_decision():
    decision = make_decision()
    ledger = DecisionLedger()
    ledger.record(decision)
    with pytest.raises(PlatformValidationError):
        ledger.record(decision)


def test_decision_lifecycle_transition_is_recorded():
    decision = make_decision()
    ledger = DecisionLedger()
    ledger.record(decision)
    updated = ledger.transition(decision.identity.internal_id, DecisionState.READY_FOR_REVIEW)
    assert updated.state is DecisionState.READY_FOR_REVIEW
    assert len(ledger.history(decision.identity.internal_id)) == 2


def test_invalid_decision_transition_is_rejected():
    decision = make_decision()
    ledger = DecisionLedger()
    ledger.record(decision)
    with pytest.raises(PlatformValidationError):
        ledger.transition(decision.identity.internal_id, DecisionState.IMPLEMENTED)


def test_investor_override_preserves_original_and_replacement():
    original = make_decision(state=DecisionState.READY_FOR_CIO)
    replacement = make_decision(state=DecisionState.IMPLEMENTED)
    ledger = DecisionLedger()
    ledger.record(original)
    override = ledger.override(
        original.identity.internal_id,
        replacement,
        investor_id="INVESTOR-001",
        reason="Investor requires a lower-risk paper action.",
    )

    assert ledger.get(original.identity.internal_id).state is DecisionState.OVERRIDDEN_BY_INVESTOR
    assert ledger.get(replacement.identity.internal_id) is replacement
    assert override.reason
    assert len(ledger.overrides) == 1


def test_override_cannot_cross_strategy_boundary():
    original = make_decision("dividend", DecisionState.READY_FOR_CIO)
    replacement = make_decision("swing", DecisionState.IMPLEMENTED)
    ledger = DecisionLedger()
    ledger.record(original)
    with pytest.raises(PlatformValidationError):
        ledger.override(
            original.identity.internal_id,
            replacement,
            investor_id="INVESTOR-001",
            reason="Invalid cross-strategy override.",
        )


def test_strategy_queries_remain_isolated():
    ledger = DecisionLedger()
    ledger.record(make_decision("dividend"))
    ledger.record(make_decision("swing"))
    assert len(ledger.list_by_strategy("dividend")) == 1
    assert len(ledger.list_by_strategy("swing")) == 1


def test_governance_records_require_timezone_aware_timestamps():
    record = EvidenceAppendEntry(
        evidence_id=new_identity(IdentifierKind.EVIDENCE).internal_id,
        append_type=EvidenceAppendType.CORRECTION,
        content="Correction",
        source="Official source",
        appended_at=utc_now().replace(tzinfo=None),
    )
    with pytest.raises(PlatformValidationError):
        record.validate()
