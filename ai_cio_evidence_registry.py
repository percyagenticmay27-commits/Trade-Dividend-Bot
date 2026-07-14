"""Immutable paper-only evidence registry for the AI CIO platform."""
from __future__ import annotations

import hashlib
import html
import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "ai_cio_evidence_registry"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_OUTPUT_FILES = {
    "json": "evidence_registry.json",
    "markdown": "evidence_registry.md",
    "html": "evidence_registry.html",
}

VALID_STATUSES = {"ACTIVE", "SUPERSEDED", "EXPIRED", "RETIRED"}
VALID_EVIDENCE_TYPES = {
    "FUNDAMENTAL", "FINANCIAL", "EARNINGS", "NEWS", "TECHNICAL",
    "MARKET", "SECTOR", "MACRO", "PORTFOLIO", "POLICY", "THESIS",
    "DECISION", "RISK", "LEARNING", "OTHER",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else []


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _stable_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _new_evidence_id(record: Mapping[str, Any]) -> str:
    seed = _stable_hash(record)
    return f"E-{seed[:12].upper()}-{uuid.uuid4().hex[:8].upper()}"


def build_evidence_record(
    *,
    evidence_type: str,
    title: str,
    summary: str,
    source: str,
    observed_at: str,
    confidence: float,
    symbol: Optional[str] = None,
    sector: Optional[str] = None,
    related_thesis_ids: Optional[Sequence[str]] = None,
    related_policy_ids: Optional[Sequence[str]] = None,
    related_market_era_ids: Optional[Sequence[str]] = None,
    expires_at: Optional[str] = None,
    review_at: Optional[str] = None,
    supersedes_evidence_id: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    kind = str(evidence_type).upper().strip()
    if kind not in VALID_EVIDENCE_TYPES:
        raise ValueError(f"Unsupported evidence_type: {evidence_type}")
    if not str(title).strip() or not str(summary).strip() or not str(source).strip():
        raise ValueError("title, summary, and source are required")
    confidence_value = max(0.0, min(100.0, _number(confidence)))
    base = {
        "evidence_type": kind,
        "title": str(title).strip(),
        "summary": str(summary).strip(),
        "source": str(source).strip(),
        "observed_at": str(observed_at),
        "confidence": round(confidence_value, 4),
        "symbol": str(symbol).upper().strip() if symbol else None,
        "sector": str(sector).strip() if sector else None,
        "related_thesis_ids": [str(v) for v in _sequence(related_thesis_ids)],
        "related_policy_ids": [str(v) for v in _sequence(related_policy_ids)],
        "related_market_era_ids": [str(v) for v in _sequence(related_market_era_ids)],
        "expires_at": expires_at,
        "review_at": review_at,
        "supersedes_evidence_id": supersedes_evidence_id,
        "metadata": dict(_mapping(metadata)),
    }
    created_at = _now()
    record = {
        "evidence_id": _new_evidence_id(base),
        "created_at_utc": created_at,
        "status": "ACTIVE",
        "immutable": True,
        **base,
    }
    record["content_hash"] = _stable_hash({k: v for k, v in record.items() if k != "content_hash"})
    return record


def validate_evidence_record(record: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ["evidence_id", "evidence_type", "title", "summary", "source", "observed_at", "confidence", "status", "immutable", "content_hash"]
    for key in required:
        if key not in record:
            errors.append(f"Missing required field: {key}")
    if str(record.get("evidence_type", "")).upper() not in VALID_EVIDENCE_TYPES:
        errors.append("Invalid evidence_type")
    if str(record.get("status", "")).upper() not in VALID_STATUSES:
        errors.append("Invalid status")
    if record.get("immutable") is not True:
        errors.append("Evidence record must be immutable")
    confidence = _number(record.get("confidence"), -1.0)
    if not 0.0 <= confidence <= 100.0:
        errors.append("confidence must be between 0 and 100")
    if not errors and "content_hash" in record:
        expected = _stable_hash({k: v for k, v in record.items() if k != "content_hash"})
        if expected != record.get("content_hash"):
            errors.append("content_hash mismatch; immutable evidence appears modified")
    return errors


def supersede_evidence(
    previous_record: Mapping[str, Any],
    *,
    evidence_type: Optional[str] = None,
    title: Optional[str] = None,
    summary: str,
    source: str,
    observed_at: str,
    confidence: float,
    metadata: Optional[Mapping[str, Any]] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    errors = validate_evidence_record(previous_record)
    if errors:
        raise ValueError("Cannot supersede invalid evidence: " + "; ".join(errors))
    old = dict(previous_record)
    old["status"] = "SUPERSEDED"
    old["superseded_at_utc"] = _now()
    old["content_hash"] = _stable_hash({k: v for k, v in old.items() if k != "content_hash"})
    new = build_evidence_record(
        evidence_type=evidence_type or str(previous_record.get("evidence_type", "OTHER")),
        title=title or str(previous_record.get("title", "Superseding Evidence")),
        summary=summary,
        source=source,
        observed_at=observed_at,
        confidence=confidence,
        symbol=previous_record.get("symbol"),
        sector=previous_record.get("sector"),
        related_thesis_ids=previous_record.get("related_thesis_ids"),
        related_policy_ids=previous_record.get("related_policy_ids"),
        related_market_era_ids=previous_record.get("related_market_era_ids"),
        expires_at=previous_record.get("expires_at"),
        review_at=previous_record.get("review_at"),
        supersedes_evidence_id=str(previous_record.get("evidence_id")),
        metadata=metadata,
    )
    return old, new


def build_evidence_registry(
    *,
    records: Optional[Sequence[Mapping[str, Any]]] = None,
    decision_links: Optional[Sequence[Mapping[str, Any]]] = None,
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    valid_records: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in _sequence(records):
        if not isinstance(raw, Mapping):
            invalid_records.append({"record": raw, "errors": ["Record must be a mapping"]})
            continue
        item = dict(raw)
        errors = validate_evidence_record(item)
        evidence_id = str(item.get("evidence_id", ""))
        if evidence_id in seen_ids:
            errors.append("Duplicate evidence_id")
        if errors:
            invalid_records.append({"evidence_id": evidence_id or None, "errors": errors})
        else:
            valid_records.append(item)
            seen_ids.add(evidence_id)

    links = [dict(v) for v in _sequence(decision_links) if isinstance(v, Mapping)]
    by_type: dict[str, int] = {}
    by_symbol: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for item in valid_records:
        by_type[item["evidence_type"]] = by_type.get(item["evidence_type"], 0) + 1
        symbol = item.get("symbol") or "UNASSIGNED"
        by_symbol[str(symbol)] = by_symbol.get(str(symbol), 0) + 1
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1

    active = [r for r in valid_records if r.get("status") == "ACTIVE"]
    avg_conf = sum(_number(r.get("confidence")) for r in active) / len(active) if active else 0.0
    linked_evidence_ids = {str(link.get("evidence_id")) for link in links if link.get("evidence_id")}
    orphan_ids = [r["evidence_id"] for r in valid_records if r["evidence_id"] not in linked_evidence_ids]

    warnings = []
    if invalid_records:
        warnings.append(f"{len(invalid_records)} invalid evidence record(s) were excluded.")
    if orphan_ids:
        warnings.append(f"{len(orphan_ids)} evidence record(s) are not linked to a decision, thesis, policy, or report.")

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at_utc or _now(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
        "immutability_enforced": True,
        "record_count": len(valid_records),
        "active_record_count": len(active),
        "invalid_record_count": len(invalid_records),
        "average_active_confidence": round(avg_conf, 4),
        "records_by_type": dict(sorted(by_type.items())),
        "records_by_symbol": dict(sorted(by_symbol.items())),
        "records_by_status": dict(sorted(by_status.items())),
        "orphan_evidence_ids": orphan_ids,
        "records": valid_records,
        "invalid_records": invalid_records,
        "decision_links": links,
        "governance": {
            "evidence_records_editable": False,
            "corrections_require_superseding_record": True,
            "original_evidence_preserved": True,
            "automatic_policy_changes_allowed": False,
            "investor_approval_required_for_strategic_changes": True,
        },
        "warnings": warnings,
        "errors": [],
    }


def find_evidence(
    registry: Mapping[str, Any],
    *,
    symbol: Optional[str] = None,
    evidence_type: Optional[str] = None,
    status: Optional[str] = "ACTIVE",
    minimum_confidence: float = 0.0,
) -> list[dict[str, Any]]:
    results = []
    for raw in _sequence(registry.get("records")):
        if not isinstance(raw, Mapping):
            continue
        if symbol and str(raw.get("symbol", "")).upper() != symbol.upper():
            continue
        if evidence_type and str(raw.get("evidence_type", "")).upper() != evidence_type.upper():
            continue
        if status and str(raw.get("status", "")).upper() != status.upper():
            continue
        if _number(raw.get("confidence")) < minimum_confidence:
            continue
        results.append(dict(raw))
    return sorted(results, key=lambda r: (str(r.get("observed_at", "")), str(r.get("evidence_id", ""))), reverse=True)


def format_evidence_registry_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# AI CIO Evidence Registry", "",
        f"**Records:** {report.get('record_count', 0)}", "",
        f"**Active Evidence:** {report.get('active_record_count', 0)}", "",
        f"**Average Active Confidence:** {_number(report.get('average_active_confidence')):.2f}%", "",
        "## Evidence Summary", "",
        "| Evidence ID | Type | Symbol | Status | Confidence | Title |", "|---|---|---|---|---:|---|",
    ]
    for item in _sequence(report.get("records")):
        if isinstance(item, Mapping):
            lines.append(
                f"| {item.get('evidence_id', '')} | {item.get('evidence_type', '')} | {item.get('symbol') or '—'} | "
                f"{item.get('status', '')} | {_number(item.get('confidence')):.2f}% | {item.get('title', '')} |"
            )
    lines.extend([
        "", "## Governance", "",
        "Evidence is immutable. New or corrected information creates a superseding record that preserves the original evidence and audit trail.",
        "", "## Warnings", "",
    ])
    warnings = _sequence(report.get("warnings"))
    lines.extend(f"- {w}" for w in warnings) if warnings else lines.append("- None")
    return "\n".join(lines) + "\n"


def format_evidence_registry_html(report: Mapping[str, Any]) -> str:
    body = html.escape(format_evidence_registry_markdown(report))
    return "<!doctype html><html><head><meta charset='utf-8'><title>AI CIO Evidence Registry</title><style>body{font-family:Arial,sans-serif;max-width:1200px;margin:0 auto;padding:32px;background:#f5f7fb;color:#172033}pre{white-space:pre-wrap;background:white;padding:28px;border-radius:14px;box-shadow:0 4px 18px rgba(0,0,0,.08);line-height:1.5}</style></head><body><pre>" + body + "</pre></body></html>"


def write_evidence_registry(payload: Mapping[str, Any], root_path: str = ".", output_files: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    report = build_evidence_registry(**dict(payload))
    root = Path(root_path)
    root.mkdir(parents=True, exist_ok=True)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    (root / files["json"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_evidence_registry_markdown(report), encoding="utf-8")
    (root / files["html"]).write_text(format_evidence_registry_html(report), encoding="utf-8")
    return report


def build_and_write_evidence_registry(payload: Mapping[str, Any], root_path: str = ".", output_files: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    return write_evidence_registry(payload, root_path, output_files)


if __name__ == "__main__":
    sample = build_evidence_record(
        evidence_type="EARNINGS",
        title="AMD quarterly earnings update",
        summary="Revenue and guidance improved versus the prior quarter.",
        source="Company earnings release",
        observed_at="2026-07-14T20:05:00Z",
        confidence=94.0,
        symbol="AMD",
        sector="Technology",
        review_at="2026-10-15",
    )
    result = write_evidence_registry({"records": [sample], "decision_links": [{"evidence_id": sample["evidence_id"], "decision_id": "D-001"}]})
    print(f"Evidence Registry: {result['record_count']} record(s)")
