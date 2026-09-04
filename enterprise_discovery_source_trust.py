"""Governed source-trust profile validation for Enterprise discovery."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

SOURCE_TRUST_POLICY = "FAIL_CLOSED_CONTINUOUS_SOURCE_DISCOVERY_NO_AUTO_ACTIVATION"
ALLOWED_TIERS = {
    "TIER_1_PRIMARY_OFFICIAL",
    "TIER_2_PROFESSIONAL_NEWS",
    "TIER_3_REVIEWED_SPECIALIST",
    "TIER_4_DISCOVERY_ONLY",
}


def load_source_trust_profile(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("source trust profile must be a JSON object")
    if payload.get("policy") != SOURCE_TRUST_POLICY:
        raise ValueError("unsupported source trust policy")
    if payload.get("auto_activate_new_sources") is not False:
        raise ValueError("new sources must never auto-activate")
    return payload


def evaluate_source_candidate(candidate: Mapping[str, Any], profile: Mapping[str, Any]) -> dict[str, Any]:
    """Return a fail-closed admission decision for a newly discovered source."""
    name = str(candidate.get("name") or "").strip()
    tier = str(candidate.get("tier") or "").strip()
    url = str(candidate.get("url") or "").strip()
    publisher = str(candidate.get("publisher") or name).strip()
    provenance = str(candidate.get("provenance") or "").strip()
    source_class = str(candidate.get("source_class") or "").strip()
    published_timestamp_supported = candidate.get("published_timestamp_supported") is True
    reasons: list[str] = []

    if not name:
        reasons.append("MISSING_NAME")
    if tier not in ALLOWED_TIERS:
        reasons.append("INVALID_TIER")
    if not url.lower().startswith("https://"):
        reasons.append("HTTPS_REQUIRED")
    if not publisher:
        reasons.append("IDENTIFIABLE_PUBLISHER_REQUIRED")
    if not provenance:
        reasons.append("STABLE_PROVENANCE_REQUIRED")
    if not source_class:
        reasons.append("SOURCE_CLASS_REQUIRED")
    if not published_timestamp_supported:
        reasons.append("PUBLISHED_TIMESTAMP_REQUIRED")
    if candidate.get("repost_only") is True:
        reasons.append("REPOST_ONLY_REJECTED")
    if candidate.get("anonymous_social") is True:
        reasons.append("ANONYMOUS_SOCIAL_REJECTED")

    return {
        "name": name or None,
        "tier": tier or None,
        "status": "REVIEW_REQUIRED" if not reasons else "REJECTED",
        "eligible_for_activation_review": not reasons,
        "auto_activate": False,
        "reasons": reasons,
    }
