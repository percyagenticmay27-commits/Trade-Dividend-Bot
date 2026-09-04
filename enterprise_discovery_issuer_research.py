"""Governed issuer-primary research profiles.

Profiles identify verified first-party research locations for a symbol. Merely being
an issuer publication never makes evidence favorable or scoring eligible.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

ISSUER_RESEARCH_POLICY = "VERIFIED_ISSUER_PRIMARY_SOURCES_NONSCORING_UNTIL_EXPLICIT_REVIEW"
ISSUER_RESEARCH_VERSION = "1.0"


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().rstrip(".")


def validate_issuer_profile(profile: Mapping[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    symbol = str(profile.get("symbol") or "").strip().upper()
    if not symbol:
        errors.append("MISSING_SYMBOL")
    if profile.get("tier") != "TIER_1_PRIMARY_OFFICIAL":
        errors.append("INVALID_TIER")
    if profile.get("status") != "VERIFIED_ACTIVE":
        errors.append("PROFILE_NOT_ACTIVE")
    domains = {str(value).lower().strip() for value in profile.get("verified_domains", []) if str(value).strip()}
    if not domains:
        errors.append("MISSING_VERIFIED_DOMAINS")
    pages = profile.get("research_pages")
    if not isinstance(pages, list) or not pages:
        errors.append("MISSING_RESEARCH_PAGES")
    else:
        for page in pages:
            if not isinstance(page, Mapping):
                errors.append("INVALID_RESEARCH_PAGE")
                continue
            url = str(page.get("url") or "").strip()
            host = _host(url)
            if not url.startswith("https://"):
                errors.append(f"HTTPS_REQUIRED:{url}")
            if host not in domains:
                errors.append(f"UNVERIFIED_DOMAIN:{host}")
    if profile.get("scoring_eligible") is not False:
        errors.append("ISSUER_PROFILE_MUST_BE_NONSCORING")
    return not errors, errors


def build_issuer_research_registry(profiles: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    accepted: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    for profile in profiles:
        valid, errors = validate_issuer_profile(profile)
        symbol = str(profile.get("symbol") or "").strip().upper()
        if not valid:
            rejected.append({"symbol": symbol or None, "errors": errors})
            continue
        accepted[symbol] = deepcopy(dict(profile))
    return {
        "version": ISSUER_RESEARCH_VERSION,
        "policy": ISSUER_RESEARCH_POLICY,
        "profiles": accepted,
        "profile_count": len(accepted),
        "rejected_profiles": rejected,
        "scoring_event_count": 0,
    }


def attach_issuer_research_registry(report: Mapping[str, Any], registry: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(report))
    result["issuer_research_registry"] = deepcopy(dict(registry))
    return result
