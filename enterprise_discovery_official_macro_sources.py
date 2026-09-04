"""Collect vetted Tier-1 official macro/regulatory feeds as non-scoring evidence.

This layer intentionally keeps broad macro/regulatory evidence separate from symbol
observations. Nothing collected here may affect Theme Strength, nomination, or a
catalyst until a later governed layer establishes explicit symbol/theme linkage.
"""
from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Iterable, Mapping

OFFICIAL_MACRO_POLICY = "TIER_1_OFFICIAL_MACRO_EVIDENCE_NONSCORING_UNTIL_EXPLICIT_SYMBOL_LINKAGE"
OFFICIAL_MACRO_VERSION = "1.0"


def _default_get(url: str, user_agent: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310: vetted HTTPS config only
        return response.read()


def _as_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        try:
            if re.fullmatch(r"\d{8}(?:T\d{4,6})?", text):
                return datetime.strptime(text[:8], "%Y%m%d").date()
            return parsedate_to_datetime(text).date()
        except (TypeError, ValueError, OverflowError):
            return None


def _entries(payload: bytes) -> list[ET.Element]:
    root = ET.fromstring(payload)
    return list(root.findall(".//item")) + list(root.findall(".//{*}entry"))


def collect_official_macro_evidence(
    sources: Iterable[Mapping[str, Any]],
    *,
    as_of: str | datetime,
    user_agent: str,
    get_bytes: Callable[[str, str], bytes] = _default_get,
    lookback_days: int = 7,
) -> dict[str, Any]:
    now = datetime.fromisoformat(str(as_of).replace("Z", "+00:00")) if not isinstance(as_of, datetime) else as_of
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now.date() - timedelta(days=max(1, int(lookback_days)))
    evidence: list[dict[str, Any]] = []
    warnings: list[str] = []

    for source in sources:
        name = str(source.get("source_name") or "Official source").strip()
        url = str(source.get("url") or "").strip()
        tier = str(source.get("tier") or "").strip()
        source_class = str(source.get("source_class") or "").strip()
        if tier != "TIER_1_PRIMARY_OFFICIAL" or source_class != "GOVERNMENT_PRIMARY":
            warnings.append(f"OFFICIAL_MACRO_SOURCE_REJECTED:{name}:INVALID_TRUST_CLASS")
            continue
        if not url.lower().startswith("https://"):
            warnings.append(f"OFFICIAL_MACRO_SOURCE_REJECTED:{name}:HTTPS_REQUIRED")
            continue
        try:
            payload = get_bytes(url, user_agent)
            for entry in _entries(payload):
                title = (entry.findtext("title") or entry.findtext("{*}title") or "").strip()
                published_text = (
                    entry.findtext("pubDate") or entry.findtext("published") or entry.findtext("updated")
                    or entry.findtext("{*}published") or entry.findtext("{*}updated")
                )
                published = _as_date(published_text)
                if not title or published is None or published < cutoff:
                    continue
                link = entry.findtext("link") or ""
                if not link:
                    link_element = entry.find("{*}link")
                    link = str(link_element.get("href") or "") if link_element is not None else ""
                evidence.append({
                    "source": name,
                    "source_class": source_class,
                    "tier": tier,
                    "published_on": published.isoformat(),
                    "title": title,
                    "source_url": link or None,
                    "roles": list(source.get("roles") or []),
                    "scoring_eligible": False,
                    "symbol_linkage": None,
                    "catalyst_inference_used": False,
                })
        except (OSError, UnicodeError, ValueError, ET.ParseError) as exc:
            warnings.append(f"OFFICIAL_MACRO_SOURCE_FAILED:{name}:{exc}")

    return {
        "version": OFFICIAL_MACRO_VERSION,
        "policy": OFFICIAL_MACRO_POLICY,
        "generated_at": now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "evidence": evidence,
        "warnings": warnings,
        "evidence_count": len(evidence),
        "scoring_event_count": 0,
    }


def attach_official_macro_evidence(report: Mapping[str, Any], macro_report: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(report))
    result["official_macro_evidence"] = deepcopy(dict(macro_report))
    return result
