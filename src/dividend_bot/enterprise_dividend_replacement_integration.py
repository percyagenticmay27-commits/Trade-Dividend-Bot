"""Governed dividend replacement analysis for the Trade Dividend Bot.

Compares weakening paper-only holdings with stronger candidate opportunities.
This module is advisory and reporting only. It cannot sell, buy, place orders,
communicate with a broker, or move capital.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "enterprise_dividend_replacement_integration"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ADVISORY_ONLY = True
HUMAN_APPROVAL_REQUIRED = True

RECOMMENDATION_TYPES = {"HOLD", "REVIEW", "REPLACEMENT_REVIEW"}
DEFAULT_OUTPUT_FILES = {
    "json": "enterprise_dividend_replacement_analysis.json",
    "markdown": "enterprise_dividend_replacement_analysis.md",
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    text = str(value or default).strip()
    return text.upper() if text else default


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _first(mapping: Mapping[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _stable_id(current_symbol: str, candidate_symbol: str, period: str) -> str:
    raw = f"{current_symbol}|{candidate_symbol}|{period}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()
    return f"DIV-REPL-{digest}"


def _normalized_holding(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **dict(item),
        "symbol": _upper(_first(item, ("symbol", "ticker", "asset"), "UNKNOWN")),
        "projected_annual_income": round(_number(_first(item, ("projected_annual_income", "annual_income", "annual_dividend_income"), 0.0)), 2),
        "yield_percent": round(_number(_first(item, ("yield_percent", "dividend_yield", "current_yield_percent"), 0.0)), 4),
        "confidence_score": round(_number(_first(item, ("confidence_score", "confidence"), 0.0)), 2),
        "quality_score": round(_number(_first(item, ("quality_score", "opportunity_quality", "score"), 0.0)), 2),
        "risk_score": round(_number(_first(item, ("risk_score", "portfolio_risk_score"), 50.0)), 2),
        "income_growth_percent": round(_number(_first(item, ("income_growth_percent", "dividend_growth_percent"), 0.0)), 4),
    }


def _weakness_score(item: Mapping[str, Any]) -> float:
    alerts = {_upper(x) for x in item.get("alert_types", []) if str(x).strip()}
    recommendation = _upper(item.get("cio_recommendation"), "HOLD")
    score = 0.0
    if "DIVIDEND_SUSPENSION" in alerts:
        score += 100
    if "DIVIDEND_CUT" in alerts:
        score += 55
    if "MISSED_PAYMENT" in alerts:
        score += 45
    if "NEGATIVE_INCOME_GROWTH" in alerts or _number(item.get("income_growth_percent")) < 0:
        score += 25
    if _number(item.get("confidence_score")) < 50:
        score += 20
    if recommendation in {"EXIT_REVIEW", "REPLACEMENT_REVIEW"}:
        score += 35
    elif recommendation == "REDUCE":
        score += 20
    return round(score, 2)


def _candidate_score(item: Mapping[str, Any]) -> float:
    quality = _number(item.get("quality_score"))
    confidence = _number(item.get("confidence_score"))
    growth = max(-20.0, min(30.0, _number(item.get("income_growth_percent"))))
    yield_percent = max(0.0, min(15.0, _number(item.get("yield_percent"))))
    risk = max(0.0, min(100.0, _number(item.get("risk_score"), 50.0)))
    score = quality * 0.35 + confidence * 0.30 + (growth + 20.0) * 0.40 + yield_percent * 1.0 + (100.0 - risk) * 0.15
    return round(max(0.0, min(100.0, score)), 2)


def build_enterprise_dividend_replacement_analysis(
    *,
    governed_holdings: Optional[Sequence[Mapping[str, Any]]] = None,
    replacement_candidates: Optional[Sequence[Mapping[str, Any]]] = None,
    cio_recommendations: Optional[Sequence[Mapping[str, Any]]] = None,
    alerts: Optional[Sequence[Mapping[str, Any]]] = None,
    reviews: Optional[Sequence[Mapping[str, Any]]] = None,
    reporting_period: str = "CURRENT",
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Build governed holding-versus-candidate comparisons without execution."""
    generated_at = generated_at_utc or _now_utc()
    warnings: list[str] = []
    holdings = [_normalized_holding(row) for row in _rows(governed_holdings or [])]
    candidates = [_normalized_holding(row) for row in _rows(replacement_candidates or [])]
    if not holdings:
        warnings.append("Governed holdings were not supplied.")
    if not candidates:
        warnings.append("Replacement candidates were not supplied.")

    cio_by_symbol = {_upper(row.get("symbol")): row for row in _rows(cio_recommendations or [])}
    alert_types_by_symbol: dict[str, list[str]] = {}
    alert_ids_by_symbol: dict[str, list[str]] = {}
    for row in _rows(alerts or []):
        symbol = _upper(row.get("symbol"))
        alert_types_by_symbol.setdefault(symbol, []).append(_upper(row.get("alert_type")))
        if row.get("alert_id"):
            alert_ids_by_symbol.setdefault(symbol, []).append(str(row["alert_id"]))
    review_ids_by_symbol: dict[str, list[str]] = {}
    for row in _rows(reviews or []):
        symbol = _upper(row.get("symbol"))
        if row.get("review_id"):
            review_ids_by_symbol.setdefault(symbol, []).append(str(row["review_id"]))

    for holding in holdings:
        symbol = holding["symbol"]
        cio = cio_by_symbol.get(symbol, {})
        holding["cio_recommendation"] = _upper(cio.get("recommendation"), "HOLD")
        holding["alert_types"] = sorted(set(alert_types_by_symbol.get(symbol, [])))
        holding["alert_ids"] = sorted(set(alert_ids_by_symbol.get(symbol, [])))
        holding["review_ids"] = sorted(set(review_ids_by_symbol.get(symbol, [])))
        holding["weakness_score"] = _weakness_score(holding)

    for candidate in candidates:
        candidate["candidate_score"] = _candidate_score(candidate)

    comparisons: list[dict[str, Any]] = []
    for holding in holdings:
        weakness = _number(holding.get("weakness_score"))
        eligible = [c for c in candidates if c["symbol"] != holding["symbol"]]
        eligible.sort(key=lambda row: (-_number(row.get("candidate_score")), row["symbol"]))
        best = eligible[0] if eligible else None
        if not best:
            recommendation = "REVIEW" if weakness > 0 else "HOLD"
            advantage = 0.0
        else:
            advantage = round(_number(best.get("candidate_score")) - max(0.0, 100.0 - weakness), 2)
            recommendation = "REPLACEMENT_REVIEW" if weakness >= 35 and advantage >= 5 else "REVIEW" if weakness > 0 else "HOLD"
        comparisons.append({
            "comparison_id": _stable_id(holding["symbol"], best["symbol"] if best else "NONE", reporting_period),
            "current_symbol": holding["symbol"],
            "candidate_symbol": best["symbol"] if best else None,
            "recommendation": recommendation,
            "approval_status": "PENDING_INVESTOR_APPROVAL",
            "weakness_score": weakness,
            "candidate_score": _number(best.get("candidate_score")) if best else 0.0,
            "candidate_advantage_score": advantage,
            "current_holding": holding,
            "candidate": best,
            "source_alert_ids": holding.get("alert_ids", []),
            "source_review_ids": holding.get("review_ids", []),
            "governance_note": "Comparison is advisory only. Investor approval is required before any paper portfolio change.",
        })

    priority = {"REPLACEMENT_REVIEW": 0, "REVIEW": 1, "HOLD": 2}
    comparisons.sort(key=lambda row: (priority[row["recommendation"]], -row["weakness_score"], row["current_symbol"]))
    counts = {name.lower(): sum(1 for row in comparisons if row["recommendation"] == name) for name in RECOMMENDATION_TYPES}
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "reporting_period": reporting_period,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "advisory_only": True,
        "human_approval_required": True,
        "status": "READY" if holdings and candidates else "PARTIAL",
        "summary": {
            "holding_count": len(holdings),
            "candidate_count": len(candidates),
            "comparison_count": len(comparisons),
            **counts,
        },
        "comparisons": comparisons,
        "warnings": warnings,
    }


