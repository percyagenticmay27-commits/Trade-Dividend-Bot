"""Assemble fail-closed Dividend Watchlist Promotion Readiness evidence.

The Dividend Gateway owns income-mechanism qualification before Watchlist admission.
This module owns only the four refreshable Watchlist -> paper-readiness gates:
Trusted Sources, Financial Health, Theme / Opportunity, and Entry Readiness.
No gate is hardcoded PASS. Missing or stale evidence remains PENDING.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Mapping

FINANCIAL_HEALTH_THRESHOLD = 70.0
FINANCIAL_HEALTH_COMPONENTS = (
    "revenue_growth",
    "eps_growth",
    "operating_cash_flow",
    "gross_margin_trend",
    "debt_health",
    "analyst_revisions",
    "sector_strength",
)

# Freshness windows are evidence-class policy, not cached PASS durations.
# A prior PASS is never reused after its required evidence becomes stale.
TRUSTED_SOURCE_MAX_AGE_HOURS = 24.0
FINANCIAL_HEALTH_MAX_AGE_HOURS = 168.0
THEME_OPPORTUNITY_MAX_AGE_HOURS = 24.0
ENTRY_MAX_AGE_HOURS = 24.0

_DISCOVERY_PATH = Path("results/enterprise_dividend_discovery_bucket.json")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _records(value: Any):
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _records(child)
    elif isinstance(value, list):
        for child in value:
            yield from _records(child)


def _symbol(record: Mapping[str, Any]) -> str:
    return str(record.get("underlying_symbol") or record.get("symbol") or record.get("ticker") or "").upper()


def _find_symbol(payload: Any, symbol: str) -> Mapping[str, Any]:
    symbol = symbol.upper()
    for record in _records(payload):
        if _symbol(record) == symbol:
            return record
    return {}


def _numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _freshness(timestamp: Any, max_age_hours: float, now: datetime | None) -> tuple[bool, str]:
    parsed = _parse_timestamp(timestamp)
    if parsed is None:
        return False, "Evidence timestamp is unavailable or invalid."
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    age_hours = max(0.0, (current - parsed).total_seconds() / 3600.0)
    if age_hours > max_age_hours:
        return False, f"Evidence is stale ({age_hours:.1f}h old; maximum {max_age_hours:.1f}h)."
    return True, ""


def _pending_for_stale(gate: dict[str, Any], timestamp: Any, max_age_hours: float, now: datetime | None) -> dict[str, Any]:
    fresh, reason = _freshness(timestamp, max_age_hours, now)
    gate["freshness_status"] = "FRESH" if fresh else "STALE_OR_UNAVAILABLE"
    gate["max_age_hours"] = max_age_hours
    if not fresh:
        gate["status"] = "PENDING"
        gate["reason"] = reason
    return gate


def _financial_health_gate(discovery: Mapping[str, Any], now: datetime | None) -> dict[str, Any]:
    block = discovery.get("financial_health")
    if not isinstance(block, Mapping):
        return {"status": "PENDING", "reason": "Authoritative Financial Health evidence is unavailable.", "freshness_status": "STALE_OR_UNAVAILABLE"}

    components = block.get("components")
    component_values: list[float] = []
    complete = isinstance(components, Mapping)
    if complete:
        for name in FINANCIAL_HEALTH_COMPONENTS:
            number = _numeric(components.get(name))
            if number is None:
                complete = False
                break
            component_values.append(number)

    score = _numeric(block.get("score"))
    if score is None and complete:
        score = mean(component_values)

    if not complete:
        status = "PENDING"
        reason = "Financial Health requires all seven governed components."
    elif score is None:
        status = "PENDING"
        reason = "Complete Financial Health components are present but no score could be resolved."
    else:
        status = "PASS" if score >= FINANCIAL_HEALTH_THRESHOLD else "FAIL"
        reason = None

    gate: dict[str, Any] = {
        "status": status,
        "value": round(score, 2) if score is not None and complete else None,
        "threshold": FINANCIAL_HEALTH_THRESHOLD,
        "evidence_source": str(_DISCOVERY_PATH),
    }
    if reason:
        gate["reason"] = reason
    if block.get("provenance") not in (None, ""):
        gate["provenance"] = block.get("provenance")
    timestamp = block.get("evidence_timestamp")
    if timestamp not in (None, ""):
        gate["as_of"] = timestamp
    if isinstance(components, Mapping):
        gate["components"] = copy.deepcopy(dict(components))
    return _pending_for_stale(gate, timestamp, FINANCIAL_HEALTH_MAX_AGE_HOURS, now)


def _trusted_sources_gate(discovery: Mapping[str, Any], now: datetime | None) -> dict[str, Any]:
    source_evidence = discovery.get("source_evidence")
    confluence = discovery.get("source_confluence")
    count = discovery.get("independent_source_count")
    if count is None and isinstance(confluence, Mapping):
        count = confluence.get("independent_source_count")
    if count is None and isinstance(source_evidence, list):
        producers = {
            str(record.get("producer") or record.get("source") or "").strip()
            for record in source_evidence
            if isinstance(record, Mapping) and (record.get("producer") or record.get("source"))
        }
        count = len(producers) if producers else None
    numeric_count = _numeric(count)

    timestamps: list[datetime] = []
    if isinstance(source_evidence, list):
        for record in source_evidence:
            if not isinstance(record, Mapping):
                continue
            mentioned = record.get("mentioned_on")
            if mentioned:
                parsed = _parse_timestamp(f"{mentioned}T23:59:59Z" if len(str(mentioned)) == 10 else mentioned)
                if parsed is not None:
                    timestamps.append(parsed)
    latest = max(timestamps).isoformat().replace("+00:00", "Z") if timestamps else discovery.get("evidence_timestamp")

    gate: dict[str, Any] = {
        "status": "PENDING",
        "reason": "Trusted-source evidence must be re-evaluated from current governed source evidence; no Dividend-specific pass threshold is published.",
        "evidence_source": str(_DISCOVERY_PATH),
    }
    if numeric_count is not None:
        gate["value"] = int(numeric_count) if numeric_count.is_integer() else numeric_count
    if latest:
        gate["as_of"] = latest
    if isinstance(confluence, Mapping):
        gate["provenance"] = copy.deepcopy(dict(confluence))
    return _pending_for_stale(gate, latest, TRUSTED_SOURCE_MAX_AGE_HOURS, now)


def _theme_gate(discovery: Mapping[str, Any], item: Mapping[str, Any], now: datetime | None) -> dict[str, Any]:
    explicit = item.get("opportunity_thesis") or item.get("theme_opportunity")
    theme = explicit if isinstance(explicit, Mapping) else discovery.get("theme_strength")
    if not isinstance(theme, Mapping):
        return {"status": "PENDING", "reason": "Authoritative Theme / Opportunity evidence is unavailable.", "freshness_status": "STALE_OR_UNAVAILABLE"}

    # Preserve an authoritative published status when present; otherwise fail closed.
    published_status = str(theme.get("status") or "").upper()
    status = published_status if published_status in {"PASS", "FAIL", "PENDING"} else "PENDING"
    gate: dict[str, Any] = {
        "status": status,
        "value": theme.get("score", theme.get("value")),
        "reason": theme.get("reason") or "Theme evidence is current only when refreshed; no Dividend-specific pass threshold is published.",
        "evidence_source": theme.get("evidence_source") or str(_DISCOVERY_PATH),
    }
    if theme.get("threshold") is not None:
        gate["threshold"] = theme.get("threshold")
    if theme.get("provenance") not in (None, ""):
        gate["provenance"] = theme.get("provenance")
    timestamp = theme.get("evidence_timestamp") or theme.get("as_of") or theme.get("generated_at_utc")
    if timestamp:
        gate["as_of"] = timestamp
    if isinstance(theme.get("components"), Mapping):
        gate["components"] = copy.deepcopy(dict(theme["components"]))
    return _pending_for_stale(gate, timestamp, THEME_OPPORTUNITY_MAX_AGE_HOURS, now)


def _entry_gate(item: Mapping[str, Any], now: datetime | None) -> dict[str, Any]:
    raw_status = str(item.get("entry_status") or "").upper()
    score = _numeric(item.get("entry_score"))
    if raw_status in {"STRONG_ENTRY", "BUY", "READY", "APPROVED"}:
        status = "PASS"
    elif raw_status in {"BLOCKED", "NO_ENTRY", "REJECTED", "FAIL"}:
        status = "FAIL"
    else:
        status = "PENDING"
    reason_parts = []
    if raw_status:
        reason_parts.append(f"Status: {raw_status}")
    confidence = item.get("entry_confidence_level") or item.get("entry_confidence")
    if confidence not in (None, ""):
        reason_parts.append(f"Confidence: {confidence}")
    timing = item.get("timing_context")
    if timing not in (None, ""):
        reason_parts.append(f"Timing: {timing}")
    reasons = item.get("entry_reasons")
    if isinstance(reasons, list) and reasons:
        reason_parts.append("Reasons: " + ", ".join(str(x) for x in reasons if x))
    timestamp = item.get("entry_evidence_generated_at_utc")
    gate: dict[str, Any] = {
        "status": status,
        "value": score,
        "reason": "; ".join(reason_parts) or "Authoritative entry evidence is unavailable.",
        "evidence_source": item.get("entry_evidence_source") or item.get("evidence_source") or "entry_score_report.json",
        "as_of": timestamp,
        "entry_status": raw_status or None,
        "confidence": confidence,
        "timing": timing,
    }
    if item.get("entry_threshold") is not None:
        gate["threshold"] = item.get("entry_threshold")
    return _pending_for_stale(gate, timestamp, ENTRY_MAX_AGE_HOURS, now)


def build_dividend_promotion_readiness(
    item: Mapping[str, Any], root: str | Path = ".", *, now: datetime | None = None
) -> dict[str, Any]:
    symbol = _symbol(item)
    root_path = Path(root)
    discovery = _find_symbol(_load_json(root_path / _DISCOVERY_PATH), symbol) if symbol else {}

    gates = {
        "trusted_sources": _trusted_sources_gate(discovery, now),
        "financial_health": _financial_health_gate(discovery, now),
        "opportunity_thesis": _theme_gate(discovery, item, now),
        "entry": _entry_gate(item, now),
    }
    blockers = [key.upper() for key, gate in gates.items() if str(gate.get("status") or "PENDING").upper() != "PASS"]
    return {
        **gates,
        "promotion_ready": not blockers,
        "blocking_reasons": blockers,
        "policy": "DIVIDEND_PRETRADE_FOUR_REFRESHABLE_GATES_FAIL_CLOSED",
    }


def enrich_dividend_watchlist_row(row: Mapping[str, Any], root: str | Path = ".", *, now: datetime | None = None) -> dict[str, Any]:
    enriched = copy.deepcopy(dict(row))
    raw = enriched.get("watchlist")
    if not isinstance(raw, list):
        return enriched
    items: list[Any] = []
    for value in raw:
        if not isinstance(value, Mapping):
            items.append(value)
            continue
        item = copy.deepcopy(dict(value))
        item["promotion_readiness"] = build_dividend_promotion_readiness(item, root, now=now)
        items.append(item)
    enriched["watchlist"] = items
    return enriched
