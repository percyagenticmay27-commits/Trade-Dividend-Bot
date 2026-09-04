"""Targeted SEC submissions enrichment for retained Enterprise discovery candidates.

Broad SEC daily-index discovery remains cheap and evidence-only. This module performs
bounded company-submissions lookups only for caller-approved symbols so structured
filing metadata such as 8-K item codes can be preserved without treating those codes
as catalyst conclusions.
"""
from __future__ import annotations

import json
import time
import urllib.request
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Mapping

from enterprise_discovery_sec_filing_metadata import extract_recent_sec_filing_metadata

SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
TARGETED_SEC_ENRICHMENT_POLICY = "ACTIVE_CANDIDATES_ONLY_STRUCTURED_METADATA_NO_CATALYST_INFERENCE"
TARGETED_SEC_ENRICHMENT_VERSION = "1.0"


def _default_get(url: str, user_agent: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310: fixed SEC HTTPS endpoints
        return response.read()


def _ticker_ciks(payload: Mapping[str, Any]) -> dict[str, str]:
    fields = payload.get("fields")
    data = payload.get("data")
    if not isinstance(fields, list) or not isinstance(data, list):
        return {}
    try:
        cik_index = fields.index("cik")
        ticker_index = fields.index("ticker")
    except ValueError:
        return {}
    result: dict[str, str] = {}
    for row in data:
        if not isinstance(row, list) or max(cik_index, ticker_index) >= len(row):
            continue
        ticker = str(row[ticker_index] or "").strip().upper()
        cik = str(row[cik_index] or "").strip()
        if ticker and cik.isdigit():
            result.setdefault(ticker, cik.zfill(10))
    return result


def _filing_evidence(filing: Mapping[str, Any]) -> dict[str, Any]:
    form = str(filing.get("form") or "").strip().upper()
    filed = str(filing.get("filing_date") or "").strip()
    accession = str(filing.get("accession_number") or "").strip()
    document = str(filing.get("primary_document") or "").strip()
    return {
        "source": "SEC EDGAR Targeted Submissions",
        "source_class": "PRIMARY_COMPANY",
        "producer": "U.S. Securities and Exchange Commission",
        "mentioned_on": filed,
        "story_id": f"SEC:{accession or document or filed}",
        "stance": "NEUTRAL",
        "themes": [],
        "earnings_growth_related": form in {"10-K", "10-Q", "20-F", "40-F", "6-K"},
        "analyst_upgrade_related": False,
        "form": form,
        "filing_date": filed,
        "accession_number": accession or None,
        "primary_document": document or None,
        "sec_item_codes": list(filing.get("sec_item_codes") or []),
        "sec_filing_metadata": dict(filing.get("sec_filing_metadata") or {}),
        "targeted_sec_enrichment": {
            "version": TARGETED_SEC_ENRICHMENT_VERSION,
            "policy": TARGETED_SEC_ENRICHMENT_POLICY,
            "catalyst_inference_used": False,
        },
    }


def enrich_active_candidates_with_sec_submissions(
    report: Mapping[str, Any],
    active_symbols: Iterable[str],
    *,
    as_of: str | datetime,
    user_agent: str,
    get_bytes: Callable[[str, str], bytes] = _default_get,
    minimum_request_interval: float = 0.11,
) -> dict[str, Any]:
    """Append structured SEC submissions evidence for approved active symbols only."""
    result = deepcopy(dict(report))
    warnings = result.setdefault("warnings", [])
    if not isinstance(warnings, list):
        warnings = []
        result["warnings"] = warnings
    if not str(user_agent).strip():
        warnings.append("TARGETED_SEC_ENRICHMENT_SKIPPED:MISSING_USER_AGENT")
        return result

    now = datetime.fromisoformat(str(as_of).replace("Z", "+00:00")) if not isinstance(as_of, datetime) else as_of
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now.date() - timedelta(days=7)
    requested = {str(value or "").strip().upper() for value in active_symbols if str(value or "").strip()}
    observations = {
        str(row.get("underlying_symbol") or "").strip().upper(): row
        for row in result.get("observations", [])
        if isinstance(row, dict) and str(row.get("underlying_symbol") or "").strip()
    }
    targets = sorted(requested & set(observations))
    if not targets:
        result["targeted_sec_enrichment"] = {
            "version": TARGETED_SEC_ENRICHMENT_VERSION,
            "policy": TARGETED_SEC_ENRICHMENT_POLICY,
            "target_count": 0,
            "enriched_count": 0,
        }
        return result

    last_request = 0.0
    try:
        ticker_payload = json.loads(get_bytes(SEC_COMPANY_TICKERS_URL, user_agent).decode("utf-8"))
        ticker_ciks = _ticker_ciks(ticker_payload if isinstance(ticker_payload, Mapping) else {})
        last_request = time.monotonic()
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        warnings.append(f"TARGETED_SEC_ENRICHMENT_DIRECTORY_FAILED:{exc}")
        return result

    enriched_count = 0
    for symbol in targets:
        cik = ticker_ciks.get(symbol)
        if not cik:
            warnings.append(f"TARGETED_SEC_ENRICHMENT_MISSING_CIK:{symbol}")
            continue
        try:
            remaining = minimum_request_interval - (time.monotonic() - last_request)
            if remaining > 0:
                time.sleep(remaining)
            payload = json.loads(get_bytes(SEC_SUBMISSIONS_URL.format(cik=cik), user_agent).decode("utf-8"))
            last_request = time.monotonic()
            filings = extract_recent_sec_filing_metadata(payload if isinstance(payload, Mapping) else {}, cutoff=cutoff)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            warnings.append(f"TARGETED_SEC_ENRICHMENT_FAILED:{symbol}:{exc}")
            continue
        row = observations[symbol]
        evidence = row.setdefault("source_evidence", [])
        if not isinstance(evidence, list):
            evidence = []
            row["source_evidence"] = evidence
        existing = {
            str(item.get("story_id") or "")
            for item in evidence if isinstance(item, Mapping)
        }
        added = 0
        for filing in filings:
            item = _filing_evidence(filing)
            if item["story_id"] in existing:
                # Prefer the structured targeted copy when the broad story identity is exact.
                for index, prior in enumerate(evidence):
                    if isinstance(prior, Mapping) and str(prior.get("story_id") or "") == item["story_id"]:
                        evidence[index] = item
                        break
                continue
            evidence.append(item)
            existing.add(item["story_id"])
            added += 1
        if filings:
            enriched_count += 1

    result["targeted_sec_enrichment"] = {
        "version": TARGETED_SEC_ENRICHMENT_VERSION,
        "policy": TARGETED_SEC_ENRICHMENT_POLICY,
        "target_count": len(targets),
        "enriched_count": enriched_count,
        "catalyst_inference_used": False,
    }
    return result