def render_enterprise_dividend_replacement_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Enterprise Dividend Replacement Analysis",
        "",
        f"- Generated: {report.get('generated_at_utc', '')}",
        f"- Status: {report.get('status', 'UNKNOWN')}",
        f"- Paper Trade Mode: {report.get('paper_trade_mode', False)}",
        f"- Human Approval Required: {report.get('human_approval_required', True)}",
        "",
        "## Summary",
        "",
        f"- Holdings: {summary.get('holding_count', 0)}",
        f"- Candidates: {summary.get('candidate_count', 0)}",
        f"- Replacement Reviews: {summary.get('replacement_review', 0)}",
        f"- Reviews: {summary.get('review', 0)}",
        f"- Holds: {summary.get('hold', 0)}",
        "",
        "## Comparisons",
        "",
    ]
    for row in report.get("comparisons", []):
        lines.extend([
            f"### {row.get('current_symbol')} → {row.get('candidate_symbol') or 'No Candidate'}",
            "",
            f"- Recommendation: {row.get('recommendation')}",
            f"- Approval Status: {row.get('approval_status')}",
            f"- Weakness Score: {row.get('weakness_score')}",
            f"- Candidate Score: {row.get('candidate_score')}",
            f"- Candidate Advantage: {row.get('candidate_advantage_score')}",
            "",
        ])
    if report.get("warnings"):
        lines.extend(["## Warnings", ""] + [f"- {item}" for item in report["warnings"]] + [""])
    lines.extend(["## Governance", "", "No sale, purchase, allocation change, or capital movement is authorized by this report.", ""])
    return "\n".join(lines)


def write_enterprise_dividend_replacement_outputs(report: Mapping[str, Any], output_dir: str | Path) -> dict[str, str]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / DEFAULT_OUTPUT_FILES["json"]
    markdown_path = directory / DEFAULT_OUTPUT_FILES["markdown"]
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_enterprise_dividend_replacement_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def build_and_write_enterprise_dividend_replacement_analysis(output_dir: str | Path, **kwargs: Any) -> dict[str, Any]:
    report = build_enterprise_dividend_replacement_analysis(**kwargs)
    report["output_files"] = write_enterprise_dividend_replacement_outputs(report, output_dir)
    return report
