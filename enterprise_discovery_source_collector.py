"""Credential-free SEC/company-feed collection for Enterprise discovery.

Configured sources associate an underlying company with its authoritative SEC
CIK or company/IR feed. The collector never guesses a ticker from prose.
"""
from __future__ import annotations

import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from enterprise_weekly_market_discovery import _symbol

SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_FORMS = {"8-K", "10-K", "10-Q", "20-F", "40-F", "6-K", "S-1", "S-3", "DEF 14A"}


def _as_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
            return parsed.date()
        except (TypeError, ValueError, OverflowError):
            return None


def _default_get(url: str, user_agent: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "application/json, application/atom+xml, application/rss+xml, application/xml, text/xml"})
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310: URLs are owner-configured HTTPS sources
        return response.read()


def _recent_sec_evidence(payload: Mapping[str, Any], source: Mapping[str, Any], cutoff: date) -> list[dict[str, Any]]:
    recent = ((payload.get("filings") or {}).get("recent") or {}) if isinstance(payload, Mapping) else {}
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    accessions = recent.get("accessionNumber") or []
    primary_docs = recent.get("primaryDocument") or []
    rows = []
    for index, form in enumerate(forms):
        filed = _as_date(dates[index] if index < len(dates) else None)
        if not filed or filed < cutoff or str(form).upper() not in SEC_FORMS:
            continue
        accession = str(accessions[index] if index < len(accessions) else "").strip()
        document = str(primary_docs[index] if index < len(primary_docs) else "").strip()
        rows.append({
            "source": str(source.get("source_name") or "SEC EDGAR"),
            "source_class": "PRIMARY_COMPANY",
            "producer": "U.S. Securities and Exchange Commission",
            "mentioned_on": filed.isoformat(),
            "story_id": f"SEC:{accession or document or filed.isoformat()}",
            "stance": "NEUTRAL",
            "themes": list(source.get("themes") or []),
            "earnings_growth_related": str(form).upper() in {"10-K", "10-Q", "20-F", "40-F", "6-K"},
            "analyst_upgrade_related": False,
            "form": str(form).upper(),
            "accession_number": accession or None,
            "primary_document": document or None,
        })
    return rows


def _recent_feed_evidence(xml_bytes: bytes, source: Mapping[str, Any], cutoff: date) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    rows = []
    entries = list(root.findall(".//item")) + list(root.findall(".//{*}entry"))
    for entry in entries:
        title = (entry.findtext("title") or entry.findtext("{*}title") or "").strip()
        published_text = (
            entry.findtext("pubDate") or entry.findtext("published") or entry.findtext("updated")
            or entry.findtext("{*}published") or entry.findtext("{*}updated")
        )
        published = _as_date(published_text)
        if not title or not published or published < cutoff:
            continue
        link = entry.findtext("link") or ""
        if not link:
            link_element = entry.find("{*}link")
            link = str(link_element.get("href") or "") if link_element is not None else ""
        rows.append({
            "source": str(source.get("source_name") or "Company Investor Relations"),
            "source_class": str(source.get("source_class") or "PRIMARY_COMPANY").upper(),
            "producer": str(source.get("producer") or source.get("source_name") or "Company Investor Relations"),
            "mentioned_on": published.isoformat(),
            "story_id": str(link or f"{source.get('source_name')}:{published}:{title}"),
            "source_url": str(link) or None,
            "title": title,
            "stance": "NEUTRAL",
            "themes": list(source.get("themes") or []),
            "earnings_growth_related": bool(source.get("earnings_growth_related", False)),
            "analyst_upgrade_related": False,
        })
    return rows


def collect_credential_free_observations(
    sources: Iterable[Mapping[str, Any]],
    *,
    as_of: str | datetime,
    user_agent: str,
    market_snapshot: Mapping[str, Any] | None = None,
    get_bytes: Callable[[str, str], bytes] = _default_get,
    minimum_request_interval: float = 0.11,
) -> dict[str, Any]:
    """Collect configured authoritative feeds without inferring symbols."""
    if not str(user_agent).strip():
        raise ValueError("A descriptive User-Agent with operator contact is required")
    now = datetime.fromisoformat(str(as_of).replace("Z", "+00:00")) if not isinstance(as_of, datetime) else as_of
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now.date() - timedelta(days=7)
    by_symbol: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    last_request = 0.0
    for source in sources:
        try:
            symbol = _symbol(source.get("underlying_symbol"))
            kind = str(source.get("source_type") or "").upper()
            if kind == "SEC_SUBMISSIONS":
                cik = str(source.get("cik") or "").strip().zfill(10)
                if not cik.isdigit() or len(cik) != 10:
                    raise ValueError("SEC source requires a numeric CIK")
                url = SEC_SUBMISSIONS_URL.format(cik=cik)
            elif kind in {"RSS", "ATOM", "COMPANY_FEED"}:
                url = str(source.get("url") or "").strip()
                if not url.lower().startswith("https://"):
                    raise ValueError("feed URL must use HTTPS")
            else:
                raise ValueError(f"unsupported credential-free source_type: {kind}")
            remaining = minimum_request_interval - (time.monotonic() - last_request)
            if remaining > 0:
                time.sleep(remaining)
            raw = get_bytes(url, user_agent)
            last_request = time.monotonic()
            evidence = (
                _recent_sec_evidence(json.loads(raw.decode("utf-8")), source, cutoff)
                if kind == "SEC_SUBMISSIONS" else _recent_feed_evidence(raw, source, cutoff)
            )
            if not evidence:
                continue
            row = by_symbol.setdefault(symbol, {
                "underlying_symbol": symbol,
                "discovery_status": "NEW",
                "themes": set(),
                "sector": source.get("sector"),
                "source_evidence": [],
            })
            row["themes"].update(str(value).strip() for value in source.get("themes", []) if str(value).strip())
            row["source_evidence"].extend(evidence)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError, ET.ParseError) as exc:
            warnings.append(f"{source.get('source_name') or source.get('underlying_symbol') or 'SOURCE'}: {exc}")

    market_records = {}
    if isinstance(market_snapshot, Mapping):
        for record in market_snapshot.get("records", []):
            if isinstance(record, Mapping) and record.get("symbol"):
                market_records[str(record["symbol"]).upper()] = dict(record)
    observations = []
    for symbol, row in sorted(by_symbol.items()):
        row["themes"] = sorted(row["themes"])
        market = market_records.get(symbol)
        row["market_evidence"] = market if market is not None else None
        if market is None:
            row.setdefault("evidence_warnings", []).append("Market evidence is unavailable; no market conclusion was inferred.")
        observations.append(row)
    return {
        "schema_version": "1.0",
        "generated_at": now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "paper_trade_mode": True,
        "advisory_only": True,
        "observations": observations,
        "warnings": warnings,
    }


def load_json_if_present(path: Path) -> Any:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
