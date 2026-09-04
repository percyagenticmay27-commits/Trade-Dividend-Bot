"""Structured SEC filing metadata extraction for Enterprise discovery.

This module preserves authoritative filing metadata from SEC submissions JSON.
It does not infer catalyst families, favorability, or company-specific event
semantics from a filing form or item code.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

SEC_FILING_METADATA_VERSION = "1.0"
SEC_FILING_METADATA_POLICY = "PRESERVE_STRUCTURED_SEC_METADATA_NO_EVENT_INFERENCE"

ALLOWED_FORMS = {"8-K", "10-K", "10-Q", "20-F", "40-F", "6-K", "S-1", "S-3", "DEF 14A"}


def _as_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _normalize_item_codes(value: Any) -> list[str]:
    """Preserve SEC-supplied item codes without assigning catalyst meaning."""
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [part.strip() for part in value.replace(";", ",").split(",")]
    elif isinstance(value, (list, tuple)):
        candidates = [str(part).strip() for part in value]
    else:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        result.append(candidate)
    return result


def extract_recent_sec_filing_metadata(
    payload: Mapping[str, Any], *, cutoff: date
) -> list[dict[str, Any]]:
    """Extract aligned structured metadata from SEC submissions recent filings.

    SEC ``items`` values are retained as audit metadata only. No item code or form
    is converted here into a reviewed catalyst event or scoring family.
    """
    recent = ((payload.get("filings") or {}).get("recent") or {}) if isinstance(payload, Mapping) else {}
    if not isinstance(recent, Mapping):
        return []
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    accessions = recent.get("accessionNumber") or []
    primary_docs = recent.get("primaryDocument") or []
    items = recent.get("items") or []
    if not isinstance(forms, list):
        return []

    rows: list[dict[str, Any]] = []
    for index, raw_form in enumerate(forms):
        form = str(raw_form or "").strip().upper()
        filed = _as_date(dates[index] if isinstance(dates, list) and index < len(dates) else None)
        if form not in ALLOWED_FORMS or filed is None or filed < cutoff:
            continue
        accession = str(accessions[index] if isinstance(accessions, list) and index < len(accessions) else "").strip()
        primary_document = str(primary_docs[index] if isinstance(primary_docs, list) and index < len(primary_docs) else "").strip()
        raw_items = items[index] if isinstance(items, list) and index < len(items) else None
        rows.append({
            "form": form,
            "filing_date": filed.isoformat(),
            "accession_number": accession or None,
            "primary_document": primary_document or None,
            "sec_item_codes": _normalize_item_codes(raw_items),
            "sec_filing_metadata": {
                "version": SEC_FILING_METADATA_VERSION,
                "policy": SEC_FILING_METADATA_POLICY,
                "item_codes_preserved": bool(_normalize_item_codes(raw_items)),
                "catalyst_inference_used": False,
            },
        })
    return rows
