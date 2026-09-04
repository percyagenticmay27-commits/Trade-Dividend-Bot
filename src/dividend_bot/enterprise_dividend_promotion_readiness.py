"""Assemble fail-closed Dividend pre-trade Promotion Readiness evidence.

This module joins existing authoritative Dividend artifacts by symbol. It does not
change watchlist lifecycle state, authorize purchases, or use post-entry strategy
performance. Missing evidence remains PENDING.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from statistics import mean
from typing import Any, Mapping

FINANCIAL_HEALTH_THRESHOLD = 70.0

_DISCOVERY_PATH = Path("results/enterprise_dividend_discovery_bucket.json")
_SUITABILITY_PATH = Path("results/enterprise_dividend_suitability.json")
_MAPPING_PATH = Path("results/enterprise_dividend_income_mapping.json")


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


def _financial_health_gate(discovery: Mapping[str, Any]) -> dict[str, Any]:
    block = discovery.get("financial_health")
    if not isinstance(block, Mapping):
        return {"status": "PENDING", "reason": "Authoritative Financial Health evidence is unavailable."}

    score = _numeric(block.get("score"))
    components = block.get("components")
    if score is None and isinstance(components, Mapping):
        values = [_numeric(value) for value in components.values()]
        if values and all(value is not None for value in values):
            score = mean(value for value in values if value is not None)

    gate: dict[str, Any] = {
        "status": "PASS" if score is not None and score >= FINANCIAL_HEALTH_THRESHOLD else "FAIL" if score is not None else "PENDING",
        "value": round(score, 2) if score is not None else None,
        "threshold": FINANCIAL_HEALTH_THRESHOLD,
        "evidence_source": str(_DISCOVERY_PATH),
    }
    if block.get("provenance") not in (None, ""):
        gate["provenance"] = block.get("provenance")
    if block.get("evidence_timestamp") not in (None, ""):
        gate["as_of"] = block.get("evidence_timestamp")
    if isinstance(components, Mapping):
        gate["components"] = copy.deepcopy(dict(components))
    return gate


def _trusted_sources_gate(discovery: Mapping[str, Any]) -> dict[str, Any]:
    confluence = discovery.get("source_confluence")
    count = discovery.get("independent_source_count")
    if count is None and isinstance(confluence, Mapping):
        count = confluence.get("independent_source_count")
    numeric_count = _numeric(count)
    if numeric_count is None:
        return {"status": "PENDING", "reason": "Authoritative trusted-source count is unavailable."}
    return {
        "status": "PENDING",
        "value": int(numeric_count) if numeric_count.is_integer() else numeric_count,
        "reason": "Trusted-source evidence is available, but no Dividend-specific pass threshold is published.",
        "evidence_source": str(_DISCOVERY_PATH),
        "provenance": copy.deepcopy(confluence) if isinstance(confluence, Mapping) else None,
    }


def _suitability_gate(suitability: Mapping[str, Any], mapping: Mapping[str, Any]) -> dict[str, Any]:
    raw = str(suitability.get("suitability_status") or "").upper()
    if raw in {"ELIGIBLE", "PASS", "APPROVED"}:
        status = "PASS"
    elif raw in {"REJECTED", "FAIL", "INELIGIBLE"}:
        status = "FAIL"
    else:
        status = "PENDING"
    reasons = suitability.get("decision_reasons")
    if isinstance(reasons, list):
        reason = "; ".join(str(item) for item in reasons if item not in (None, ""))
    else:
        reason = str(reasons or "")
    if not reason and mapping:
        map_status = mapping.get("mapping_status")
        if map_status:
            reason = f"Income mapping status: {map_status}."
    return {
        "status": status,
        "value": suitability.get("suitability_score"),
        "reason": reason or "Authoritative Dividend suitability evidence is unavailable.",
        "evidence_source": str(_SUITABILITY_PATH),
        "as_of": suitability.get("evidence_as_of"),
        "suitability_status": raw or None,
        "mapping_status": mapping.get("mapping_status") if mapping else None,
    }


def _explicit_gate(*records: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    for record in records:
        for key in keys:
            value = record.get(key)
            if isinstance(value, Mapping):
                return copy.deepcopy(dict(value))
    return {"status": "PENDING", "reason": "Authoritative gate evidence is unavailable."}


def _valuation_gate(item: Mapping[str, Any]) -> dict[str, Any]:
    explicit = item.get("valuation")
    if isinstance(explicit, Mapping):
        return copy.deepcopy(dict(explicit))
    score = _numeric(item.get("valuation_score"))
    if score is None:
        return {"status": "PENDING", "reason": "Authoritative valuation score is unavailable."}
    return {
        "status": "PENDING",
        "value": score,
        "reason": "Valuation score is available, but no Dividend-specific pass threshold is published in this record.",
        "evidence_source": "Dividend watchlist / ranking evidence",
    }


def _theme_gate(discovery: Mapping[str, Any], item: Mapping[str, Any]) -> dict[str, Any]:
    explicit = item.get("opportunity_thesis") or item.get("theme_opportunity")
    if isinstance(explicit, Mapping):
        return copy.deepcopy(dict(explicit))
    theme = discovery.get("theme_strength")
    if not isinstance(theme, Mapping):
        return {"status": "PENDING", "reason": "Authoritative Theme / Opportunity evidence is unavailable."}
    gate: dict[str, Any] = {
        "status": "PENDING",
        "value": theme.get("score"),
        "reason": "Theme evidence is available, but no Dividend-specific pass threshold is published.",
        "evidence_source": str(_DISCOVERY_PATH),
    }
    if theme.get("provenance") not in (None, ""):
        gate["provenance"] = theme.get("provenance")
    if theme.get("evidence_timestamp") not in (None, ""):
        gate["as_of"] = theme.get("evidence_timestamp")
    if isinstance(theme.get("components"), Mapping):
        gate["components"] = copy.deepcopy(dict(theme["components"]))
    return gate


def _entry_gate(item: Mapping[str, Any]) -> dict[str, Any]:
    raw_status = str(item.get("entry_status") or "").upper()
    score = _numeric(item.get("entry_score"))
    if raw_status in {"STRONG_ENTRY", "BUY", "READY", "APPROVED"}:
        status = "PASS"
    elif raw_status in {"BLOCKED", "NO_ENTRY", "REJECTED", "FAIL"}:
        status = "FAIL"
    else:
        status = "PENDING"
    gate: dict[str, Any] = {
        "status": status,
        "value": score,
        "reason": "; ".join(str(x) for x in item.get("entry_reasons", []) if x) if isinstance(item.get("entry_reasons"), list) else None,
        "evidence_source": item.get("entry_evidence_source") or item.get("evidence_source") or "entry_score_report.json",
        "as_of": item.get("entry_evidence_generated_at_utc"),
        "entry_status": raw_status or None,
        "confidence": item.get("entry_confidence_level") or item.get("entry_confidence"),
        "timing": item.get("timing_context"),
    }
    if item.get("entry_threshold") is not None:
        gate["threshold"] = item.get("entry_threshold")
    return gate


def build_dividend_promotion_readiness(item: Mapping[str, Any], root: str | Path = ".") -> dict[str, Any]:
    symbol = _symbol(item)
    root_path = Path(root)
    discovery = _find_symbol(_load_json(root_path / _DISCOVERY_PATH), symbol) if symbol else {}
    suitability = _find_symbol(_load_json(root_path / _SUITABILITY_PATH), symbol) if symbol else {}
    mapping = _find_symbol(_load_json(root_path / _MAPPING_PATH), symbol) if symbol else {}

    trusted = _trusted_sources_gate(discovery)
    financial = _financial_health_gate(discovery)
    income = _suitability_gate(suitability, mapping)
    safety = _explicit_gate(item, suitability, discovery, keys=("dividend_safety", "income_safety", "payout_safety"))
    valuation = _valuation_gate(item)
    theme = _theme_gate(discovery, item)
    entry = _entry_gate(item)

    gates = {
        "trusted_sources": trusted,
        "financial_health": financial,
        "dividend_suitability": income,
        "dividend_safety": safety,
        "valuation": valuation,
        "opportunity_thesis": theme,
        "entry": entry,
    }
    blockers = [key.upper() for key, gate in gates.items() if str(gate.get("status") or "PENDING").upper() != "PASS"]
    return {
        **gates,
        "promotion_ready": not blockers,
        "blocking_reasons": blockers,
        "policy": "DIVIDEND_PRETRADE_ALL_SEVEN_GATES_FAIL_CLOSED",
    }


def enrich_dividend_watchlist_row(row: Mapping[str, Any], root: str | Path = ".") -> dict[str, Any]:
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
        item["promotion_readiness"] = build_dividend_promotion_readiness(item, root)
        items.append(item)
    enriched["watchlist"] = items
    return enriched
