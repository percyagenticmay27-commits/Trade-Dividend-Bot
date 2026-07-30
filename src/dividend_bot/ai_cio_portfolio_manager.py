"""Paper-only AI CIO portfolio coordination recommendations.

This module is advisory. It consumes published Enterprise reports and produces
portfolio-level recommendations. It never submits allocation requests, moves
capital, activates strategies, contacts a broker, or places orders.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "ai_cio_portfolio_manager"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
ENTERPRISE_VERSION = "1.0.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
AUTOMATIC_ALLOCATION_ENABLED = False

DEFAULT_MAX_STRATEGY_WEIGHT = 50.0
DEFAULT_MIN_CASH_RESERVE = 10.0
ELIGIBLE_HEALTH_STATUSES = {"HEALTHY", "WARNING"}


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: str | Path, *, required: bool) -> tuple[dict[str, Any], Optional[str]]:
    source = Path(path)
    if not source.is_file():
        if required:
            raise FileNotFoundError(f"required input not found: {source}")
        return {}, f"optional input not found: {source.name}"
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        if required:
            raise ValueError(f"invalid required input {source}: {exc}") from exc
        return {}, f"invalid optional input {source.name}: {exc}"
    if not isinstance(value, dict):
        if required:
            raise ValueError(f"invalid required input {source}: root must be an object")
        return {}, f"invalid optional input {source.name}: root must be an object"
    return value, None


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _strategy_health_map(health_report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    values = health_report.get("strategies", [])
    if not isinstance(values, list):
        return {}
    return {
        str(item.get("strategy_id")): item
        for item in values
        if isinstance(item, Mapping) and item.get("strategy_id")
    }


def _performance_map(performance_report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    for key in ("strategies", "strategy_performance", "performance"):
        values = performance_report.get(key)
        if isinstance(values, list):
            return {
                str(item.get("strategy_id")): item
                for item in values
                if isinstance(item, Mapping) and item.get("strategy_id")
            }
    return {}


def _policy(policy: Mapping[str, Any]) -> dict[str, float]:
    max_weight = min(100.0, max(0.0, _float(policy.get("max_strategy_weight"), DEFAULT_MAX_STRATEGY_WEIGHT)))
    reserve = min(100.0, max(0.0, _float(policy.get("minimum_cash_reserve"), DEFAULT_MIN_CASH_RESERVE)))
    return {"max_strategy_weight": max_weight, "minimum_cash_reserve": reserve}


def _eligibility_reason(strategy: Mapping[str, Any], health: Mapping[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    classification = str(health.get("classification") or strategy.get("health_status") or "UNKNOWN").upper()
    runtime = str(strategy.get("runtime_status") or "UNKNOWN").upper()
    readiness = str(strategy.get("readiness") or "UNKNOWN").upper()
    paper_safe = bool(strategy.get("paper_trade_mode", False)) and not bool(strategy.get("live_trading_enabled", True)) and not bool(strategy.get("broker_execution_enabled", True))
    if classification not in ELIGIBLE_HEALTH_STATUSES:
        reasons.append(f"health classification {classification} is not allocation-eligible")
    if runtime not in {"RUNNING", "ONLINE", "AVAILABLE", "ENABLED"}:
        reasons.append(f"runtime status {runtime} is not active")
    if readiness not in {"READY", "TRUE", "YES", "UNKNOWN"}:
        reasons.append(f"readiness status {readiness} is not ready")
    if not paper_safe:
        reasons.append("paper-only safety contract is not satisfied")
    return not reasons, reasons


def build_portfolio_recommendation(
    executive_dashboard: Mapping[str, Any],
    *,
    enterprise_health: Optional[Mapping[str, Any]] = None,
    performance_report: Optional[Mapping[str, Any]] = None,
    investor_policy: Optional[Mapping[str, Any]] = None,
    available_paper_cash: float = 0.0,
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Build an advisory allocation recommendation from published reports only."""
    dashboard = dict(executive_dashboard)
    health_report = dict(enterprise_health or {})
    performance = _performance_map(performance_report or {})
    health_by_id = _strategy_health_map(health_report)
    policy = _policy(investor_policy or {})
    warnings: list[str] = []
    blockers: list[str] = []

    enterprise_status = str(
        dashboard.get("enterprise_summary", {}).get("enterprise_status")
        or dashboard.get("enterprise_status")
        or "UNKNOWN"
    ).upper()
    paper_safety = dashboard.get("paper_safety", {})
    platform_safe = bool(paper_safety.get("paper_trade_mode", True)) and not bool(paper_safety.get("live_trading_enabled", False)) and not bool(paper_safety.get("broker_execution_enabled", False))
    if not platform_safe or enterprise_status == "UNSAFE":
        blockers.append("Enterprise paper-safety gate is not satisfied")
    if enterprise_status in {"CRITICAL", "UNSAFE"}:
        blockers.append(f"Enterprise status {enterprise_status} blocks recommendations")

    strategies = dashboard.get("strategy_summary", [])
    if not isinstance(strategies, list):
        raise ValueError("executive dashboard strategy_summary must be a list")

    candidates: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for raw in strategies:
        if not isinstance(raw, Mapping):
            continue
        strategy = dict(raw)
        strategy_id = str(strategy.get("strategy_id") or "").strip()
        if not strategy_id:
            warnings.append("strategy summary item missing strategy_id")
            continue
        health = health_by_id.get(strategy_id, {})
        eligible, reasons = _eligibility_reason(strategy, health)
        health_score = _float(health.get("health_score", strategy.get("health_score", 0.0)))
        perf = performance.get(strategy_id, {})
        performance_score = min(100.0, max(0.0, _float(perf.get("performance_score", perf.get("score", 50.0)), 50.0)))
        confidence = min(100.0, max(0.0, (health_score * 0.6) + (performance_score * 0.4)))
        item = {
            "strategy_id": strategy_id,
            "strategy_name": str(strategy.get("strategy_name") or strategy_id),
            "health_score": round(health_score, 2),
            "performance_score": round(performance_score, 2),
            "advisory_confidence": round(confidence, 2),
        }
        if eligible:
            candidates.append(item)
        else:
            item["exclusion_reasons"] = reasons
            excluded.append(item)

    reserve_pct = policy["minimum_cash_reserve"]
    deployable_pct = max(0.0, 100.0 - reserve_pct)
    raw_total = sum(max(item["advisory_confidence"], 1.0) for item in candidates)
    recommendations: list[dict[str, Any]] = []
    if candidates and not blockers:
        uncapped = {
            item["strategy_id"]: deployable_pct * max(item["advisory_confidence"], 1.0) / raw_total
            for item in candidates
        }
        capped = {key: min(value, policy["max_strategy_weight"]) for key, value in uncapped.items()}
        allocated = sum(capped.values())
        if allocated > 0 and allocated < deployable_pct:
            remaining = deployable_pct - allocated
            adjustable = [item for item in candidates if capped[item["strategy_id"]] < policy["max_strategy_weight"]]
            while remaining > 0.0001 and adjustable:
                share = remaining / len(adjustable)
                next_adjustable = []
                for item in adjustable:
                    sid = item["strategy_id"]
                    room = policy["max_strategy_weight"] - capped[sid]
                    addition = min(room, share)
                    capped[sid] += addition
                    remaining -= addition
                    if capped[sid] < policy["max_strategy_weight"] - 0.0001:
                        next_adjustable.append(item)
                if len(next_adjustable) == len(adjustable) and share <= 0.0001:
                    break
                adjustable = next_adjustable
        for item in sorted(candidates, key=lambda x: (-x["advisory_confidence"], x["strategy_id"])):
            pct = round(capped[item["strategy_id"]], 2)
            recommendations.append({
                **item,
                "recommended_percentage": pct,
                "recommended_paper_amount": round(max(0.0, float(available_paper_cash)) * pct / 100.0, 2),
                "recommendation": "ALLOCATE_PAPER_CAPITAL" if pct > 0 else "HOLD",
            })
    elif not candidates:
        warnings.append("no allocation-eligible strategies are available")

    total_recommended_pct = round(sum(item["recommended_percentage"] for item in recommendations), 2)
    cash_reserve_pct = round(100.0 - total_recommended_pct, 2)
    status = "BLOCKED" if blockers else ("ADVISORY_READY" if recommendations else "NO_ELIGIBLE_STRATEGIES")
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "enterprise_version": ENTERPRISE_VERSION,
        "generated_at_utc": generated_at_utc or _now_utc(),
        "status": status,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "automatic_allocation_enabled": False,
        "available_paper_cash": round(max(0.0, float(available_paper_cash)), 2),
        "policy": policy,
        "summary": {
            "enterprise_status": enterprise_status,
            "eligible_strategy_count": len(candidates),
            "excluded_strategy_count": len(excluded),
            "recommended_strategy_count": len(recommendations),
            "recommended_allocation_percentage": total_recommended_pct,
            "recommended_cash_reserve_percentage": cash_reserve_pct,
        },
        "recommendations": recommendations,
        "excluded_strategies": excluded,
        "warnings": sorted(set(warnings)),
        "blockers": sorted(set(blockers)),
        "governance": {
            "advisory_only": True,
            "investor_approval_required": True,
            "governance_review_required": True,
            "allocation_request_not_created": True,
            "strategy_activation_not_allowed": True,
            "order_execution_allowed": False,
            "capital_movement_allowed": False,
        },
    }


