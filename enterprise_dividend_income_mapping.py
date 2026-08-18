"""Dividend-owned mapping from discovered underlyings to reviewed income vehicles.

This layer is advisory and paper-only. It never invents a mapping, activates a
candidate, changes allocation, or places an order.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "1.0"
STRATEGY_ID = "DIVIDEND-001"
MAPPING_TYPES = {"DIRECT_DIVIDEND_EQUITY", "INCOME_ETF"}
MAPPING_STATUSES = {"REVIEWED", "DISABLED"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _symbol(value: Any, field: str) -> str:
    symbol = str(value or "").strip().upper()
    if not symbol or not symbol.replace(".", "").replace("-", "").isalnum():
        raise ValueError(f"{field} must be a valid uppercase symbol")
    return symbol


def load_json(path: str | Path) -> dict[str, Any]:
    file = Path(path)
    if not file.is_file():
        raise FileNotFoundError(file)
    payload = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{file} must contain a JSON object")
    return dict(payload)


def validate_discovery_bucket(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Dividend discovery schema_version must be 1.0")
    if payload.get("strategy_id") != STRATEGY_ID:
        raise ValueError("Dividend discovery strategy_id must be DIVIDEND-001")
    if payload.get("paper_trade_mode") is not True or payload.get("advisory_only") is not True:
        raise ValueError("Dividend discovery bucket must remain paper-only and advisory")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("Dividend discovery candidates must be a list")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for raw in candidates:
        if not isinstance(raw, Mapping):
            raise ValueError("Dividend discovery candidate must be an object")
        symbol = _symbol(raw.get("underlying_symbol"), "underlying_symbol")
        if symbol in seen:
            raise ValueError(f"duplicate Dividend discovery underlying: {symbol}")
        if raw.get("requires_dividend_income_mapping") is not True:
            raise ValueError(f"{symbol} must require Dividend-owned income mapping")
        if raw.get("promotion_authority") != STRATEGY_ID:
            raise ValueError(f"{symbol} promotion authority must remain DIVIDEND-001")
        seen.add(symbol)
        normalized.append(dict(raw, underlying_symbol=symbol))
    return dict(payload, candidates=normalized)


def validate_mapping_catalog(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Dividend income mapping catalog schema_version must be 1.0")
    if payload.get("strategy_id") != STRATEGY_ID:
        raise ValueError("Dividend income mapping catalog strategy_id must be DIVIDEND-001")
    rows = payload.get("mappings")
    if not isinstance(rows, list):
        raise ValueError("Dividend income mapping catalog mappings must be a list")
    result: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise ValueError("Dividend income mapping must be an object")
        underlying = _symbol(raw.get("underlying_symbol"), "underlying_symbol")
        income_symbol = _symbol(raw.get("income_symbol"), "income_symbol")
        mapping_type = str(raw.get("mapping_type") or "").upper()
        status = str(raw.get("status") or "").upper()
        if mapping_type not in MAPPING_TYPES:
            raise ValueError(f"{underlying} mapping_type is not approved")
        if status not in MAPPING_STATUSES:
            raise ValueError(f"{underlying} mapping status is not approved")
        if raw.get("reviewed") is not True:
            raise ValueError(f"{underlying} mapping must be explicitly reviewed")
        if raw.get("automatic_activation_allowed") is not False:
            raise ValueError(f"{underlying} automatic activation must be false")
        evidence = raw.get("mapping_evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"{underlying} mapping requires evidence")
        for item in evidence:
            if not isinstance(item, Mapping) or not str(item.get("source_url") or "").startswith("https://"):
                raise ValueError(f"{underlying} mapping evidence requires HTTPS source URLs")
        if underlying in result:
            raise ValueError(f"duplicate reviewed Dividend mapping: {underlying}")
        result[underlying] = {
            **dict(raw),
            "underlying_symbol": underlying,
            "income_symbol": income_symbol,
            "mapping_type": mapping_type,
            "status": status,
        }
    return result


def build_income_mapping_report(
    discovery_bucket: Mapping[str, Any],
    mapping_catalog: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    bucket = validate_discovery_bucket(discovery_bucket)
    catalog = validate_mapping_catalog(mapping_catalog)
    rows: list[dict[str, Any]] = []
    for candidate in bucket["candidates"]:
        underlying = candidate["underlying_symbol"]
        mapping = catalog.get(underlying)
        approved = bool(mapping and mapping["status"] == "REVIEWED")
        rows.append({
            "underlying_symbol": underlying,
            "discovery_status": candidate.get("discovery_status"),
            "mapping_status": "REVIEWED_MAPPING_AVAILABLE" if approved else "RESEARCH_REQUIRED",
            "income_symbol": mapping["income_symbol"] if approved else None,
            "mapping_type": mapping["mapping_type"] if approved else None,
            "mapping_evidence": list(mapping["mapping_evidence"]) if approved else [],
            "requires_manual_review": True,
            "automatic_activation_allowed": False,
            "promotion_authority": STRATEGY_ID,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "strategy_id": STRATEGY_ID,
        "generated_at": generated_at or _utc_now(),
        "paper_trade_mode": True,
        "advisory_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "order_placement_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
        "candidate_count": len(rows),
        "reviewed_mapping_count": sum(row["mapping_status"] == "REVIEWED_MAPPING_AVAILABLE" for row in rows),
        "research_required_count": sum(row["mapping_status"] == "RESEARCH_REQUIRED" for row in rows),
        "candidates": rows,
    }


def write_income_mapping_report(
    discovery_path: str | Path,
    catalog_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    report = build_income_mapping_report(load_json(discovery_path), load_json(catalog_path))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
