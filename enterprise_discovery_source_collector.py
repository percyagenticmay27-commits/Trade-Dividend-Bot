"""Credential-free SEC/company-feed collection for Enterprise discovery.

Configured sources associate an underlying company with its authoritative SEC
CIK or company/IR feed. The collector never guesses a ticker from prose.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from enterprise_weekly_market_discovery import _symbol

SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_FORMS = {"8-K", "10-K", "10-Q", "20-F", "40-F", "6-K", "S-1", "S-3", "DEF 14A"}
SEC_BROAD_DISCOVERY_FORMS = {"8-K", "6-K", "S-1"}
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_MAX_RESULTS = 25


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


def _youtube_symbols(text: str, allowed_symbols: Iterable[str]) -> list[str]:
    """Return explicit, market-context tickers from an approved underlying universe."""
    original = str(text or "")
    matches = set()
    for raw_symbol in allowed_symbols:
        try:
            symbol = _symbol(raw_symbol)
        except ValueError:
            continue
        escaped = re.escape(symbol)
        boundary_symbol = rf"(?<![A-Z0-9]){escaped}(?![A-Z0-9])"
        cashtag = re.search(rf"(?<![A-Z0-9])\${escaped}(?![A-Z0-9])", original, re.IGNORECASE)
        parenthesized = re.search(rf"\(\s*{escaped}\s*\)", original)
        market_context = re.search(
            rf"(?:{boundary_symbol}\s+(?:stock|shares?|earnings|ticker)|(?:stock|shares?|ticker)\s+{boundary_symbol})",
            original,
            re.IGNORECASE,
        )
        if cashtag or parenthesized or market_context:
            matches.add(symbol)
    return sorted(matches)


def collect_youtube_evidence(
    sources: Iterable[Mapping[str, Any]],
    *,
    as_of: str | datetime,
    api_key: str,
    allowed_symbols: Iterable[str],
    user_agent: str,
    get_bytes: Callable[[str, str], bytes] = _default_get,
    quota_budget_units: int = 500,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Collect bounded YouTube search evidence without treating popularity as authority.

    A search.list request costs quota, so this adapter has an explicit per-run budget.
    Symbols are recognized only from the caller's underlying-company universe; the
    adapter never promotes an unknown token or a leveraged product from video prose.
    """
    if not str(api_key).strip():
        return [], ["YouTube Data API key is unavailable; YouTube evidence was not collected."]
    now = datetime.fromisoformat(str(as_of).replace("Z", "+00:00")) if not isinstance(as_of, datetime) else as_of
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    published_after = now - timedelta(days=7)
    remaining = max(0, int(quota_budget_units))
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for source in sources:
        if remaining < 100:
            warnings.append("YouTube quota budget reached; remaining configured searches were skipped.")
            break
        query = str(source.get("query") or "").strip()
        channel_id = str(source.get("channel_id") or "").strip()
        if not query and not channel_id:
            warnings.append(f"{source.get('source_name') or 'YouTube source'}: query or channel_id is required")
            continue
        params = {
            "part": "snippet",
            "type": "video",
            "order": "date",
            "maxResults": str(min(YOUTUBE_MAX_RESULTS, max(1, int(source.get("max_results", 10))))),
            "publishedAfter": published_after.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "key": api_key,
        }
        if query:
            params["q"] = query
        if channel_id:
            params["channelId"] = channel_id
        try:
            payload = json.loads(get_bytes(f"{YOUTUBE_SEARCH_URL}?{urllib.parse.urlencode(params)}", user_agent).decode("utf-8"))
            remaining -= 100
            for item in payload.get("items", []) if isinstance(payload, Mapping) else []:
                snippet = item.get("snippet") if isinstance(item, Mapping) else None
                if not isinstance(snippet, Mapping):
                    continue
                video_id = ((item.get("id") or {}).get("videoId")) if isinstance(item.get("id"), Mapping) else None
                published = _as_date(snippet.get("publishedAt"))
                if not video_id or not published:
                    continue
                title = str(snippet.get("title") or "")
                description = str(snippet.get("description") or "")
                producer = str(snippet.get("channelTitle") or source.get("source_name") or "").strip()
                actual_channel_id = str(snippet.get("channelId") or "").strip()
                configured_channel_id = channel_id or None
                if configured_channel_id and actual_channel_id != configured_channel_id:
                    continue
                authority = str(source.get("authority") or "DISCOVERY_ONLY").upper()
                reviewed = bool(source.get("credibility_reviewed", False))
                for symbol in _youtube_symbols(f"{title}\n{description}", allowed_symbols):
                    rows.append({
                        "underlying_symbol": symbol,
                        "evidence": {
                            "source": producer,
                            "source_class": "PROFESSIONAL_MEDIA" if authority == "PROFESSIONAL_MEDIA" else "CREATOR_INTELLIGENCE",
                            "producer": producer,
                            "mentioned_on": published.isoformat(),
                            "story_id": f"YOUTUBE:{video_id}",
                            "source_url": f"https://www.youtube.com/watch?v={video_id}",
                            "title": title,
                            "stance": "NEUTRAL",
                            "themes": list(source.get("themes") or []),
                            "earnings_growth_related": bool(source.get("earnings_growth_related", False)),
                            "analyst_upgrade_related": bool(source.get("analyst_upgrade_related", False)),
                            "platform": "YOUTUBE",
                            "channel_id": actual_channel_id or None,
                            "credibility_reviewed": reviewed,
                            "authority": authority,
                        },
                        "confirmation_eligible": reviewed and authority in {"REVIEWED_CREATOR", "PROFESSIONAL_MEDIA"},
                    })
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            # Never include the request URL because it contains the API key.
            warnings.append(f"{source.get('source_name') or 'YouTube source'}: YouTube request failed: {exc}")
    return rows, warnings


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


