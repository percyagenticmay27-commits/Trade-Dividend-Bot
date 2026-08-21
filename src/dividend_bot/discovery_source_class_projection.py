"""Canonical AI CIO source-class propagation for the SWING-001 discovery bucket.

AI CIO owns source classification.  This adapter translates legacy producer-internal
class labels into the shared cross-service vocabulary and copies the authoritative
class into each projected ``evidence_sources`` record.  It never infers trust in the
Swing service and never changes Discovery Leadership values.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

SHARED_SOURCE_CLASSES = {
    "PRIMARY_REGULATORY",
    "COMPANY_PRIMARY",
    "INSTITUTIONAL_NEWS",
    "PROFESSIONAL_RESEARCH",
    "PROFESSIONAL_CREATOR",
    "MARKET_ANALYTICS",
    "SOCIAL_COMMUNITY",
}

LEGACY_SOURCE_CLASS_MAP = {
    "PROFESSIONAL_MEDIA": "INSTITUTIONAL_NEWS",
    "CREATOR_INTELLIGENCE": "PROFESSIONAL_CREATOR",
}


def canonical_source_class(evidence: Mapping[str, Any]) -> str | None:
    """Return AI CIO's shared external source class, or None when unclassified.

    ``PRIMARY_COMPANY`` is a legacy producer label that historically covered both
    SEC evidence and company-primary feeds.  Structured SEC provenance is resolved
    inside AI CIO; all other legacy PRIMARY_COMPANY evidence maps to COMPANY_PRIMARY.
    """
    raw = str(evidence.get("source_class") or "").strip().upper()
    if not raw or raw == "UNCLASSIFIED":
        return None
    if raw in SHARED_SOURCE_CLASSES:
        return raw
    if raw in LEGACY_SOURCE_CLASS_MAP:
        return LEGACY_SOURCE_CLASS_MAP[raw]
    if raw == "PRIMARY_COMPANY":
        producer = str(evidence.get("producer") or "").strip().lower()
        source = str(evidence.get("source") or "").strip().lower()
        if "securities and exchange commission" in producer or source.startswith("sec edgar"):
            return "PRIMARY_REGULATORY"
        return "COMPANY_PRIMARY"
    return None


def _source_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("source") or "").strip().casefold(),
        str(row.get("mentioned_on") or "")[:10],
    )


def propagate_source_classes_to_swing_bucket(
    bucket: Mapping[str, Any],
    weekly_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Add authoritative source_class metadata without changing the SWING contract."""
    if str(bucket.get("schema_version")) != "1.0" or str(bucket.get("strategy_id")) != "SWING-001":
        raise ValueError("unexpected SWING-001 discovery contract")

    report_by_symbol = {
        str(row.get("underlying_symbol") or "").strip().upper(): row
        for row in weekly_report.get("candidates", [])
        if isinstance(row, Mapping)
    }

    projected_candidates: list[dict[str, Any]] = []
    for candidate_raw in bucket.get("candidates", []):
        if not isinstance(candidate_raw, Mapping):
            continue
        candidate = dict(candidate_raw)
        symbol = str(candidate.get("underlying_symbol") or "").strip().upper()
        report_row = report_by_symbol.get(symbol, {})

        authority: dict[tuple[str, str], set[str]] = defaultdict(set)
        for evidence in report_row.get("source_evidence", []) or []:
            if not isinstance(evidence, Mapping):
                continue
            source_class = canonical_source_class(evidence)
            if source_class:
                authority[_source_key(evidence)].add(source_class)

        projected_evidence: list[dict[str, Any]] = []
        for evidence_raw in candidate.get("evidence_sources", []) or []:
            if not isinstance(evidence_raw, Mapping):
                continue
            evidence = dict(evidence_raw)
            classes = authority.get(_source_key(evidence), set())
            # Fail closed on absent or conflicting producer authority.
            evidence["source_class"] = next(iter(classes)) if len(classes) == 1 else None
            projected_evidence.append(evidence)
        candidate["evidence_sources"] = projected_evidence
        projected_candidates.append(candidate)

    result = dict(bucket)
    result["schema_version"] = "1.0"
    result["strategy_id"] = "SWING-001"
    result["candidates"] = projected_candidates
    return result
