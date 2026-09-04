"""Fail-closed structured catalyst extraction for Enterprise discovery.

This layer converts only explicit, reviewed structured source metadata into
catalyst_events. It deliberately does not inspect headlines, descriptions, or
other free text to infer catalyst families.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping

CATALYST_EXTRACTION_VERSION = "1.0"
CATALYST_EXTRACTION_POLICY = "STRUCTURED_METADATA_ONLY_NO_FREE_TEXT_INFERENCE"

CATALYST_FAMILIES = (
    "earnings_fundamental_growth",
    "analyst_institutional_revisions",
    "guidance_outlook",
    "product_innovation",
    "contracts_customer_wins",
    "capex_infrastructure_demand",
    "regulatory_government",
    "ma_strategic_activity",
    "sector_industry_tailwind",
    "corporate_capital_catalyst",
)

# Provider topics are retained as structured audit metadata only. A broad topic
# does not establish that a company-specific event is confirmed and favorable.
PROVIDER_TOPIC_FIELDS = ("topics", "provider_topics", "categories", "provider_categories")


def _event_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.combine(date.fromisoformat(text[:10]), datetime.min.time())
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _structured_topics(item: Mapping[str, Any]) -> list[Any]:
    values: list[Any] = []
    for field in PROVIDER_TOPIC_FIELDS:
        raw = item.get(field)
        if isinstance(raw, list):
            values.extend(deepcopy(raw))
    return values


def _explicit_reviewed_events(item: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Accept only explicitly reviewed source-event metadata.

    Source adapters may attach ``reviewed_catalyst_events`` after a human or
    authoritative structured-source review. Merely having a form, topic, title,
    sentiment label, or category never creates a confirmed event here.
    """
    raw_events = item.get("reviewed_catalyst_events")
    if raw_events is None:
        return [], []
    identity = str(item.get("story_id") or item.get("source_url") or item.get("source") or "UNKNOWN")
    if not isinstance(raw_events, list):
        return [], [f"INVALID_REVIEWED_CATALYST_EVENTS:{identity}:NOT_LIST"]
    source_class = str(item.get("source_class") or "").upper()
    authority = str(item.get("authority") or "").upper()
    reviewed = bool(item.get("credibility_reviewed", False))
    trusted = source_class in {"PRIMARY_COMPANY", "GOVERNMENT_REGULATORY"} or (
        reviewed and authority in {"PROFESSIONAL_MEDIA", "INSTITUTIONAL_RESEARCH", "REVIEWED_CREATOR"}
    )
    if not trusted:
        return [], [f"UNTRUSTED_REVIEWED_CATALYST_EVENTS:{identity}"]

    accepted: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for raw in raw_events:
        if not isinstance(raw, Mapping):
            warnings.append(f"INVALID_REVIEWED_CATALYST_EVENT:{identity}:NOT_OBJECT")
            continue
        event_id = str(raw.get("event_id") or "").strip()
        family = str(raw.get("family") or "").strip()
        event_date = _event_date(raw.get("event_date") or item.get("mentioned_on"))
        reason = str(raw.get("reason") or "").strip()
        status = str(raw.get("status") or "").upper()
        if not event_id or family not in CATALYST_FAMILIES or not event_date or not reason:
            warnings.append(f"INVALID_REVIEWED_CATALYST_EVENT:{identity}:{event_id or 'MISSING_ID'}")
            continue
        if event_id in seen:
            warnings.append(f"DUPLICATE_REVIEWED_CATALYST_EVENT:{identity}:{event_id}")
            continue
        seen.add(event_id)
        # Only the scoring contract's strongest semantics cross this extraction
        # boundary. DEVELOPING/neutral/adverse records remain audit-only upstream.
        if status != "CONFIRMED" or raw.get("favorable") is not True or raw.get("company_specific") is not True:
            warnings.append(f"NONSCORING_REVIEWED_CATALYST_EVENT:{identity}:{event_id}")
            continue
        accepted.append({
            "event_id": event_id,
            "family": family,
            "status": "CONFIRMED",
            "event_date": event_date,
            "reason": reason,
            "favorable": True,
            "company_specific": True,
            "source": str(item.get("source") or "").strip() or None,
            "source_url": str(item.get("source_url") or "").strip() or None,
            "provenance": deepcopy(raw.get("provenance")) if raw.get("provenance") is not None else {
                "story_id": item.get("story_id"),
                "form": item.get("form"),
                "accession_number": item.get("accession_number"),
                "platform": item.get("platform"),
            },
        })
    return accepted, warnings


def enrich_evidence_item(item: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Preserve structured provider metadata and attach only reviewed events."""
    enriched = deepcopy(dict(item))
    topics = _structured_topics(item)
    if topics:
        enriched["structured_provider_topics"] = topics
    events, warnings = _explicit_reviewed_events(item)
    if events:
        enriched["catalyst_events"] = events
    enriched["catalyst_extraction"] = {
        "version": CATALYST_EXTRACTION_VERSION,
        "policy": CATALYST_EXTRACTION_POLICY,
        "free_text_inference_used": False,
        "structured_provider_topic_count": len(topics),
        "accepted_event_count": len(events),
    }
    return enriched, warnings


def enrich_observations_with_catalyst_events(report: Mapping[str, Any]) -> dict[str, Any]:
    """Apply extraction to observation source evidence without changing nominations."""
    enriched = deepcopy(dict(report))
    warnings = list(enriched.get("warnings") or [])
    for row in enriched.get("observations", []) if isinstance(enriched.get("observations"), list) else []:
        if not isinstance(row, dict):
            continue
        evidence_rows = row.get("source_evidence")
        if not isinstance(evidence_rows, list):
            continue
        normalized = []
        for evidence in evidence_rows:
            if not isinstance(evidence, Mapping):
                continue
            item, item_warnings = enrich_evidence_item(evidence)
            normalized.append(item)
            warnings.extend(item_warnings)
        row["source_evidence"] = normalized
    enriched["warnings"] = warnings
    enriched["catalyst_extraction_version"] = CATALYST_EXTRACTION_VERSION
    enriched["catalyst_extraction_policy"] = CATALYST_EXTRACTION_POLICY
    return enriched
