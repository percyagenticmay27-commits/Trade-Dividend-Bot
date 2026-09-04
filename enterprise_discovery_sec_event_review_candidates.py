"""Non-scoring SEC event-review candidates for Enterprise discovery.

SEC filing item codes identify subjects that may deserve research. They never prove
that an event is favorable, company-specific, or eligible for Theme Strength. This
layer creates REVIEW_REQUIRED audit records only; the existing explicit
``sec_reviewed_events`` contract remains the sole path into scored catalyst events.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

SEC_EVENT_REVIEW_POLICY = "SEC_ITEM_CODES_CREATE_REVIEW_CANDIDATES_ONLY_NO_SCORING"
SEC_EVENT_REVIEW_VERSION = "1.0"

# These are research routing hints, not catalyst classifications. 9.01 is exhibit
# metadata and intentionally does not create an independent review candidate.
ITEM_RESEARCH_HINTS: dict[str, tuple[str, ...]] = {
    "1.01": ("contracts_customer_wins", "corporate_capital_catalyst", "ma_strategic_activity"),
    "1.02": ("contracts_customer_wins", "corporate_capital_catalyst", "ma_strategic_activity"),
    "2.01": ("ma_strategic_activity", "corporate_capital_catalyst"),
    "2.02": ("earnings_fundamental_growth", "guidance_outlook"),
    "2.03": ("corporate_capital_catalyst",),
    "2.04": ("corporate_capital_catalyst",),
    "2.05": ("corporate_capital_catalyst",),
    "2.06": ("corporate_capital_catalyst",),
    "5.02": ("corporate_capital_catalyst",),
    "7.01": ("guidance_outlook", "product_innovation", "contracts_customer_wins"),
    "8.01": ("product_innovation", "contracts_customer_wins", "regulatory_government", "corporate_capital_catalyst"),
}


def attach_sec_event_review_candidates(item: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(item))
    if str(result.get("source_class") or "").upper() != "PRIMARY_COMPANY":
        return result
    codes = [str(value or "").strip() for value in result.get("sec_item_codes", []) if str(value or "").strip()]
    accession = str(result.get("accession_number") or "").strip()
    candidates: list[dict[str, Any]] = []
    for code in codes:
        if code == "9.01":
            continue
        hints = ITEM_RESEARCH_HINTS.get(code, ())
        candidates.append({
            "review_candidate_id": f"SEC_REVIEW:{accession or result.get('story_id') or 'UNKNOWN'}:{code}",
            "status": "REVIEW_REQUIRED",
            "sec_item_code": code,
            "possible_catalyst_families": list(hints),
            "possible_families_are_scoring": False,
            "favorable": None,
            "company_specific": None,
            "reason": "SEC item code identifies a filing subject for review; filing content must establish event semantics.",
            "provenance": {
                "form": result.get("form"),
                "filing_date": result.get("filing_date") or result.get("mentioned_on"),
                "accession_number": result.get("accession_number"),
                "primary_document": result.get("primary_document"),
                "story_id": result.get("story_id"),
                "source": result.get("source"),
                "source_url": result.get("source_url"),
            },
        })
    result["sec_event_review_candidates"] = candidates
    result["sec_event_review_candidate_metadata"] = {
        "version": SEC_EVENT_REVIEW_VERSION,
        "policy": SEC_EVENT_REVIEW_POLICY,
        "candidate_count": len(candidates),
        "scoring_event_count": 0,
        "item_9_01_supporting_metadata_only": "9.01" in codes,
    }
    return result


def enrich_report_with_sec_event_review_candidates(report: Mapping[str, Any]) -> dict[str, Any]:
    enriched = deepcopy(dict(report))
    candidate_count = 0
    rows = enriched.get("observations")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("source_evidence"), list):
                continue
            output = []
            for item in row["source_evidence"]:
                if not isinstance(item, Mapping):
                    continue
                reviewed = attach_sec_event_review_candidates(item)
                candidate_count += len(reviewed.get("sec_event_review_candidates") or [])
                output.append(reviewed)
            row["source_evidence"] = output
    enriched["sec_event_review_candidate_version"] = SEC_EVENT_REVIEW_VERSION
    enriched["sec_event_review_candidate_policy"] = SEC_EVENT_REVIEW_POLICY
    enriched["sec_event_review_candidate_count"] = candidate_count
    return enriched
