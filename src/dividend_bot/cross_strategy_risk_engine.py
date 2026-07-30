"""Advisory paper-only cross-strategy portfolio risk assessment."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "cross_strategy_risk_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: str | Path, *, required: bool) -> tuple[dict[str, Any], list[str]]:
    source = Path(path)
    if not source.is_file():
        if required:
            raise FileNotFoundError(str(source))
        return {}, [f"missing optional input: {source.name}"]
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        if required:
            raise ValueError(f"invalid required input {source.name}: {exc}") from exc
        return {}, [f"invalid optional input {source.name}: {exc}"]
    if not isinstance(value, dict):
        if required:
            raise ValueError(f"invalid required input {source.name}: root must be an object")
        return {}, [f"invalid optional input {source.name}: root must be an object"]
    return value, []


def _allocations(manager: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("recommendations", "strategy_recommendations", "allocations"):
        value = manager.get(key)
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _weight(item: Mapping[str, Any]) -> float:
    for key in ("recommended_weight_pct", "recommended_percentage", "weight_pct", "percentage"):
        value = item.get(key)
        if isinstance(value, (int, float)):
            return max(0.0, float(value))
    return 0.0


def _sid(item: Mapping[str, Any]) -> str:
    return str(item.get("strategy_id") or item.get("id") or item.get("strategy_name") or "UNKNOWN")


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))


def build_cross_strategy_risk_report(
    portfolio_manager: Mapping[str, Any],
    *,
    enterprise_health: Optional[Mapping[str, Any]] = None,
    correlation_evidence: Optional[Mapping[str, Any]] = None,
    policy: Optional[Mapping[str, Any]] = None,
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    policy_data = dict(policy or {})
    max_strategy_weight = float(policy_data.get("max_strategy_weight_pct", 40.0))
    max_pair_correlation = float(policy_data.get("max_pair_correlation", 0.80))
    min_cash_reserve = float(policy_data.get("minimum_cash_reserve_pct", 10.0))
    allocations = _allocations(portfolio_manager)
    total_weight = round(sum(_weight(item) for item in allocations), 4)
    reserve = portfolio_manager.get("cash_reserve_pct")
    if not isinstance(reserve, (int, float)):
        reserve = max(0.0, 100.0 - total_weight)
    reserve = float(reserve)

    health_map: dict[str, str] = {}
    health_rows = (enterprise_health or {}).get("strategies", [])
    if isinstance(health_rows, list):
        for row in health_rows:
            if isinstance(row, Mapping):
                health_map[_sid(row)] = str(row.get("classification") or row.get("health_status") or "UNKNOWN").upper()

    correlations: dict[tuple[str, str], float] = {}
    pairs = (correlation_evidence or {}).get("pairs", [])
    if isinstance(pairs, list):
        for pair in pairs:
            if not isinstance(pair, Mapping):
                continue
            a = str(pair.get("strategy_a") or pair.get("left") or "")
            b = str(pair.get("strategy_b") or pair.get("right") or "")
            value = pair.get("correlation")
            if a and b and isinstance(value, (int, float)):
                correlations[_pair_key(a, b)] = float(value)

    findings: list[dict[str, Any]] = []
    exposure: list[dict[str, Any]] = []
    for item in allocations:
        sid = _sid(item)
        weight = _weight(item)
        health = health_map.get(sid, str(item.get("health_classification") or item.get("health") or "UNKNOWN").upper())
        exposure.append({"strategy_id": sid, "weight_pct": round(weight, 4), "health": health})
        if weight > max_strategy_weight:
            findings.append({"severity": "HIGH", "type": "CONCENTRATION", "strategy_id": sid, "message": f"strategy weight {weight:.2f}% exceeds {max_strategy_weight:.2f}%"})
        if health in {"DEGRADED", "CRITICAL", "OFFLINE", "UNSAFE"} and weight > 0:
            findings.append({"severity": "CRITICAL" if health in {"CRITICAL", "UNSAFE"} else "HIGH", "type": "HEALTH_EXPOSURE", "strategy_id": sid, "message": f"positive allocation to {health} strategy"})

    ids = [_sid(item) for item in allocations if _weight(item) > 0]
    for index, left in enumerate(ids):
        for right in ids[index + 1:]:
            value = correlations.get(_pair_key(left, right))
            if value is not None and value > max_pair_correlation:
                findings.append({"severity": "HIGH", "type": "CORRELATION", "strategies": [left, right], "correlation": value, "message": f"pair correlation {value:.2f} exceeds {max_pair_correlation:.2f}"})

    warnings: list[str] = []
    if not correlations and len(ids) > 1:
        warnings.append("correlation evidence unavailable; pair risk not scored")
    if reserve < min_cash_reserve:
        findings.append({"severity": "HIGH", "type": "CASH_RESERVE", "message": f"cash reserve {reserve:.2f}% is below {min_cash_reserve:.2f}%"})
    if total_weight > 100.0001:
        findings.append({"severity": "CRITICAL", "type": "OVERALLOCATION", "message": f"recommended strategy weights total {total_weight:.2f}%"})

    critical = sum(item["severity"] == "CRITICAL" for item in findings)
    high = sum(item["severity"] == "HIGH" for item in findings)
    risk_score = min(100, critical * 40 + high * 18 + len(warnings) * 5)
    status = "CRITICAL" if critical else "HIGH" if high else "WATCH" if warnings else "ACCEPTABLE"
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at_utc or _now_utc(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "risk_status": status,
        "risk_score": risk_score,
        "summary": {"strategy_count": len(allocations), "allocated_weight_pct": total_weight, "cash_reserve_pct": round(reserve, 4), "critical_findings": critical, "high_findings": high},
        "strategy_exposure": exposure,
        "findings": findings,
        "warnings": warnings,
        "policy": {"max_strategy_weight_pct": max_strategy_weight, "max_pair_correlation": max_pair_correlation, "minimum_cash_reserve_pct": min_cash_reserve},
        "governance": {"advisory_only": True, "automatic_reallocation_allowed": False, "investor_approval_required": True, "governance_review_required": True},
    }


def write_cross_strategy_risk_json(report: Mapping[str, Any], output_path: str | Path) -> str:
    path = Path(output_path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def render_cross_strategy_risk_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = ["# Cross-Strategy Risk Report", "", f"- Status: **{report['risk_status']}**", f"- Risk Score: {report['risk_score']}", f"- Allocated Weight: {summary['allocated_weight_pct']:.2f}%", f"- Cash Reserve: {summary['cash_reserve_pct']:.2f}%", "", "## Strategy Exposure", "", "| Strategy | Weight | Health |", "|---|---:|---|"]
    for item in report["strategy_exposure"]:
        lines.append(f"| {item['strategy_id']} | {item['weight_pct']:.2f}% | {item['health']} |")
    lines.extend(["", "## Findings", ""])
    lines.extend([f"- **{item['severity']}** — {item['message']}" for item in report["findings"]] or ["- No material findings."])
    if report["warnings"]:
        lines.extend(["", "## Warnings", "", *[f"- {item}" for item in report["warnings"]]])
    lines.extend(["", "## Governance", "", "- Advisory only", "- No automatic reallocation", "- Investor approval and governance review required", ""])
    return "\n".join(lines)


def write_cross_strategy_risk_markdown(report: Mapping[str, Any], output_path: str | Path) -> str:
    path = Path(output_path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_cross_strategy_risk_markdown(report), encoding="utf-8")
    return str(path)


def build_and_write_cross_strategy_risk(
    portfolio_manager_path: str | Path,
    output_dir: str | Path = "results",
    *,
    enterprise_health_path: str | Path | None = None,
    correlation_evidence_path: str | Path | None = None,
    policy_path: str | Path | None = None,
    generated_at_utc: Optional[str] = None,
) -> dict[str, str]:
    manager, _ = _load_json(portfolio_manager_path, required=True)
    health, health_warnings = _load_json(enterprise_health_path, required=False) if enterprise_health_path else ({}, [])
    correlations, correlation_warnings = _load_json(correlation_evidence_path, required=False) if correlation_evidence_path else ({}, [])
    policy, policy_warnings = _load_json(policy_path, required=False) if policy_path else ({}, [])
    report = build_cross_strategy_risk_report(manager, enterprise_health=health, correlation_evidence=correlations, policy=policy, generated_at_utc=generated_at_utc)
    report["warnings"] = sorted(set(report["warnings"] + health_warnings + correlation_warnings + policy_warnings))
    directory = Path(output_dir)
    return {"json": write_cross_strategy_risk_json(report, directory / "cross_strategy_risk.json"), "markdown": write_cross_strategy_risk_markdown(report, directory / "cross_strategy_risk.md")}
