"""Governed catalyst classification for Enterprise discovery evidence.

This layer never infers a catalyst from headline or free text. It accepts only
explicit catalyst metadata attached to an authoritative or reviewed evidence item,
normalizes that metadata to the AI CIO catalyst taxonomy, and strips unsupported
claims before Theme Strength consumes the evidence.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from enterprise_discovery_theme_strength import CATALYST_EVIDENCE_FLAGS, CATALYST_FAMILIES

CATALYST_CLASSIFICATION_VERSION = "1.1"
CATALYST_EVIDENCE_POLICY = "EXPLICIT_REVIEWED_CLASSIFICATION_ONLY"
CATALYST_EVENT_POLICY = "CONFIRMED_FAVORABLE_COMPANY_SPECIFIC_EXPLICIT_EVENTS_ONLY"

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


def _valid_event_date(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.fromisoformat(f"{text[:10]}T00:00:00+00:00")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_catalyst_events(
    item: Mapping[str, Any], *, trusted: bool, identity: str
) -> tuple[list[dict[str, Any]], set[str], list[str]]:
    """Validate explicit event metadata and return deduplicated scoring events.

    No free-text classification occurs here. An event can contribute a catalyst
    family only when the source itself is eligible and the event explicitly says it
    is CONFIRMED, favorable, company-specific, dated, and identified by event_id.
    Freshness expiration remains governed by the discovery evidence lifecycle; this
    validator deliberately does not invent a second lookback window.
    """
    raw_events = item.get("catalyst_events")
    if raw_events is None:
        return [], set(), []
    if not isinstance(raw_events, list):
        return [], set(), [f"INVALID_CATALYST_EVENTS:{identity}:NOT_LIST"]

    accepted: list[dict[str, Any]] = []
    families: set[str] = set()
    warnings: list[str] = []
    seen_ids: set[str] = set()

    for index, raw_event in enumerate(raw_events):
        event_identity = f"{identity}:{index}"
        if not isinstance(raw_event, Mapping):
            warnings.append(f"INVALID_CATALYST_EVENT:{event_identity}:NOT_MAPPING")
            continue

        event_id = _text(raw_event.get("event_id"))
        family = _text(raw_event.get("family")).lower()
        status = _text(raw_event.get("status")).upper()
        event_date = _valid_event_date(raw_event.get("event_date"))
        reason = _text(raw_event.get("reason"))
        favorable = raw_event.get("favorable") is True
        company_specific = raw_event.get("company_specific") is True

        if not event_id:
            warnings.append(f"INVALID_CATALYST_EVENT:{event_identity}:MISSING_EVENT_ID")
            continue
        if family not in CATALYST_FAMILIES:
            warnings.append(f"UNKNOWN_CATALYST_FAMILY:{event_id}:{family or 'MISSING'}")
            continue
        if event_id in seen_ids:
            warnings.append(f"DUPLICATE_CATALYST_EVENT:{event_id}")
            continue
        seen_ids.add(event_id)
        if not trusted:
            warnings.append(f"UNREVIEWED_CATALYST_EVENT_REJECTED:{event_id}")
            continue
        if status != "CONFIRMED":
            warnings.append(f"NONCONFIRMED_CATALYST_EVENT_REJECTED:{event_id}:{status or 'MISSING'}")
            continue
        if not favorable:
            warnings.append(f"NONFAVORABLE_CATALYST_EVENT_REJECTED:{event_id}")
            continue
        if not company_specific:
            warnings.append(f"NONCOMPANY_SPECIFIC_CATALYST_EVENT_REJECTED:{event_id}")
            continue
        if event_date is None:
            warnings.append(f"INVALID_CATALYST_EVENT:{event_id}:INVALID_EVENT_DATE")
            continue
        if not reason:
            warnings.append(f"INVALID_CATALYST_EVENT:{event_id}:MISSING_REASON")
            continue

        accepted_event = {
            "event_id": event_id,
            "family": family,
            "status": "CONFIRMED",
            "event_date": event_date,
            "reason": reason,
            "favorable": True,
            "company_specific": True,
            "source": _text(raw_event.get("source") or item.get("source")) or None,
            "source_url": _text(raw_event.get("source_url") or item.get("source_url") or item.get("url")) or None,
            "provenance": _text(raw_event.get("provenance") or item.get("authority") or item.get("source_class")) or None,
        }
        accepted.append(accepted_event)
        families.add(family)

    return accepted, families, warnings


def classify_evidence_item(item: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Normalize one evidence item and fail closed on unsupported catalyst claims."""
    normalized = dict(item)
    requested, unknown = _explicit_families(item)
    trusted = _source_is_authoritative_or_reviewed(item)
    identity = _text(item.get("story_id") or item.get("source_url") or item.get("source") or "UNKNOWN")
    events, event_families, event_warnings = _normalize_catalyst_events(
        item, trusted=trusted, identity=identity
    )

    # Existing explicit flags remain supported for backwards compatibility. New
    # structured events add families only after the stricter event validation above.
    accepted = (requested if trusted else set()) | event_families

    normalized["catalyst_events"] = events
    normalized["catalyst_families"] = sorted(accepted)
    for family, flag in CATALYST_EVIDENCE_FLAGS.items():
        normalized[flag] = family in accepted
    for family, flag in LEGACY_FLAGS.items():
        normalized[flag] = family in accepted

    normalized["catalyst_classification"] = {
        "version": CATALYST_CLASSIFICATION_VERSION,
        "policy": CATALYST_EVIDENCE_POLICY,
        "event_policy": CATALYST_EVENT_POLICY,
        "source_eligible": trusted,
        "explicit_family_count": len(requested),
        "accepted_family_count": len(accepted),
        "accepted_families": sorted(accepted),
        "accepted_event_count": len(events),
        "accepted_event_ids": [event["event_id"] for event in events],
    }

    warnings: list[str] = list(event_warnings)
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
    report["catalyst_event_policy"] = CATALYST_EVENT_POLICY
    report["warnings"] = list(dict.fromkeys(str(value) for value in warnings))
    return report