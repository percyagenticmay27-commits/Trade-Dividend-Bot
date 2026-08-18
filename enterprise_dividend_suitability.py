"""Fail-closed Dividend vehicle suitability gate.

Consumes reviewed Dividend income mappings plus separately reviewed suitability
metrics. Produces advisory paper-review classifications only.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "1.0"
STRATEGY_ID = "DIVIDEND-001"
STATUSES = {"ELIGIBLE_FOR_PAPER_REVIEW", "WATCH_ONLY", "REJECTED", "EVIDENCE_REQUIRED"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return dict(value)


def _symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()
    if not symbol or not symbol.replace(".", "").replace("-", "").isalnum():
        raise ValueError("invalid income symbol")
    return symbol


def validate_mapping_report(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("strategy_id") != STRATEGY_ID:
        raise ValueError("mapping report must be schema 1.0 / DIVIDEND-001")
    required_locks = {
        "paper_trade_mode": True,
        "advisory_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "order_placement_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
    }
    if any(payload.get(key) is not expected for key, expected in required_locks.items()):
        raise ValueError("mapping report execution locks are not preserved")
    rows = payload.get("candidates")
    if not isinstance(rows, list):
        raise ValueError("mapping report candidates must be a list")
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def validate_evidence_catalog(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("strategy_id") != STRATEGY_ID:
        raise ValueError("suitability catalog must be schema 1.0 / DIVIDEND-001")
    rows = payload.get("vehicles")
    if not isinstance(rows, list):
        raise ValueError("suitability catalog vehicles must be a list")
    result: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise ValueError("suitability evidence must be an object")
        symbol = _symbol(raw.get("income_symbol"))
        if raw.get("reviewed") is not True:
            raise ValueError(f"{symbol} suitability evidence must be reviewed")
        as_of = date.fromisoformat(str(raw.get("evidence_as_of") or ""))
        sources = raw.get("sources")
        if not isinstance(sources, list) or not sources:
            raise ValueError(f"{symbol} suitability evidence requires sources")
        if any(not str(item.get("source_url") or "").startswith("https://") for item in sources if isinstance(item, Mapping)):
            raise ValueError(f"{symbol} suitability sources must use HTTPS")
        if len([item for item in sources if isinstance(item, Mapping)]) != len(sources):
            raise ValueError(f"{symbol} suitability sources must be objects")
        if symbol in result:
            raise ValueError(f"duplicate suitability evidence: {symbol}")
        result[symbol] = {**dict(raw), "income_symbol": symbol, "evidence_as_of": as_of.isoformat()}
    return result


def _number(row: Mapping[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{row.get('income_symbol')} {key} must be numeric or null")


def _assess(mapping: Mapping[str, Any], evidence: Mapping[str, Any] | None, generated: date) -> dict[str, Any]:
    if not evidence:
        return {"suitability_status": "EVIDENCE_REQUIRED", "suitability_score": None,
                "decision_reasons": ["No separately reviewed suitability evidence is available."],
                "evidence_as_of": None, "evidence_sources": []}
    age = (generated - date.fromisoformat(evidence["evidence_as_of"])).days
    if age < 0 or age > 45:
        return {"suitability_status": "EVIDENCE_REQUIRED", "suitability_score": None,
                "decision_reasons": ["Reviewed suitability evidence is stale or future-dated."],
                "evidence_as_of": evidence["evidence_as_of"], "evidence_sources": evidence["sources"]}

    mapping_type = str(mapping.get("mapping_type") or "")
    required = ["latest_dollar_volume", "total_return_1y_percent"]
    if mapping_type == "INCOME_ETF":
        required += ["expense_ratio_percent", "latest_distribution_roc_percent", "fund_age_days"]
    else:
        required += ["forward_dividend_yield_percent", "dividend_cut_last_12m"]
    if any(evidence.get(key) is None for key in required):
        return {"suitability_status": "EVIDENCE_REQUIRED", "suitability_score": None,
                "decision_reasons": ["One or more required reviewed suitability metrics are unavailable."],
                "evidence_as_of": evidence["evidence_as_of"], "evidence_sources": evidence["sources"]}

    score = 100
    reasons: list[str] = []
    liquidity = _number(evidence, "latest_dollar_volume")
    total_return = _number(evidence, "total_return_1y_percent")
    hard_reject = False
    if liquidity is not None and liquidity < 250_000:
        hard_reject = True
        reasons.append("Latest dollar volume is below the $250,000 minimum.")
    elif liquidity is not None and liquidity < 1_000_000:
        score -= 20
        reasons.append("Latest dollar volume is below $1,000,000.")
    if total_return is not None and total_return <= -40:
        hard_reject = True
        reasons.append("One-year total return is at or below -40%.")
    elif total_return is not None and total_return < 0:
        score -= 30
        reasons.append("One-year total return is negative.")

    if mapping_type == "INCOME_ETF":
        expense = _number(evidence, "expense_ratio_percent")
        roc = _number(evidence, "latest_distribution_roc_percent")
        fund_age = _number(evidence, "fund_age_days")
        if expense is not None and expense > 1.0:
            score -= 10
            reasons.append("Expense ratio exceeds 1.00%.")
        if roc is not None and roc >= 90:
            score -= 35
            reasons.append("Latest distribution is at least 90% estimated return of capital.")
        elif roc is not None and roc >= 50:
            score -= 20
            reasons.append("Latest distribution is at least 50% estimated return of capital.")
        if fund_age is not None and fund_age < 365:
            score -= 10
            reasons.append("Fund has less than one year of operating history.")
    else:
        dividend_yield = _number(evidence, "forward_dividend_yield_percent")
        if dividend_yield is not None and dividend_yield < 1.0:
            score -= 35
            reasons.append("Forward dividend yield is below 1.00%.")
        elif dividend_yield is not None and dividend_yield < 2.0:
            score -= 15
            reasons.append("Forward dividend yield is below 2.00%.")
        if bool(evidence.get("dividend_cut_last_12m")):
            score -= 50
            reasons.append("A dividend cut occurred within the last 12 months.")

    score = max(0, score)
    status = "REJECTED" if hard_reject else "ELIGIBLE_FOR_PAPER_REVIEW" if score >= 70 else "WATCH_ONLY"
    if not reasons:
        reasons.append("Reviewed evidence passed the current conservative paper-review thresholds.")
    return {"suitability_status": status, "suitability_score": score,
            "decision_reasons": reasons, "evidence_as_of": evidence["evidence_as_of"],
            "evidence_sources": evidence["sources"]}


def build_suitability_report(mapping_report: Mapping[str, Any], evidence_catalog: Mapping[str, Any],
                             *, generated_at: str | None = None) -> dict[str, Any]:
    mappings = validate_mapping_report(mapping_report)
    evidence = validate_evidence_catalog(evidence_catalog)
    stamp = generated_at or _now()
    generated = datetime.fromisoformat(stamp.replace("Z", "+00:00")).date()
    candidates = []
    for mapping in mappings:
        income = mapping.get("income_symbol")
        reviewed_evidence = evidence.get(_symbol(income)) if income else None
        assessed = _assess(mapping, reviewed_evidence, generated)
        candidates.append({
            **mapping,
            **assessed,
            "suitability_evidence": dict(reviewed_evidence) if reviewed_evidence else None,
            "paper_review_allowed": assessed["suitability_status"] == "ELIGIBLE_FOR_PAPER_REVIEW",
            "automatic_activation_allowed": False,
        })
    return {
        "schema_version": SCHEMA_VERSION, "strategy_id": STRATEGY_ID, "generated_at": stamp,
        "paper_trade_mode": True, "advisory_only": True, "live_trading_enabled": False,
        "broker_execution_enabled": False, "order_placement_enabled": False,
        "capital_movement_enabled": False, "automatic_activation_allowed": False,
        "candidate_count": len(candidates),
        "eligible_for_paper_review_count": sum(r["suitability_status"] == "ELIGIBLE_FOR_PAPER_REVIEW" for r in candidates),
        "watch_only_count": sum(r["suitability_status"] == "WATCH_ONLY" for r in candidates),
        "rejected_count": sum(r["suitability_status"] == "REJECTED" for r in candidates),
        "evidence_required_count": sum(r["suitability_status"] == "EVIDENCE_REQUIRED" for r in candidates),
        "candidates": candidates,
    }


def write_suitability_report(mapping_path: str | Path, evidence_path: str | Path,
                             output_path: str | Path) -> dict[str, Any]:
    report = build_suitability_report(_load(mapping_path), _load(evidence_path))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
