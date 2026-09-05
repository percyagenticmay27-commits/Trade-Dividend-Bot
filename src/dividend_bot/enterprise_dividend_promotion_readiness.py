"""Assemble fail-closed Dividend Watchlist Promotion Readiness evidence.

The Dividend Gateway owns income-mechanism qualification before Watchlist admission.
This module owns only the four refreshable Watchlist -> paper-readiness gates:
Trusted Sources, Financial Health, Theme / Opportunity, and Entry Readiness.
No gate is hardcoded PASS. Missing, stale, or ungoverned freshness remains PENDING.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from statistics import mean
from typing import Any, Mapping

from src.dividend_bot.enterprise_dividend_gateway import evaluate_dividend_gateway

FINANCIAL_HEALTH_THRESHOLD = 70.0
FINANCIAL_HEALTH_COMPONENTS = (
    "revenue_growth", "eps_growth", "operating_cash_flow", "gross_margin_trend",
    "debt_health", "analyst_revisions", "sector_strength",
)
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
    for record in _records(payload):
        if _symbol(record) == symbol.upper():
            return record
    return {}


def _numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _governed_freshness(source: Mapping[str, Any], *, fallback: Any = None) -> tuple[str, str | None]:
    """Use only an upstream governed freshness state; never invent a local TTL."""
    raw = source.get("freshness_status")
    if raw in (None, ""):
        raw = fallback
    explicit = str(raw or "").strip().upper()
    if explicit in {"FRESH", "CURRENT", "CURRENT_CYCLE", "PASS"}:
        return "FRESH", None
    if explicit in {"STALE", "STALE_OR_UNAVAILABLE", "UNAVAILABLE", "FAIL"}:
        return "STALE_OR_UNAVAILABLE", "Upstream governed evidence freshness is stale or unavailable."
    if source.get("is_stale") is False:
        return "FRESH", None
    if source.get("is_stale") is True:
        return "STALE_OR_UNAVAILABLE", "Upstream governed evidence freshness is stale or unavailable."
    return "UNVERIFIED", "No governed freshness policy/state is published for this evidence."


def _apply_freshness(gate: dict[str, Any], source: Mapping[str, Any], *, fallback: Any = None) -> dict[str, Any]:
    freshness, reason = _governed_freshness(source, fallback=fallback)
    gate["freshness_status"] = freshness
    if freshness != "FRESH":
        gate["status"] = "PENDING"
        gate["reason"] = reason
    return gate


def _financial_health_gate(discovery: Mapping[str, Any]) -> dict[str, Any]:
    block = discovery.get("financial_health")
    if not isinstance(block, Mapping):
        return {"status": "PENDING", "reason": "Authoritative Financial Health evidence is unavailable.", "freshness_status": "STALE_OR_UNAVAILABLE"}
    components = block.get("components")
    values: list[float] = []
    complete = isinstance(components, Mapping)
    if complete:
        for name in FINANCIAL_HEALTH_COMPONENTS:
            number = _numeric(components.get(name))
            if number is None:
                complete = False
                break
            values.append(number)
    score = _numeric(block.get("score"))
    if score is None and complete:
        score = mean(values)
    if not complete:
        status, reason = "PENDING", "Financial Health requires all seven governed components."
    elif score is None:
        status, reason = "PENDING", "Complete Financial Health components are present but no score could be resolved."
    else:
        status, reason = ("PASS" if score >= FINANCIAL_HEALTH_THRESHOLD else "FAIL"), None
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
    return _apply_freshness(gate, block, fallback=discovery.get("freshness_status"))


def _trusted_sources_gate(discovery: Mapping[str, Any]) -> dict[str, Any]:
    source_evidence = discovery.get("source_evidence")
    confluence = discovery.get("source_confluence")
    count = discovery.get("independent_source_count")
    if count is None and isinstance(confluence, Mapping):
        count = confluence.get("independent_source_count")
    if count is None and isinstance(source_evidence, list):
        producers = {str(r.get("producer") or r.get("source") or "").strip() for r in source_evidence if isinstance(r, Mapping) and (r.get("producer") or r.get("source"))}
        count = len(producers) if producers else None
    numeric_count = _numeric(count)
    gate: dict[str, Any] = {
        "status": "PENDING",
        "reason": "Trusted-source evidence requires an authoritative Dividend-specific pass threshold.",
        "evidence_source": str(_DISCOVERY_PATH),
    }
    if numeric_count is not None:
        gate["value"] = int(numeric_count) if numeric_count.is_integer() else numeric_count
    if discovery.get("evidence_timestamp"):
        gate["as_of"] = discovery.get("evidence_timestamp")
    if isinstance(confluence, Mapping):
        gate["provenance"] = copy.deepcopy(dict(confluence))
    freshness_source = confluence if isinstance(confluence, Mapping) else discovery
    return _apply_freshness(gate, freshness_source, fallback=discovery.get("freshness_status"))


def _theme_gate(discovery: Mapping[str, Any], item: Mapping[str, Any]) -> dict[str, Any]:
    explicit = item.get("opportunity_thesis") or item.get("theme_opportunity")
    theme = explicit if isinstance(explicit, Mapping) else discovery.get("theme_strength")
    if not isinstance(theme, Mapping):
        return {"status": "PENDING", "reason": "Authoritative Theme / Opportunity evidence is unavailable.", "freshness_status": "STALE_OR_UNAVAILABLE"}
    published = str(theme.get("status") or "").upper()
    status = published if published in {"PASS", "FAIL", "PENDING"} else "PENDING"
    gate: dict[str, Any] = {
        "status": status,
        "value": theme.get("score", theme.get("value")),
        "reason": theme.get("reason") or "No authoritative Dividend-specific Theme / Opportunity pass threshold is published.",
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
    return _apply_freshness(gate, theme, fallback=discovery.get("freshness_status"))


def _entry_gate(item: Mapping[str, Any]) -> dict[str, Any]:
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
    gate: dict[str, Any] = {
        "status": status,
        "value": score,
        "reason": "; ".join(reason_parts) or "Authoritative entry evidence is unavailable.",
        "evidence_source": item.get("entry_evidence_source") or item.get("evidence_source") or "entry_score_report.json",
        "as_of": item.get("entry_evidence_generated_at_utc"),
        "entry_status": raw_status or None,
        "confidence": confidence,
        "timing": timing,
    }
    if item.get("entry_threshold") is not None:
        gate["threshold"] = item.get("entry_threshold")
    freshness_source = item.get("entry_evidence") if isinstance(item.get("entry_evidence"), Mapping) else item
    return _apply_freshness(gate, freshness_source, fallback=item.get("entry_freshness_status"))


def build_dividend_promotion_readiness(item: Mapping[str, Any], root: str | Path = ".", *, now: Any = None) -> dict[str, Any]:
    symbol = _symbol(item)
    root_path = Path(root)
    discovery = _find_symbol(_load_json(root_path / _DISCOVERY_PATH), symbol) if symbol else {}
    gates = {
        "trusted_sources": _trusted_sources_gate(discovery),
        "financial_health": _financial_health_gate(discovery),
        "opportunity_thesis": _theme_gate(discovery, item),
        "entry": _entry_gate(item),
    }
    blockers = [key.upper() for key, gate in gates.items() if str(gate.get("status") or "PENDING").upper() != "PASS"]
    gateway = evaluate_dividend_gateway(symbol, root_path, now=now) if symbol else {"eligibility_status": "RESEARCH_REQUIRED", "watchlist_admission_allowed": False}
    if gateway.get("eligibility_status") != "QUALIFIED" or gateway.get("watchlist_admission_allowed") is not True:
        blockers.insert(0, "DIVIDEND_GATEWAY")
    return {
        **gates,
        "dividend_gateway": gateway,
        "promotion_ready": not blockers,
        "blocking_reasons": blockers,
        "policy": "DIVIDEND_PRETRADE_GATEWAY_PLUS_FOUR_REFRESHABLE_GATES_FAIL_CLOSED",
    }


def enrich_dividend_watchlist_row(row: Mapping[str, Any], root: str | Path = ".", *, now: Any = None) -> dict[str, Any]:
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
