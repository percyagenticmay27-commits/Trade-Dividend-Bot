"""Governed catalyst classification for Enterprise discovery evidence.

This layer never infers a catalyst from headline or free text. It accepts only
explicit catalyst metadata attached to an authoritative or reviewed evidence item,
normalizes that metadata to the AI CIO catalyst taxonomy, and strips unsupported
claims before Theme Strength consumes the evidence.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from enterprise_discovery_theme_strength import CATALYST_EVIDENCE_FLAGS, CATALYST_FAMILIES

CATALYST_CLASSIFICATION_VERSION = "1.0"
CATALYST_EVIDENCE_POLICY = "EXPLICIT_REVIEWED_CLASSIFICATION_ONLY"

LEGACY_FLAGS = {
    "earnings_fundamental_growth": "earnings_growth_related",
    "analyst_institutional_revisions": "analyst_upgrade_related",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _source_is_authoritative_or_reviewed(item: Mapping[str, Any]) -> bool:
    source_class = _text(item.get("source_class")).upper()
    authority = _text(item.get("authority")).upper()
    reviewed = item.get("credibility_reviewed") is True

    # Primary-company/regulatory records are authoritative by source class. Other
    # classes require explicit review/authority metadata; historical creator rows
    # without those fields are therefore unable to create a new catalyst claim.
    if source_class in {"PRIMARY_COMPANY", "PRIMARY_GOVERNMENT", "REGULATORY"}:
        return True
    if source_class == "PROFESSIONAL_MEDIA":
        return reviewed or authority == "PROFESSIONAL_MEDIA"
    if source_class == "CREATOR_INTELLIGENCE":
        return reviewed and authority in {"REVIEWED_CREATOR", "PROFESSIONAL_MEDIA"}
    if source_class == "INSTITUTIONAL_RESEARCH":
        return reviewed or authority == "INSTITUTIONAL_RESEARCH"
    return False


def _explicit_families(item: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    """Return approved and unknown explicit family names without text inference."""
    approved: set[str] = set()
    unknown: set[str] = set()
    raw = item.get("catalyst_families")
    if isinstance(raw, (list, tuple, set)):
        for value in raw:
            family = _text(value).lower()
            if not family:
                continue
            if family in CATALYST_FAMILIES:
                approved.add(family)
            else:
                unknown.add(family)

    for family, flag in {**LEGACY_FLAGS, **CATALYST_EVIDENCE_FLAGS}.items():
        if item.get(flag) is True:
            approved.add(family)
    return approved, unknown


def classify_evidence_item(item: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Normalize one evidence item and fail closed on unsupported catalyst claims."""
    normalized = dict(item)
    requested, unknown = _explicit_families(item)
    trusted = _source_is_authoritative_or_reviewed(item)
    accepted = requested if trusted else set()

    # Canonicalize every source-derived catalyst flag. This intentionally clears
    # explicit but unreviewed claims so downstream scoring cannot count them.
    normalized["catalyst_families"] = sorted(accepted)
    for family, flag in CATALYST_EVIDENCE_FLAGS.items():
        normalized[flag] = family in accepted
    for family, flag in LEGACY_FLAGS.items():
        normalized[flag] = family in accepted

    normalized["catalyst_classification"] = {
        "version": CATALYST_CLASSIFICATION_VERSION,
        "policy": CATALYST_EVIDENCE_POLICY,
        "source_eligible": trusted,
        "explicit_family_count": len(requested),
        "accepted_family_count": len(accepted),
        "accepted_families": sorted(accepted),
    }

    warnings: list[str] = []
    identity = _text(item.get("story_id") or item.get("source_url") or item.get("source") or "UNKNOWN")
    if unknown:
        warnings.append(f"UNKNOWN_CATALYST_FAMILY:{identity}:{','.join(sorted(unknown))}")
    if requested and not trusted:
        warnings.append(f"UNREVIEWED_CATALYST_EVIDENCE_REJECTED:{identity}")
    return normalized, warnings


def attach_candidate_catalyst_classification(report: dict[str, Any]) -> dict[str, Any]:
    """Classify all discovery source evidence without changing lifecycle state."""
    warnings = report.setdefault("warnings", [])
    if not isinstance(warnings, list):
        warnings = []
        report["warnings"] = warnings

    for row in report.get("observations", []):
        if not isinstance(row, dict):
            continue
        key = "source_evidence" if isinstance(row.get("source_evidence"), list) else "evidence_sources"
        evidence = row.get(key)
        if not isinstance(evidence, list):
            continue
        classified: list[dict[str, Any]] = []
        for item in evidence:
            if not isinstance(item, Mapping):
                continue
            normalized, item_warnings = classify_evidence_item(item)
            classified.append(normalized)
            warnings.extend(item_warnings)
        row[key] = classified

    report["catalyst_classification_version"] = CATALYST_CLASSIFICATION_VERSION
    report["catalyst_evidence_policy"] = CATALYST_EVIDENCE_POLICY
    report["warnings"] = list(dict.fromkeys(str(value) for value in warnings))
    return report
