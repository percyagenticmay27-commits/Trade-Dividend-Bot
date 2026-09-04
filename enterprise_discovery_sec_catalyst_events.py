"""Fail-closed SEC catalyst-event production from explicit reviewed filing metadata.

Generic filing form types are evidence, not favorable catalyst events.  This
module only converts explicit, structured, reviewed SEC event metadata into the
reviewed_catalyst_events contract consumed by the governed extractor.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

SEC_CATALYST_EVENT_POLICY = "EXPLICIT_REVIEWED_SEC_EVENT_METADATA_ONLY"
SEC_CATALYST_EVENT_VERSION = "1.0"

CATALYST_FAMILIES = {
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
}


def attach_sec_reviewed_catalyst_events(item: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Attach reviewed events only when explicit SEC event metadata is supplied.

    ``sec_reviewed_events`` is deliberately separate from form/title fields.  A
    10-Q, 10-K, 6-K or 8-K can support discovery evidence but cannot establish
    favorable event semantics merely from its form code.
    """
    result = deepcopy(dict(item))
    if str(result.get("source_class") or "").upper() != "PRIMARY_COMPANY":
        return result, []

    raw_events = result.get("sec_reviewed_events")
    if raw_events is None:
        result["sec_catalyst_event_production"] = {
            "version": SEC_CATALYST_EVENT_VERSION,
            "policy": SEC_CATALYST_EVENT_POLICY,
            "accepted_event_count": 0,
        }
        return result, []

    identity = str(result.get("accession_number") or result.get("story_id") or "UNKNOWN")
    if not isinstance(raw_events, list):
        return result, [f"INVALID_SEC_REVIEWED_EVENTS:{identity}:NOT_LIST"]

    accepted: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for raw in raw_events:
        if not isinstance(raw, Mapping):
            warnings.append(f"INVALID_SEC_REVIEWED_EVENT:{identity}:NOT_OBJECT")
            continue
        event_id = str(raw.get("event_id") or "").strip()
        family = str(raw.get("family") or "").strip()
        status = str(raw.get("status") or "").upper()
        reason = str(raw.get("reason") or "").strip()
        event_date = str(raw.get("event_date") or result.get("mentioned_on") or "").strip()
        if not event_id or family not in CATALYST_FAMILIES or not reason or not event_date:
            warnings.append(f"INVALID_SEC_REVIEWED_EVENT:{identity}:{event_id or 'MISSING_ID'}")
            continue
        if event_id in seen:
            warnings.append(f"DUPLICATE_SEC_REVIEWED_EVENT:{identity}:{event_id}")
            continue
        seen.add(event_id)
        if status != "CONFIRMED" or raw.get("favorable") is not True or raw.get("company_specific") is not True:
            warnings.append(f"NONSCORING_SEC_REVIEWED_EVENT:{identity}:{event_id}")
            continue
        accepted.append({
            "event_id": event_id,
            "family": family,
            "status": "CONFIRMED",
            "event_date": event_date,
            "reason": reason,
            "favorable": True,
            "company_specific": True,
            "provenance": {
                "form": result.get("form"),
                "accession_number": result.get("accession_number"),
                "primary_document": result.get("primary_document"),
                "story_id": result.get("story_id"),
                **(deepcopy(raw.get("provenance")) if isinstance(raw.get("provenance"), Mapping) else {}),
            },
        })

    if accepted:
        result["reviewed_catalyst_events"] = accepted
    result["sec_catalyst_event_production"] = {
        "version": SEC_CATALYST_EVENT_VERSION,
        "policy": SEC_CATALYST_EVENT_POLICY,
        "accepted_event_count": len(accepted),
    }
    return result, warnings


def enrich_report_with_sec_reviewed_events(report: Mapping[str, Any]) -> dict[str, Any]:
    enriched = deepcopy(dict(report))
    warnings = list(enriched.get("warnings") or [])
    rows = enriched.get("observations")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("source_evidence"), list):
                continue
            output = []
            for item in row["source_evidence"]:
                if not isinstance(item, Mapping):
                    continue
                produced, item_warnings = attach_sec_reviewed_catalyst_events(item)
                output.append(produced)
                warnings.extend(item_warnings)
            row["source_evidence"] = output
    enriched["warnings"] = warnings
    enriched["sec_catalyst_event_version"] = SEC_CATALYST_EVENT_VERSION
    enriched["sec_catalyst_event_policy"] = SEC_CATALYST_EVENT_POLICY
    return enriched
