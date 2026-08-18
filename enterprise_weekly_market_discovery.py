"""Deterministic, paper-only Enterprise weekly market discovery producer.

This module normalizes already-collected evidence. Network source adapters are
deliberately outside this layer so missing credentials fail closed.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "1.0"
SWING_STRATEGY_ID = "SWING-001"
DIVIDEND_STRATEGY_ID = "DIVIDEND-001"
ACTIVE_STATUSES = {"NEW", "EMERGING", "RISING", "HOT", "COOLING", "DECLINING"}
SWING_STATUSES = {"EMERGING", "RISING", "HOT", "COOLING", "DECLINING"}
SWING_ELIGIBLE = {"EMERGING", "RISING", "HOT"}
LEVERAGED_SUFFIXES = ("2X", "3X", "BULL", "BEAR")
SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,14}$")


def _utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise ValueError(f"invalid underlying_symbol: {value!r}")
    if symbol.endswith(LEVERAGED_SUFFIXES):
        raise ValueError(f"leveraged/inverse product is not an underlying nomination: {symbol}")
    return symbol


def _story_key(item: Mapping[str, Any]) -> str:
    return str(item.get("story_id") or item.get("canonical_story_id") or item.get("source_url") or "").strip()


def _normalize_evidence(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for raw in items:
        source = str(raw.get("source") or raw.get("source_name") or "").strip()
        mentioned = str(raw.get("mentioned_on") or raw.get("published_at") or "")[:10]
        if not source or not mentioned:
            continue
        mentioned = date.fromisoformat(mentioned).isoformat()
        story = _story_key(raw) or f"{source.lower()}:{mentioned}"
        producer = str(raw.get("producer") or raw.get("originating_source") or source).strip().lower()
        key = (story.lower(), producer, mentioned)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "source": source,
            "mentioned_on": mentioned,
            "source_class": str(raw.get("source_class") or "UNCLASSIFIED").upper(),
            "producer": str(raw.get("producer") or raw.get("originating_source") or source).strip(),
            "story_id": story,
            "themes": sorted({str(v).strip() for v in raw.get("themes", []) if str(v).strip()}),
            "stance": str(raw.get("stance") or "NEUTRAL").upper(),
            "earnings_growth_related": bool(raw.get("earnings_growth_related", False)),
            "analyst_upgrade_related": bool(raw.get("analyst_upgrade_related", False)),
        })
    return sorted(rows, key=lambda row: (row["mentioned_on"], row["source"], row["story_id"]))


def _evidence_analysis(evidence: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(evidence)
    independent_stories = {
        (str(row.get("story_id") or "").lower(), str(row.get("producer") or "").lower())
        for row in rows
    }
    producers = {str(row.get("producer") or "").strip().lower() for row in rows if str(row.get("producer") or "").strip()}
    source_classes = sorted({
        str(row.get("source_class") or "UNCLASSIFIED").upper()
        for row in rows
    })
    stances = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0, "MIXED": 0, "UNSPECIFIED": 0}
    for row in rows:
        stance = str(row.get("stance") or "UNSPECIFIED").upper()
        stances[stance if stance in stances else "UNSPECIFIED"] += 1
    independent_count = len(independent_stories)
    class_count = len(source_classes)
    if independent_count >= 3 and class_count >= 2:
        level = "STRONG"
    elif independent_count >= 2:
        level = "CONFIRMED"
    elif independent_count == 1:
        level = "SINGLE_SOURCE"
    else:
        level = "NONE"
    return {
        "independent_source_count": independent_count,
        "independent_producer_count": len(producers),
        "source_class_count": class_count,
        "source_classes": source_classes,
        "level": level,
        "syndicated_repeats_counted_separately": False,
        "stance_summary": {
            **stances,
            "disagreement_present": stances["BULLISH"] > 0 and stances["BEARISH"] > 0,
        },
        "inference_allowed": False,
    }


def _retention_days(status: str) -> int:
    if status == "EMERGING":
        return 21
    if status in {"COOLING", "DECLINING"}:
        return 7
    return 14


def build_weekly_discovery(
    observations: Iterable[Mapping[str, Any]],
    previous_candidates: Iterable[Mapping[str, Any]] = (),
    *,
    generated_at: str | datetime,
) -> dict[str, Any]:
    now = _utc(generated_at)
    previous = {_symbol(row.get("underlying_symbol")): dict(row) for row in previous_candidates}
    candidates: list[dict[str, Any]] = []
    research_evidence_pool: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in observations:
        symbol = _symbol(raw.get("underlying_symbol"))
        if symbol in seen:
            raise ValueError(f"duplicate underlying_symbol: {symbol}")
        seen.add(symbol)
        requested = str(raw.get("discovery_status") or "NEW").upper()
        if requested not in ACTIVE_STATUSES:
            raise ValueError(f"unsupported discovery_status: {requested}")
        prior = previous.get(symbol)
        first = _utc(prior.get("first_discovered_at")) if prior and prior.get("first_discovered_at") else now
        weeks = int(prior.get("consecutive_weeks_detected", 0)) + 1 if prior else 1
        evidence = _normalize_evidence(raw.get("source_evidence") or raw.get("evidence_sources") or [])
        evidence_analysis = _evidence_analysis(evidence)
        independent = evidence_analysis["independent_source_count"]
        expires = now + timedelta(days=_retention_days(requested))
        candidate = {
            "underlying_symbol": symbol,
            "discovery_status": requested,
            "previous_status": str(prior.get("discovery_status") or "ABSENT") if prior else "ABSENT",
            "first_discovered_at": _iso(first),
            "last_confirmed_at": _iso(now),
            "expires_at": _iso(expires),
            "consecutive_weeks_detected": weeks,
            "themes": sorted({str(v).strip() for v in raw.get("themes", []) if str(v).strip()}),
            "sector": str(raw.get("sector") or "").strip() or None,
            "catalysts": list(raw.get("catalysts") or []),
            "risks": list(raw.get("risks") or []),
            "bullish_thesis": raw.get("bullish_thesis"),
            "bearish_thesis": raw.get("bearish_thesis"),
            "source_evidence": evidence,
            "independent_source_count": independent,
            "source_confluence": evidence_analysis,
            "evidence_stance_summary": evidence_analysis["stance_summary"],
            "attention_acceleration": raw.get("attention_acceleration"),
            "market_evidence": raw.get("market_evidence"),
            "discovery_confidence": raw.get("discovery_confidence"),
            "nomination_eligible": bool(raw.get("nomination_eligible", True)),
        }
        if candidate["nomination_eligible"]:
            candidates.append(candidate)
        else:
            candidate["record_type"] = "RESEARCH_EVIDENCE_ONLY"
            research_evidence_pool.append(candidate)
    expired_candidates: list[dict[str, Any]] = []
    for symbol, prior in previous.items():
        if symbol in seen:
            continue
        expires_at = prior.get("expires_at")
        if expires_at and now <= _utc(expires_at):
            candidates.append(dict(prior))
            continue
        stale = dict(prior)
        stale["previous_status"] = prior.get("discovery_status") or prior.get("previous_status") or "NOT_REPORTED"
        stale["discovery_status"] = "STALE"
        stale["expired_at"] = _iso(now)
        expired_candidates.append(stale)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso(now),
        "schedule": "Saturday 20:00 America/Chicago",
        "paper_trade_mode": True,
        "advisory_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "order_placement_enabled": False,
        "capital_movement_enabled": False,
        "candidates": sorted(candidates, key=lambda row: row["underlying_symbol"]),
        "research_evidence_pool": sorted(research_evidence_pool, key=lambda row: row["underlying_symbol"]),
        "expired_candidates": sorted(expired_candidates, key=lambda row: row["underlying_symbol"]),
    }


def build_swing_projection(report: Mapping[str, Any]) -> dict[str, Any]:
    candidates = []
    for row in report.get("candidates", []):
        if row.get("nomination_eligible") is False:
            continue
        status = str(row.get("discovery_status") or "").upper()
        if status == "NEW":
            status = "EMERGING"
        if status not in SWING_STATUSES:
            continue
        candidates.append({
            "underlying_symbol": _symbol(row.get("underlying_symbol")),
            "discovery_status": status,
            "weekly_lifecycle_status": row.get("discovery_status"),
            "themes": list(row.get("themes") or []),
            "evidence_sources": [
                {
                    "source": evidence["source"],
                    "mentioned_on": evidence["mentioned_on"],
                    "themes": evidence.get("themes", []),
                    "earnings_growth_related": evidence.get("earnings_growth_related", False),
                    "analyst_upgrade_related": evidence.get("analyst_upgrade_related", False),
                }
                for evidence in row.get("source_evidence", [])
            ],
        })
    return {"schema_version": "1.0", "strategy_id": SWING_STRATEGY_ID, "candidates": candidates}


def build_dividend_projection(report: Mapping[str, Any]) -> dict[str, Any]:
    candidates = []
    for row in report.get("candidates", []):
        if row.get("discovery_status") not in ACTIVE_STATUSES:
            continue
        candidates.append({
            "underlying_symbol": _symbol(row.get("underlying_symbol")),
            "discovery_status": row.get("discovery_status"),
            "themes": list(row.get("themes") or []),
            "sector": row.get("sector"),
            "requires_dividend_income_mapping": True,
            "promotion_authority": DIVIDEND_STRATEGY_ID,
            "nomination_eligible": bool(row.get("nomination_eligible", True)),
            "source_evidence": list(row.get("source_evidence") or []),
        })
    return {
        "schema_version": "1.0",
        "strategy_id": DIVIDEND_STRATEGY_ID,
        "paper_trade_mode": True,
        "advisory_only": True,
        "candidates": candidates,
    }


def write_weekly_discovery(
    root: str | Path,
    observations: Iterable[Mapping[str, Any]],
    previous_candidates: Iterable[Mapping[str, Any]] = (),
    *,
    generated_at: str | datetime,
) -> dict[str, Any]:
    root_path = Path(root)
    results = root_path / "results"
    state = root_path / "state"
    results.mkdir(parents=True, exist_ok=True)
    state.mkdir(parents=True, exist_ok=True)
    report = build_weekly_discovery(observations, previous_candidates, generated_at=generated_at)
    outputs = {
        results / "enterprise_weekly_market_discovery.json": report,
        results / "enterprise_swing_discovery_bucket.json": build_swing_projection(report),
        results / "enterprise_dividend_discovery_bucket.json": build_dividend_projection(report),
    }
    for path, payload in outputs.items():
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (state / "enterprise_market_discovery_history.jsonl").open("a", encoding="utf-8") as handle:
        for candidate in [*report["candidates"], *report["research_evidence_pool"], *report["expired_candidates"]]:
            handle.write(json.dumps({"observed_at": report["generated_at"], **candidate}, sort_keys=True) + "\n")
    return report
