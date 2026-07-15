"""AI CIO Decision Record v1.0.

Standardized, paper-only institutional decision records shared across governance,
executive, investment, research, risk, and learning modules.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4

MODULE_NAME = "ai_cio_decision_record"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

DECISION_TYPES = {
    "PROMOTION", "DEMOTION", "REJECTION", "OBSERVATION_EXTENSION",
    "WATCHLIST_ADMISSION", "WATCHLIST_REMOVAL", "PORTFOLIO_RECOMMENDATION",
    "REPLACEMENT_REVIEW", "POLICY_PROPOSAL", "POLICY_APPROVAL",
    "POLICY_REJECTION", "CONSTITUTION_REVIEW", "ARCHIVE_ACTION",
    "RESEARCH_ESCALATION", "RISK_ACTION", "OTHER",
}
DECISION_STATUSES = {"PROPOSED", "UNDER_REVIEW", "APPROVED", "REJECTED", "DEFERRED", "COMPLETED", "SUPERSEDED"}
GOVERNANCE_STATUSES = {"NOT_REQUIRED", "PASS", "NOTICE", "WARNING", "FAIL", "PENDING"}
CLASSIFICATIONS = {"ROUTINE", "SIGNIFICANT", "STRATEGIC", "CONSTITUTIONAL"}
OUTCOMES = {"PENDING", "SUCCESSFUL", "PARTIALLY_SUCCESSFUL", "UNSUCCESSFUL", "NOT_APPLICABLE"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean_text(value: Any, name: str, *, required: bool = True) -> str:
    text = "" if value is None else str(value).strip()
    if required and not text:
        raise ValueError(f"{name} is required")
    return text


def _score(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if result < 0 or result > 100:
        raise ValueError(f"{name} must be between 0 and 100")
    return round(result, 2)


def _string_list(values: Iterable[Any] | None) -> list[str]:
    if values is None:
        return []
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def _canonical_payload(data: Mapping[str, Any]) -> str:
    excluded = {"record_hash", "updated_at"}
    payload = {key: value for key, value in data.items() if key not in excluded}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    timestamp: str
    originating_module: str
    decision_type: str
    title: str
    summary: str
    classification: str = "ROUTINE"
    status: str = "PROPOSED"
    symbol: str = ""
    underlying_symbol: str = ""
    sector: str = ""
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    related_decision_ids: tuple[str, ...] = field(default_factory=tuple)
    related_reports: tuple[str, ...] = field(default_factory=tuple)
    rationale: tuple[str, ...] = field(default_factory=tuple)
    risks: tuple[str, ...] = field(default_factory=tuple)
    alternatives_considered: tuple[str, ...] = field(default_factory=tuple)
    confidence_score: float = 0.0
    governance_status: str = "NOT_REQUIRED"
    investor_approval_required: bool = False
    investor_action: str = "NONE"
    final_outcome: str = "PENDING"
    outcome_notes: str = ""
    lessons_learned: tuple[str, ...] = field(default_factory=tuple)
    supersedes_decision_id: str = ""
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False
    schema_version: str = SCHEMA_VERSION
    module_version: str = MODULE_VERSION
    record_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in (
            "evidence_ids", "related_decision_ids", "related_reports", "rationale",
            "risks", "alternatives_considered", "lessons_learned",
        ):
            data[key] = list(data[key])
        return data


def build_decision_record(
    *,
    originating_module: str,
    decision_type: str,
    title: str,
    summary: str,
    classification: str = "ROUTINE",
    status: str = "PROPOSED",
    symbol: str = "",
    underlying_symbol: str = "",
    sector: str = "",
    evidence_ids: Sequence[str] | None = None,
    related_decision_ids: Sequence[str] | None = None,
    related_reports: Sequence[str] | None = None,
    rationale: Sequence[str] | None = None,
    risks: Sequence[str] | None = None,
    alternatives_considered: Sequence[str] | None = None,
    confidence_score: float = 0.0,
    governance_status: str = "NOT_REQUIRED",
    investor_approval_required: bool = False,
    investor_action: str = "NONE",
    final_outcome: str = "PENDING",
    outcome_notes: str = "",
    lessons_learned: Sequence[str] | None = None,
    supersedes_decision_id: str = "",
    decision_id: str | None = None,
    timestamp: str | None = None,
) -> DecisionRecord:
    decision_type = _clean_text(decision_type, "decision_type").upper()
    classification = _clean_text(classification, "classification").upper()
    status = _clean_text(status, "status").upper()
    governance_status = _clean_text(governance_status, "governance_status").upper()
    final_outcome = _clean_text(final_outcome, "final_outcome").upper()
    if decision_type not in DECISION_TYPES:
        raise ValueError(f"unsupported decision_type: {decision_type}")
    if classification not in CLASSIFICATIONS:
        raise ValueError(f"unsupported classification: {classification}")
    if status not in DECISION_STATUSES:
        raise ValueError(f"unsupported status: {status}")
    if governance_status not in GOVERNANCE_STATUSES:
        raise ValueError(f"unsupported governance_status: {governance_status}")
    if final_outcome not in OUTCOMES:
        raise ValueError(f"unsupported final_outcome: {final_outcome}")
    if classification == "CONSTITUTIONAL" and not investor_approval_required:
        raise ValueError("constitutional decisions require investor approval")
    if governance_status == "FAIL" and status in {"APPROVED", "COMPLETED"}:
        raise ValueError("a failed governance review cannot be approved or completed")

    payload: dict[str, Any] = {
        "decision_id": decision_id or f"DEC-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:12].upper()}",
        "timestamp": timestamp or _utc_now(),
        "originating_module": _clean_text(originating_module, "originating_module"),
        "decision_type": decision_type,
        "title": _clean_text(title, "title"),
        "summary": _clean_text(summary, "summary"),
        "classification": classification,
        "status": status,
        "symbol": str(symbol or "").strip().upper(),
        "underlying_symbol": str(underlying_symbol or "").strip().upper(),
        "sector": str(sector or "").strip(),
        "evidence_ids": tuple(_string_list(evidence_ids)),
        "related_decision_ids": tuple(_string_list(related_decision_ids)),
        "related_reports": tuple(_string_list(related_reports)),
        "rationale": tuple(_string_list(rationale)),
        "risks": tuple(_string_list(risks)),
        "alternatives_considered": tuple(_string_list(alternatives_considered)),
        "confidence_score": _score(confidence_score, "confidence_score"),
        "governance_status": governance_status,
        "investor_approval_required": bool(investor_approval_required),
        "investor_action": str(investor_action or "NONE").strip().upper(),
        "final_outcome": final_outcome,
        "outcome_notes": str(outcome_notes or "").strip(),
        "lessons_learned": tuple(_string_list(lessons_learned)),
        "supersedes_decision_id": str(supersedes_decision_id or "").strip(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "schema_version": SCHEMA_VERSION,
        "module_version": MODULE_VERSION,
        "record_hash": "",
    }
    payload["record_hash"] = sha256(_canonical_payload(payload).encode("utf-8")).hexdigest()
    return DecisionRecord(**payload)


def validate_decision_record(record: DecisionRecord | Mapping[str, Any]) -> list[str]:
    data = record.to_dict() if isinstance(record, DecisionRecord) else dict(record)
    errors: list[str] = []
    for name in ("decision_id", "timestamp", "originating_module", "decision_type", "title", "summary"):
        if not str(data.get(name, "")).strip():
            errors.append(f"missing {name}")
    if data.get("decision_type") not in DECISION_TYPES:
        errors.append("invalid decision_type")
    if data.get("classification") not in CLASSIFICATIONS:
        errors.append("invalid classification")
    if data.get("status") not in DECISION_STATUSES:
        errors.append("invalid status")
    if data.get("governance_status") not in GOVERNANCE_STATUSES:
        errors.append("invalid governance_status")
    if data.get("final_outcome") not in OUTCOMES:
        errors.append("invalid final_outcome")
    try:
        _score(data.get("confidence_score"), "confidence_score")
    except ValueError as exc:
        errors.append(str(exc))
    if data.get("paper_trade_mode") is not True:
        errors.append("paper_trade_mode must be True")
    if data.get("live_trading_enabled") is not False:
        errors.append("live_trading_enabled must be False")
    if data.get("broker_execution_enabled") is not False:
        errors.append("broker_execution_enabled must be False")
    expected_hash = sha256(_canonical_payload(data).encode("utf-8")).hexdigest()
    if data.get("record_hash") != expected_hash:
        errors.append("record hash mismatch")
    return errors


def build_decision_register(records: Sequence[DecisionRecord | Mapping[str, Any]]) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in records:
        data = item.to_dict() if isinstance(item, DecisionRecord) else dict(item)
        decision_id = str(data.get("decision_id", ""))
        errors = validate_decision_record(data)
        if decision_id in seen:
            errors.append("duplicate decision_id")
        seen.add(decision_id)
        if errors:
            invalid.append({"decision_id": decision_id, "errors": errors})
        else:
            normalized.append(data)
    normalized.sort(key=lambda row: (row.get("timestamp", ""), row.get("decision_id", "")), reverse=True)
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "record_count": len(normalized),
        "invalid_record_count": len(invalid),
        "approval_required_count": sum(bool(row.get("investor_approval_required")) for row in normalized),
        "open_decision_count": sum(row.get("status") in {"PROPOSED", "UNDER_REVIEW", "DEFERRED"} for row in normalized),
        "records": normalized,
        "invalid_records": invalid,
    }


def render_markdown(register: Mapping[str, Any]) -> str:
    lines = [
        "# AI CIO Decision Register",
        "",
        f"- Records: {register.get('record_count', 0)}",
        f"- Invalid Records: {register.get('invalid_record_count', 0)}",
        f"- Open Decisions: {register.get('open_decision_count', 0)}",
        f"- Investor Approval Required: {register.get('approval_required_count', 0)}",
        "- Mode: Paper-only",
        "",
        "## Decisions",
        "",
        "| Decision ID | Time | Module | Type | Security | Classification | Status | Confidence | Governance | Approval |",
        "|---|---|---|---|---|---|---|---:|---|---|",
    ]
    for row in register.get("records", []):
        lines.append(
            f"| {row['decision_id']} | {row['timestamp']} | {row['originating_module']} | "
            f"{row['decision_type']} | {row.get('symbol') or '—'} | {row['classification']} | "
            f"{row['status']} | {row['confidence_score']:.2f}% | {row['governance_status']} | "
            f"{'Yes' if row['investor_approval_required'] else 'No'} |"
        )
        lines.extend(["", f"### {row['title']}", "", row["summary"], ""])
        if row.get("rationale"):
            lines.append("**Rationale:** " + "; ".join(row["rationale"]))
        if row.get("risks"):
            lines.append("**Risks:** " + "; ".join(row["risks"]))
        if row.get("evidence_ids"):
            lines.append("**Evidence:** " + ", ".join(row["evidence_ids"]))
        lines.append("")
    if register.get("invalid_records"):
        lines.extend(["## Invalid Records", ""])
        for row in register["invalid_records"]:
            lines.append(f"- {row.get('decision_id') or '(unknown)'}: {', '.join(row['errors'])}")
    return "\n".join(lines).rstrip() + "\n"


def render_html(register: Mapping[str, Any]) -> str:
    rows = []
    details = []
    for row in register.get("records", []):
        rows.append(
            "<tr>"
            f"<td>{escape(row['decision_id'])}</td><td>{escape(row['timestamp'])}</td>"
            f"<td>{escape(row['originating_module'])}</td><td>{escape(row['decision_type'])}</td>"
            f"<td>{escape(row.get('symbol') or '—')}</td><td>{escape(row['classification'])}</td>"
            f"<td>{escape(row['status'])}</td><td>{row['confidence_score']:.2f}%</td>"
            f"<td>{escape(row['governance_status'])}</td>"
            f"<td>{'Yes' if row['investor_approval_required'] else 'No'}</td></tr>"
        )
        detail_items = "".join(f"<li>{escape(x)}</li>" for x in row.get("rationale", [])) or "<li>None recorded</li>"
        details.append(
            f"<details><summary>{escape(row['title'])} — More...</summary>"
            f"<p>{escape(row['summary'])}</p><h4>Rationale</h4><ul>{detail_items}</ul>"
            f"<p><strong>Evidence:</strong> {escape(', '.join(row.get('evidence_ids', [])) or 'None')}</p>"
            f"<p><strong>Outcome:</strong> {escape(row['final_outcome'])}</p></details>"
        )
    return f"""<!doctype html><html><head><meta charset=\"utf-8\"><title>AI CIO Decision Register</title>
