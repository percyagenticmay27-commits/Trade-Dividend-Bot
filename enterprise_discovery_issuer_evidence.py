"""Collect verified issuer-primary research pages as non-scoring symbol evidence."""
from __future__ import annotations

import re
import urllib.request
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlparse

ISSUER_EVIDENCE_POLICY = "VERIFIED_ISSUER_PRIMARY_EVIDENCE_NONSCORING_REVIEW_REQUIRED"
ISSUER_EVIDENCE_VERSION = "1.0"


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and data.strip():
            self.title_parts.append(data.strip())


def _default_get(url: str, user_agent: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310: verified HTTPS domains only
        return response.read()


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().rstrip(".")


def _page_title(payload: bytes) -> str | None:
    text = payload.decode("utf-8", errors="replace")
    parser = _PageParser()
    parser.feed(text)
    title = re.sub(r"\s+", " ", " ".join(parser.title_parts)).strip()
    return title or None


def collect_issuer_primary_evidence(
    profiles: Iterable[Mapping[str, Any]],
    *,
    active_symbols: Iterable[str],
    as_of: str | datetime,
    user_agent: str,
    get_bytes: Callable[[str, str], bytes] = _default_get,
) -> dict[str, Any]:
    now = datetime.fromisoformat(str(as_of).replace("Z", "+00:00")) if not isinstance(as_of, datetime) else as_of
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    targets = {str(symbol).strip().upper() for symbol in active_symbols if str(symbol).strip()}
    evidence: list[dict[str, Any]] = []
    warnings: list[str] = []

    for profile in profiles:
        symbol = str(profile.get("symbol") or "").strip().upper()
        if symbol not in targets:
            continue
        if profile.get("tier") != "TIER_1_PRIMARY_OFFICIAL" or profile.get("status") != "VERIFIED_ACTIVE":
            warnings.append(f"ISSUER_PROFILE_REJECTED:{symbol or 'UNKNOWN'}:INVALID_TRUST_STATE")
            continue
        if profile.get("scoring_eligible") is not False:
            warnings.append(f"ISSUER_PROFILE_REJECTED:{symbol}:SCORING_PROFILE_FORBIDDEN")
            continue
        domains = {str(value).lower().strip() for value in profile.get("verified_domains", []) if str(value).strip()}
        for page in profile.get("research_pages", []):
            if not isinstance(page, Mapping):
                warnings.append(f"ISSUER_PAGE_REJECTED:{symbol}:INVALID_PAGE")
                continue
            url = str(page.get("url") or "").strip()
            role = str(page.get("role") or "").strip()
            if not url.startswith("https://") or _host(url) not in domains:
                warnings.append(f"ISSUER_PAGE_REJECTED:{symbol}:{role or 'UNKNOWN'}:UNVERIFIED_URL")
                continue
            try:
                payload = get_bytes(url, user_agent)
                evidence.append({
                    "underlying_symbol": symbol,
                    "issuer_name": str(profile.get("issuer_name") or "").strip() or None,
                    "source": f"{symbol} Official Issuer Research",
                    "source_class": "PRIMARY_COMPANY",
                    "tier": "TIER_1_PRIMARY_OFFICIAL",
                    "role": role or None,
                    "source_url": url,
                    "page_title": _page_title(payload),
                    "collected_at": now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "symbol_linkage": "VERIFIED_PROFILE",
                    "review_required": True,
                    "scoring_eligible": False,
                    "catalyst_inference_used": False,
                    "reviewed_catalyst_events": [],
                    "catalyst_events": [],
                })
            except (OSError, UnicodeError, ValueError) as exc:
                warnings.append(f"ISSUER_PAGE_FAILED:{symbol}:{role or 'UNKNOWN'}:{exc}")

    return {
        "version": ISSUER_EVIDENCE_VERSION,
        "policy": ISSUER_EVIDENCE_POLICY,
        "generated_at": now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "evidence": evidence,
        "evidence_count": len(evidence),
        "symbols": sorted({row["underlying_symbol"] for row in evidence}),
        "warnings": warnings,
        "scoring_event_count": 0,
    }


def attach_issuer_primary_evidence(report: Mapping[str, Any], issuer_report: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(report))
    result["issuer_primary_evidence"] = deepcopy(dict(issuer_report))
    return result