def collect_professional_feed_evidence(
    sources: Iterable[Mapping[str, Any]],
    *,
    as_of: str | datetime,
    allowed_symbols: Iterable[str],
    user_agent: str,
    get_bytes: Callable[[str, str], bytes] = _default_get,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Collect reviewed professional RSS/Atom headlines for known underlyings only."""
    now = datetime.fromisoformat(str(as_of).replace("Z", "+00:00")) if not isinstance(as_of, datetime) else as_of
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now.date() - timedelta(days=7)
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for source in sources:
        name = str(source.get("source_name") or "Professional media feed").strip()
        url = str(source.get("url") or "").strip()
        reviewed = bool(source.get("credibility_reviewed", False))
        authority = str(source.get("authority") or "").upper()
        if not reviewed or authority != "PROFESSIONAL_MEDIA":
            warnings.append(f"{name}: professional feed is not credibility-reviewed and was skipped")
            continue
        if not url.lower().startswith("https://"):
            warnings.append(f"{name}: feed URL must use HTTPS")
            continue
        try:
            payload = None
            last_error = None
            for attempt in range(3):
                try:
                    payload = get_bytes(url, user_agent)
                    break
                except OSError as exc:
                    last_error = exc
                    if attempt < 2:
                        time.sleep(1.0 * (attempt + 1))
            if payload is None:
                raise last_error or OSError("professional feed request failed")
            evidence_rows = _recent_feed_evidence(payload, {
                **dict(source),
                "source_class": "PROFESSIONAL_MEDIA",
                "producer": source.get("producer") or name,
            }, cutoff)
            for evidence in evidence_rows:
                title = str(evidence.get("title") or "")
                for symbol in _youtube_symbols(title, allowed_symbols):
                    evidence["platform"] = "PROFESSIONAL_RSS"
                    evidence["credibility_reviewed"] = True
                    evidence["authority"] = "PROFESSIONAL_MEDIA"
                    rows.append({
                        "underlying_symbol": symbol,
                        "evidence": dict(evidence),
                        "confirmation_eligible": True,
                    })
        except (OSError, UnicodeError, ValueError, ET.ParseError) as exc:
            warnings.append(f"{name}: professional feed request failed: {exc}")
    return rows, warnings


def _ticker_map(payload: Any) -> dict[str, dict[str, str]]:
    if isinstance(payload, Mapping) and isinstance(payload.get("fields"), list) and isinstance(payload.get("data"), list):
        fields = [str(value) for value in payload["fields"]]
        values = [dict(zip(fields, row)) for row in payload["data"] if isinstance(row, list)]
    else:
        values = payload.values() if isinstance(payload, Mapping) else payload if isinstance(payload, list) else []
    result = {}
    excluded = (" ETF", " ETN", " 2X", " 3X", " ULTRA", " LEVERAGED", " INVERSE", " BULL ", " BEAR ")
    allowed_exchanges = {"NASDAQ", "NYSE", "NYSE AMERICAN"}
    for row in values:
        if not isinstance(row, Mapping):
            continue
        cik = str(row.get("cik_str") or row.get("cik") or "").strip().lstrip("0")
        ticker = str(row.get("ticker") or "").strip().upper()
        title = str(row.get("title") or row.get("name") or "").strip()
        exchange = str(row.get("exchange") or "").strip().upper()
        non_common_suffix = (len(ticker) >= 5 and ticker.endswith(("U", "W", "WS"))) or "-P" in ticker or "^" in ticker
        if (
            not cik or not ticker or exchange not in allowed_exchanges or non_common_suffix
            or any(token in f" {title.upper()} " for token in excluded)
        ):
            continue
        try:
            candidate = {"underlying_symbol": _symbol(ticker), "company_name": title, "exchange": exchange}
            current = result.get(cik)
            candidate_score = ("-" not in ticker, len(ticker) <= 4, -len(ticker), ticker)
            current_ticker = current.get("underlying_symbol", "") if current else ""
            current_score = ("-" not in current_ticker, len(current_ticker) <= 4, -len(current_ticker), current_ticker)
            if current is None or candidate_score > current_score:
                result[cik] = candidate
        except ValueError:
            continue
    return result


def _parse_master_index(payload: bytes, tickers: Mapping[str, Mapping[str, str]], source_url: str) -> list[dict[str, Any]]:
    rows = []
    in_data = False
    for line in payload.decode("latin-1").splitlines():
        if line.startswith("-----"):
            in_data = True
            continue
        if not in_data:
            continue
        parts = line.split("|")
        if len(parts) != 5:
            continue
        cik, company, form, filed, filename = (part.strip() for part in parts)
        if form.upper() not in SEC_BROAD_DISCOVERY_FORMS or cik.lstrip("0") not in tickers:
            continue
        identity = tickers[cik.lstrip("0")]
        rows.append({
            "underlying_symbol": identity["underlying_symbol"],
            "company_name": identity.get("company_name") or company,
            "exchange": identity.get("exchange"),
            "evidence": {
                "source": "SEC EDGAR Daily Index",
                "source_class": "PRIMARY_COMPANY",
                "producer": "U.S. Securities and Exchange Commission",
                "mentioned_on": filed,
                "story_id": f"SEC:{filename}",
                "source_url": f"https://www.sec.gov/Archives/{filename}",
                "stance": "NEUTRAL",
                "themes": [],
                "earnings_growth_related": form.upper() == "6-K",
                "analyst_upgrade_related": False,
                "form": form.upper(),
                "broad_discovery_source": source_url,
            },
        })
    return rows


def collect_broad_sec_filing_evidence(
    *, as_of: str | datetime, user_agent: str,
    get_bytes: Callable[[str, str], bytes] = _default_get,
    index_dates: Iterable[str] | None = None,
    minimum_request_interval: float = 0.11,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not str(user_agent).strip():
        raise ValueError("A descriptive User-Agent with operator contact is required")
    now = datetime.fromisoformat(str(as_of).replace("Z", "+00:00")) if not isinstance(as_of, datetime) else as_of
    dates = [date.fromisoformat(value) for value in index_dates] if index_dates is not None else [
        now.date() - timedelta(days=offset) for offset in range(1, 8)
        if (now.date() - timedelta(days=offset)).weekday() < 5
    ]
    warnings = []
    last_request = 0.0
    tickers = _ticker_map(json.loads(get_bytes(SEC_COMPANY_TICKERS_URL, user_agent).decode("utf-8")))
    last_request = time.monotonic()
    evidence = []
    for day in dates:
        quarter = ((day.month - 1) // 3) + 1
        url = f"https://www.sec.gov/Archives/edgar/daily-index/{day.year}/QTR{quarter}/master.{day:%Y%m%d}.idx"
        try:
            remaining = minimum_request_interval - (time.monotonic() - last_request)
            if remaining > 0:
                time.sleep(remaining)
            evidence.extend(_parse_master_index(get_bytes(url, user_agent), tickers, url))
            last_request = time.monotonic()
        except (OSError, UnicodeError, ValueError) as exc:
            warnings.append(f"SEC daily index {day.isoformat()}: {exc}")
    return evidence, warnings


def collect_credential_free_observations(
    sources: Iterable[Mapping[str, Any]],
    *,
    as_of: str | datetime,
    user_agent: str,
    market_snapshot: Mapping[str, Any] | None = None,
    youtube_api_key: str = "",
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
    source_rows = list(sources)
    youtube_sources = [row for row in source_rows if str(row.get("source_type") or "").upper() == "YOUTUBE_SEARCH"]
    professional_sources = [row for row in source_rows if str(row.get("source_type") or "").upper() == "PROFESSIONAL_RSS"]
    deferred_types = {"YOUTUBE_SEARCH", "PROFESSIONAL_RSS"}
    non_youtube_sources = [row for row in source_rows if str(row.get("source_type") or "").upper() not in deferred_types]
    for source in non_youtube_sources:
        try:
            kind = str(source.get("source_type") or "").upper()
            if kind == "SEC_DAILY_INDEX":
                broad_rows, broad_warnings = collect_broad_sec_filing_evidence(
                    as_of=now, user_agent=user_agent, get_bytes=get_bytes,
                    index_dates=source.get("index_dates"),
                    minimum_request_interval=minimum_request_interval,
                )
                warnings.extend(broad_warnings)
                for item in broad_rows:
                    broad_symbol = item["underlying_symbol"]
                    broad = by_symbol.setdefault(broad_symbol, {
                        "underlying_symbol": broad_symbol,
                        "discovery_status": "NEW",
                        "themes": set(),
                        "sector": None,
                        "source_evidence": [],
                        "nomination_eligible": False,
                        "evidence_only_reason": "A material SEC filing is neutral discovery evidence and requires independent confirmation.",
                    })
                    broad["source_evidence"].append(item["evidence"])
                continue
            elif kind == "SEC_SUBMISSIONS":
                symbol = _symbol(source.get("underlying_symbol"))
                cik = str(source.get("cik") or "").strip().zfill(10)
                if not cik.isdigit() or len(cik) != 10:
                    raise ValueError("SEC source requires a numeric CIK")
                url = SEC_SUBMISSIONS_URL.format(cik=cik)
            elif kind in {"RSS", "ATOM", "COMPANY_FEED"}:
                symbol = _symbol(source.get("underlying_symbol"))
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

    professional_rows, professional_warnings = collect_professional_feed_evidence(
        professional_sources,
        as_of=now,
        allowed_symbols=by_symbol,
        user_agent=user_agent,
        get_bytes=get_bytes,
    ) if professional_sources else ([], [])
    warnings.extend(professional_warnings)
    for item in professional_rows:
        symbol = item["underlying_symbol"]
        row = by_symbol[symbol]
        row["source_evidence"].append(item["evidence"])
        row["themes"].update(str(value).strip() for value in item["evidence"].get("themes", []) if str(value).strip())
        if item.get("confirmation_eligible"):
            row.setdefault("confirmation_producers", set()).add(str(item["evidence"].get("producer") or "").lower())

    youtube_rows, youtube_warnings = collect_youtube_evidence(
        youtube_sources,
        as_of=now,
        api_key=youtube_api_key,
        allowed_symbols=by_symbol,
        user_agent=user_agent,
        get_bytes=get_bytes,
    ) if youtube_sources else ([], [])
    warnings.extend(youtube_warnings)
    for item in youtube_rows:
        symbol = item["underlying_symbol"]
        row = by_symbol.setdefault(symbol, {
            "underlying_symbol": symbol,
            "discovery_status": "NEW",
            "themes": set(),
            "sector": None,
            "source_evidence": [],
            "nomination_eligible": False,
            "evidence_only_reason": "YouTube attention alone is discovery evidence, not a strategy nomination.",
        })
        row["source_evidence"].append(item["evidence"])
        row["themes"].update(str(value).strip() for value in item["evidence"].get("themes", []) if str(value).strip())
        if item.get("confirmation_eligible"):
            row.setdefault("confirmation_producers", set()).add(str(item["evidence"].get("producer") or "").lower())

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
        producers = {str(item.get("producer") or item.get("source") or "").lower() for item in row["source_evidence"]}
        confirmation_producers = row.pop("confirmation_producers", set())
        non_youtube_producers = {
            str(item.get("producer") or item.get("source") or "").lower()
            for item in row["source_evidence"] if item.get("platform") != "YOUTUBE"
        }
        if row.get("nomination_eligible") is False and non_youtube_producers and confirmation_producers:
            row["nomination_eligible"] = True
            row.pop("evidence_only_reason", None)
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