<style>body{{font-family:Arial,sans-serif;margin:2rem;line-height:1.45}}.cards{{display:flex;gap:1rem;flex-wrap:wrap}}.card{{border:1px solid #ccc;border-radius:8px;padding:1rem;min-width:160px}}table{{border-collapse:collapse;width:100%;margin-top:1rem}}th,td{{border:1px solid #ccc;padding:.5rem;text-align:left}}details{{margin:1rem 0;padding:.75rem;border:1px solid #ddd;border-radius:6px}}.notice{{padding:1rem;border:1px solid #999;border-radius:6px}}</style></head><body>
<h1>AI CIO Decision Register</h1><div class=\"cards\"><div class=\"card\"><strong>Records</strong><br>{register.get('record_count',0)}</div><div class=\"card\"><strong>Open</strong><br>{register.get('open_decision_count',0)}</div><div class=\"card\"><strong>Approval Required</strong><br>{register.get('approval_required_count',0)}</div><div class=\"card\"><strong>Invalid</strong><br>{register.get('invalid_record_count',0)}</div></div>
<p class=\"notice\"><strong>Governance:</strong> This register records paper-only institutional decisions. It cannot place orders, bypass constitutional controls, or approve strategic changes without required investor authority.</p>
<table><thead><tr><th>Decision ID</th><th>Time</th><th>Module</th><th>Type</th><th>Security</th><th>Classification</th><th>Status</th><th>Confidence</th><th>Governance</th><th>Approval</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Decision Details</h2>{''.join(details)}</body></html>"""


def write_decision_register(
    register: Mapping[str, Any],
    output_dir: str | Path = ".",
    basename: str = "ai_cio_decision_register",
) -> dict[str, str]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": directory / f"{basename}.json",
        "markdown": directory / f"{basename}.md",
        "html": directory / f"{basename}.html",
    }
    paths["json"].write_text(json.dumps(register, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths["markdown"].write_text(render_markdown(register), encoding="utf-8")
    paths["html"].write_text(render_html(register), encoding="utf-8")
    return {key: str(path) for key, path in paths.items()}


def build_and_write_decision_register(
    records: Sequence[DecisionRecord | Mapping[str, Any]],
    output_dir: str | Path = ".",
    basename: str = "ai_cio_decision_register",
) -> tuple[dict[str, Any], dict[str, str]]:
    register = build_decision_register(records)
    return register, write_decision_register(register, output_dir, basename)


def _sample() -> list[DecisionRecord]:
    return [
        build_decision_record(
            originating_module="research_intelligence_engine",
            decision_type="RESEARCH_ESCALATION",
            title="Begin deeper analysis of XYZ Robotics",
            summary="Multiple independent sources identified the company; deeper evidence review is warranted.",
            classification="SIGNIFICANT",
            status="APPROVED",
            symbol="XYZR",
            evidence_ids=["E-RESEARCH-001", "E-NEWS-004"],
            rationale=["Research consensus is rising", "Internal evidence agreement is improving"],
            risks=["Limited public history", "IPO lock-up remains active"],
            confidence_score=86,
            governance_status="PASS",
            final_outcome="NOT_APPLICABLE",
        ),
        build_decision_record(
            originating_module="policy_simulator",
            decision_type="POLICY_PROPOSAL",
            title="Review replacement threshold candidate",
            summary="A candidate policy demonstrated a material simulated Total Wealth improvement and requires governance review.",
            classification="CONSTITUTIONAL",
            status="UNDER_REVIEW",
            evidence_ids=["E-POLICY-102"],
            rationale=["Simulated Total Wealth improvement exceeded 5%"],
            alternatives_considered=["Maintain current policy", "Extend shadow validation"],
            confidence_score=94,
            governance_status="PENDING",
            investor_approval_required=True,
            investor_action="REVIEW",
        ),
    ]


if __name__ == "__main__":
    report, files = build_and_write_decision_register(_sample())
    print(f"Decision register generated: {report['record_count']} records")
    for kind, path in files.items():
        print(f"{kind}: {path}")