def build_ai_cio_portfolio_manager(
    executive_dashboard_path: str | Path,
    *,
    enterprise_health_path: str | Path | None = None,
    performance_report_path: str | Path | None = None,
    investor_policy_path: str | Path | None = None,
    available_paper_cash: float = 0.0,
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    dashboard, _ = _read_json(executive_dashboard_path, required=True)
    warnings: list[str] = []
    health: dict[str, Any] = {}
    performance: dict[str, Any] = {}
    policy: dict[str, Any] = {}
    for path, target in (
        (enterprise_health_path, "health"),
        (performance_report_path, "performance"),
        (investor_policy_path, "policy"),
    ):
        if path is None:
            continue
        value, warning = _read_json(path, required=False)
        if warning:
            warnings.append(warning)
        if target == "health":
            health = value
        elif target == "performance":
            performance = value
        else:
            policy = value
    result = build_portfolio_recommendation(
        dashboard,
        enterprise_health=health,
        performance_report=performance,
        investor_policy=policy,
        available_paper_cash=available_paper_cash,
        generated_at_utc=generated_at_utc,
    )
    result["warnings"] = sorted(set(result["warnings"] + warnings))
    return result


def write_ai_cio_portfolio_json(report: Mapping[str, Any], output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def render_ai_cio_portfolio_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# AI CIO Portfolio Manager",
        "",
        f"- Status: **{report.get('status', 'UNKNOWN')}**",
        f"- Enterprise Status: {summary.get('enterprise_status', 'UNKNOWN')}",
        f"- Available Paper Cash: ${_float(report.get('available_paper_cash')):,.2f}",
        f"- Eligible Strategies: {summary.get('eligible_strategy_count', 0)}",
        f"- Recommended Allocation: {summary.get('recommended_allocation_percentage', 0)}%",
        f"- Recommended Cash Reserve: {summary.get('recommended_cash_reserve_percentage', 100)}%",
        "",
        "## Advisory Recommendations",
        "",
        "| Strategy | Health | Performance | Confidence | Allocation | Paper Amount |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in report.get("recommendations", []):
        lines.append(
            f"| {item['strategy_name']} (`{item['strategy_id']}`) | {item['health_score']} | "
            f"{item['performance_score']} | {item['advisory_confidence']} | "
            f"{item['recommended_percentage']}% | ${item['recommended_paper_amount']:,.2f} |"
        )
    if not report.get("recommendations"):
        lines.append("| No advisory allocations | - | - | - | - | - |")
    for heading, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        values = report.get(key, [])
        if values:
            lines.extend(["", f"## {heading}", "", *[f"- {value}" for value in values]])
    lines.extend([
        "",
        "## Governance",
        "",
        "- Advisory only",
        "- Investor approval required",
        "- Separate governance review required",
        "- No allocation request created",
        "- No strategy activation",
        "- No broker communication, orders, or capital movement",
        "",
    ])
    return "\n".join(lines)


def write_ai_cio_portfolio_markdown(report: Mapping[str, Any], output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_ai_cio_portfolio_markdown(report), encoding="utf-8")
    return str(path)


def build_and_write_ai_cio_portfolio_manager(
    executive_dashboard_path: str | Path,
    output_dir: str | Path = "results",
    **kwargs: Any,
) -> dict[str, str]:
    report = build_ai_cio_portfolio_manager(executive_dashboard_path, **kwargs)
    directory = Path(output_dir)
    return {
        "json": write_ai_cio_portfolio_json(report, directory / "ai_cio_portfolio_manager.json"),
        "markdown": write_ai_cio_portfolio_markdown(report, directory / "ai_cio_portfolio_manager.md"),
    }
