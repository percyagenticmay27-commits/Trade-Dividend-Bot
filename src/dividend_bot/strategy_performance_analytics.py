"""Read-only cross-strategy performance analytics for the paper-only Enterprise platform."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "strategy_performance_analytics"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_object(path: str | Path, *, required: bool) -> tuple[dict[str, Any], list[str]]:
    source = Path(path)
    if not source.is_file():
        if required:
            raise FileNotFoundError(f"required input not found: {source}")
        return {}, [f"optional input not found: {source}"]
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        if required:
            raise ValueError(f"invalid required input {source}: {exc}") from exc
        return {}, [f"invalid optional input {source}: {exc}"]
    if not isinstance(value, dict):
        if required:
            raise ValueError(f"invalid required input {source}: root must be an object")
        return {}, [f"invalid optional input {source}: root must be an object"]
    return value, []


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result


def _strategy_rows(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    for key in ("strategies", "strategy_performance", "performance", "results"):
        value = document.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []


def _classification(score: float) -> str:
    if score >= 80:
        return "STRONG"
    if score >= 60:
        return "STABLE"
    if score >= 40:
        return "WATCH"
    return "WEAK"


def build_strategy_metric(row: Mapping[str, Any]) -> dict[str, Any]:
    strategy_id = str(row.get("strategy_id") or row.get("bot_id") or row.get("name") or "UNKNOWN")
    total_return = _number(row.get("total_return_pct", row.get("return_pct", row.get("net_return_pct", 0.0))))
    win_rate = max(0.0, min(100.0, _number(row.get("win_rate_pct", row.get("win_rate", 0.0)))))
    max_drawdown = abs(_number(row.get("max_drawdown_pct", row.get("max_drawdown", 0.0))))
    sample_size = max(0, int(_number(row.get("trade_count", row.get("sample_size", row.get("period_count", 0))))))
    consistency = max(0.0, min(100.0, _number(row.get("consistency_score", 50.0))))

    return_component = max(0.0, min(100.0, 50.0 + total_return * 2.0))
    drawdown_component = max(0.0, 100.0 - max_drawdown * 3.0)
    sample_component = min(100.0, sample_size * 2.0)
    score = round(
        return_component * 0.30
        + win_rate * 0.25
        + drawdown_component * 0.20
        + consistency * 0.15
        + sample_component * 0.10,
        2,
    )
    warnings: list[str] = []
    if sample_size < 10:
        warnings.append("limited sample size")
    if max_drawdown > 20:
        warnings.append("elevated drawdown")
    if total_return < 0:
        warnings.append("negative return")
    return {
        "strategy_id": strategy_id,
        "strategy_name": str(row.get("strategy_name") or row.get("display_name") or strategy_id),
        "total_return_pct": round(total_return, 2),
        "win_rate_pct": round(win_rate, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "sample_size": sample_size,
        "consistency_score": round(consistency, 2),
        "performance_score": score,
        "classification": _classification(score),
        "warnings": warnings,
    }


def build_strategy_performance_analytics(
    performance_document: Mapping[str, Any],
    *,
    portfolio_manager: Optional[Mapping[str, Any]] = None,
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    rows = _strategy_rows(performance_document)
    metrics = sorted((build_strategy_metric(row) for row in rows), key=lambda item: (-item["performance_score"], item["strategy_id"]))
    recommendation_weights: dict[str, float] = {}
    if isinstance(portfolio_manager, Mapping):
        recommendations = portfolio_manager.get("recommendations", [])
        if isinstance(recommendations, list):
            for item in recommendations:
                if isinstance(item, Mapping):
                    sid = str(item.get("strategy_id") or "")
                    if sid:
                        recommendation_weights[sid] = _number(item.get("recommended_weight_pct", item.get("weight_pct", 0.0)))
    for metric in metrics:
        metric["recommended_weight_pct"] = round(recommendation_weights.get(metric["strategy_id"], 0.0), 2)

    average_score = round(sum(item["performance_score"] for item in metrics) / len(metrics), 2) if metrics else 0.0
    best = metrics[0]["strategy_id"] if metrics else None
    weakest = metrics[-1]["strategy_id"] if metrics else None
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at_utc or _now_utc(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "summary": {
            "strategy_count": len(metrics),
            "average_performance_score": average_score,
            "strong_count": sum(item["classification"] == "STRONG" for item in metrics),
            "stable_count": sum(item["classification"] == "STABLE" for item in metrics),
            "watch_count": sum(item["classification"] == "WATCH" for item in metrics),
            "weak_count": sum(item["classification"] == "WEAK" for item in metrics),
            "best_strategy_id": best,
            "weakest_strategy_id": weakest,
        },
        "strategies": metrics,
        "governance": {
            "advisory_only": True,
            "automatic_policy_change_allowed": False,
            "automatic_allocation_change_allowed": False,
            "investor_approval_required": True,
        },
    }


def write_json(report: Mapping[str, Any], output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Enterprise Strategy Performance Analytics",
        "",
        f"- Generated: {report.get('generated_at_utc')}",
        f"- Strategies: {summary.get('strategy_count', 0)}",
        f"- Average Performance Score: {summary.get('average_performance_score', 0)}",
        f"- Best Strategy: {summary.get('best_strategy_id')}",
        f"- Weakest Strategy: {summary.get('weakest_strategy_id')}",
        "",
        "| Strategy | Return % | Win Rate % | Max Drawdown % | Sample | Score | Classification | Recommended Weight % |",
        "|---|---:|---:|---:|---:|---:|---|---:|",
    ]
    for item in report.get("strategies", []):
        lines.append(
            f"| {item['strategy_name']} (`{item['strategy_id']}`) | {item['total_return_pct']} | "
            f"{item['win_rate_pct']} | {item['max_drawdown_pct']} | {item['sample_size']} | "
            f"{item['performance_score']} | {item['classification']} | {item['recommended_weight_pct']} |"
        )
    findings = [f"{item['strategy_id']}: {warning}" for item in report.get("strategies", []) for warning in item.get("warnings", [])]
    if findings:
        lines.extend(["", "## Findings", "", *[f"- {item}" for item in findings]])
    lines.extend(["", "## Governance", "", "- Advisory only", "- No automatic policy or allocation changes", "- Investor approval remains required", ""])
    return "\n".join(lines)


def write_markdown(report: Mapping[str, Any], output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(report), encoding="utf-8")
    return str(path)


def build_and_write_strategy_performance_analytics(
    performance_path: str | Path,
    output_dir: str | Path = "results",
    *,
    portfolio_manager_path: str | Path | None = None,
    generated_at_utc: Optional[str] = None,
) -> dict[str, str]:
    performance, warnings = _load_object(performance_path, required=True)
    portfolio: dict[str, Any] = {}
    if portfolio_manager_path is not None:
        portfolio, optional_warnings = _load_object(portfolio_manager_path, required=False)
        warnings.extend(optional_warnings)
    report = build_strategy_performance_analytics(performance, portfolio_manager=portfolio, generated_at_utc=generated_at_utc)
    report["warnings"] = warnings
    directory = Path(output_dir)
    return {
        "json": write_json(report, directory / "strategy_performance_analytics.json"),
        "markdown": write_markdown(report, directory / "strategy_performance_analytics.md"),
    }
