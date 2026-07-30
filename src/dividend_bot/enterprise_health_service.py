"""Read-only AI CIO health aggregation for registered Enterprise strategies.

Consumes Strategy Inventory output or in-memory inventory data. It does not import
private strategy modules, discover providers, schedule work, allocate capital, or
communicate with a broker.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

MODULE_NAME = "enterprise_health_service"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

HEALTHY_MIN_SCORE = 90
WARNING_MIN_SCORE = 75
DEGRADED_MIN_SCORE = 50
DEFAULT_HEARTBEAT_STALE_MINUTES = 30


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _string_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(sorted({str(item).strip() for item in value if str(item).strip()}))


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    text = str(value).strip().upper() if value is not None else ""
    return text or default


def _as_strategy_rows(inventory: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    if isinstance(inventory, Mapping):
        rows = inventory.get("strategies", [])
    else:
        rows = inventory
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


@dataclass(frozen=True)
class StrategyHealthAssessment:
    strategy_id: str
    strategy_name: str
    runtime_status: str
    declared_health_status: str
    effective_health_status: str
    health_score: int
    classification: str
    heartbeat_status: str
    last_heartbeat: Optional[str]
    heartbeat_age_minutes: Optional[int]
    contract_complete: bool
    readiness: str
    dependency_status: str
    dependencies: tuple[str, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    paper_safe: bool

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for key in ("dependencies", "warnings", "errors"):
            result[key] = list(result[key])
        return result


@dataclass(frozen=True)
class EnterpriseHealthReport:
    generated_at_utc: str
    enterprise_status: str
    strategies: tuple[StrategyHealthAssessment, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_name": MODULE_NAME,
            "module_version": MODULE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": self.generated_at_utc,
            "paper_trade_mode": True,
            "live_trading_enabled": False,
            "broker_execution_enabled": False,
            "enterprise_status": self.enterprise_status,
            "summary": build_enterprise_summary(self.strategies),
            "strategies": [item.to_dict() for item in self.strategies],
            "warnings": list(self.warnings),
        }


def classify_score(score: int) -> str:
    if score >= HEALTHY_MIN_SCORE:
        return "HEALTHY"
    if score >= WARNING_MIN_SCORE:
        return "WARNING"
    if score >= DEGRADED_MIN_SCORE:
        return "DEGRADED"
    return "CRITICAL"


def assess_strategy_health(
    strategy: Mapping[str, Any],
    *,
    now_utc: Optional[datetime] = None,
    stale_after_minutes: int = DEFAULT_HEARTBEAT_STALE_MINUTES,
    dependency_health: Optional[Mapping[str, str]] = None,
) -> StrategyHealthAssessment:
    now = (now_utc or _now_utc()).astimezone(timezone.utc)
    warnings = list(_string_list(strategy.get("warnings")))
    errors = list(_string_list(strategy.get("errors")))
    score = 100

    contract_complete = bool(strategy.get("contract_complete", False))
    if not contract_complete:
        score -= 30
        errors.append("required strategy contracts are incomplete")

    runtime_status = _upper(strategy.get("runtime_status"))
    if runtime_status in {"ERROR", "FAILED", "OFFLINE"}:
        score -= 40
        errors.append(f"runtime status is {runtime_status}")
    elif runtime_status in {"DEGRADED", "STOPPED", "PAUSED", "UNKNOWN"}:
        score -= 15
        warnings.append(f"runtime status is {runtime_status}")

    declared_health = _upper(strategy.get("health_status"))
    if declared_health in {"ERROR", "CRITICAL"}:
        score -= 35
        errors.append(f"declared health is {declared_health}")
    elif declared_health in {"WARNING", "DEGRADED", "UNKNOWN"}:
        score -= 15
        warnings.append(f"declared health is {declared_health}")

    readiness = _upper(strategy.get("readiness"))
    if readiness in {"FALSE", "NOT_READY", "BLOCKED", "ERROR"}:
        score -= 20
        errors.append(f"readiness is {readiness}")
    elif readiness == "UNKNOWN":
        score -= 5
        warnings.append("readiness is unknown")

    heartbeat = _parse_utc(strategy.get("last_heartbeat"))
    heartbeat_age: Optional[int] = None
    if heartbeat is None:
        heartbeat_status = "MISSING"
        score -= 15
        warnings.append("heartbeat is missing or invalid")
    else:
        heartbeat_age = max(0, int((now - heartbeat).total_seconds() // 60))
        if heartbeat_age > stale_after_minutes:
            heartbeat_status = "STALE"
            score -= 20
            warnings.append(f"heartbeat is stale ({heartbeat_age} minutes old)")
        else:
            heartbeat_status = "CURRENT"

    paper_safe = (
        bool(strategy.get("paper_trade_mode", False))
        and not bool(strategy.get("live_trading_enabled", True))
        and not bool(strategy.get("broker_execution_enabled", True))
    )
    if not paper_safe:
        score = 0
        errors.append("paper-only safety validation failed")

    dependencies = _string_list(strategy.get("required_enterprise_services"))
    unavailable: list[str] = []
    if dependency_health is not None:
        for dependency in dependencies:
            status = _upper(dependency_health.get(dependency, "UNKNOWN"))
            if status not in {"OK", "HEALTHY", "RUNNING", "AVAILABLE"}:
                unavailable.append(f"{dependency}:{status}")
    if unavailable:
        score -= min(30, 10 * len(unavailable))
        warnings.append("unavailable dependencies: " + ", ".join(unavailable))
        dependency_status = "DEGRADED"
    else:
        dependency_status = "HEALTHY" if dependency_health is not None else "NOT_EVALUATED"

    score = max(0, min(100, score))
    classification = classify_score(score)
    effective_status = classification
    if not paper_safe or errors or classification == "CRITICAL":
        effective_status = "CRITICAL"
    elif classification == "DEGRADED":
        effective_status = "DEGRADED"
    elif classification == "WARNING" or warnings:
        effective_status = "WARNING"
    else:
        effective_status = "HEALTHY"

    return StrategyHealthAssessment(
        strategy_id=str(strategy.get("strategy_id", "UNKNOWN")),
        strategy_name=str(strategy.get("strategy_name", strategy.get("strategy_id", "UNKNOWN"))),
        runtime_status=runtime_status,
        declared_health_status=declared_health,
        effective_health_status=effective_status,
        health_score=score,
        classification=classification,
        heartbeat_status=heartbeat_status,
        last_heartbeat=_iso_utc(heartbeat) if heartbeat else None,
        heartbeat_age_minutes=heartbeat_age,
        contract_complete=contract_complete,
        readiness=readiness,
        dependency_status=dependency_status,
        dependencies=dependencies,
        warnings=tuple(sorted(set(warnings))),
        errors=tuple(sorted(set(errors))),
        paper_safe=paper_safe,
    )


def build_enterprise_summary(items: Sequence[StrategyHealthAssessment]) -> dict[str, Any]:
    scores = [item.health_score for item in items]
    return {
        "registered_strategies": len(items),
        "healthy": sum(item.effective_health_status == "HEALTHY" for item in items),
        "warning": sum(item.effective_health_status == "WARNING" for item in items),
        "degraded": sum(item.effective_health_status == "DEGRADED" for item in items),
        "critical": sum(item.effective_health_status == "CRITICAL" for item in items),
        "offline": sum(item.runtime_status == "OFFLINE" for item in items),
        "stale_heartbeat": sum(item.heartbeat_status == "STALE" for item in items),
        "average_health_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
        "paper_safe": sum(item.paper_safe for item in items),
    }


def determine_enterprise_status(items: Sequence[StrategyHealthAssessment]) -> str:
    if not items:
        return "UNKNOWN"
    statuses = {item.effective_health_status for item in items}
    if "CRITICAL" in statuses:
        return "CRITICAL"
    if "DEGRADED" in statuses:
        return "DEGRADED"
    if "WARNING" in statuses:
        return "WARNING"
    return "HEALTHY"


def build_enterprise_health_report(
    inventory: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    generated_at_utc: Optional[str] = None,
    now_utc: Optional[datetime] = None,
    stale_after_minutes: int = DEFAULT_HEARTBEAT_STALE_MINUTES,
    dependency_health: Optional[Mapping[str, str]] = None,
) -> EnterpriseHealthReport:
    if stale_after_minutes < 1:
        raise ValueError("stale_after_minutes must be at least 1")
    rows = _as_strategy_rows(inventory)
    assessments = tuple(sorted(
        (
            assess_strategy_health(
                row,
                now_utc=now_utc,
                stale_after_minutes=stale_after_minutes,
                dependency_health=dependency_health,
            )
            for row in rows
        ),
        key=lambda item: item.strategy_id,
    ))
    warnings: list[str] = []
    if not rows:
        warnings.append("strategy inventory contains no registered strategies")
    timestamp = generated_at_utc or _iso_utc(now_utc or _now_utc())
    return EnterpriseHealthReport(
        generated_at_utc=timestamp,
        enterprise_status=determine_enterprise_status(assessments),
        strategies=assessments,
        warnings=tuple(warnings),
    )


def load_strategy_inventory(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read strategy inventory: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("strategy inventory root must be an object")
    return value


def write_enterprise_health_json(report: EnterpriseHealthReport, output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def render_enterprise_health_markdown(report: EnterpriseHealthReport) -> str:
    summary = build_enterprise_summary(report.strategies)
    lines = [
        "# Enterprise Health",
        "",
        f"- Generated: {report.generated_at_utc}",
        f"- Enterprise Status: **{report.enterprise_status}**",
        f"- Registered Strategies: {summary['registered_strategies']}",
        f"- Healthy: {summary['healthy']}",
        f"- Warning: {summary['warning']}",
        f"- Degraded: {summary['degraded']}",
        f"- Critical: {summary['critical']}",
        f"- Average Health Score: {summary['average_health_score']}",
        "",
        "| Strategy | Runtime | Effective Health | Score | Heartbeat | Dependencies | Paper Safe |",
        "|---|---|---|---:|---|---|---|",
    ]
    for item in report.strategies:
        lines.append(
            f"| {item.strategy_name} (`{item.strategy_id}`) | {item.runtime_status} | "
            f"{item.effective_health_status} | {item.health_score} | {item.heartbeat_status} | "
            f"{item.dependency_status} | {'Yes' if item.paper_safe else 'No'} |"
        )
    findings = list(report.warnings)
    for item in report.strategies:
        findings.extend(f"{item.strategy_id}: {message}" for message in (*item.warnings, *item.errors))
    if findings:
        lines.extend(["", "## Findings", "", *[f"- {message}" for message in findings]])
    lines.append("")
    return "\n".join(lines)


def write_enterprise_health_markdown(report: EnterpriseHealthReport, output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_enterprise_health_markdown(report), encoding="utf-8")
    return str(path)


def build_and_write_enterprise_health(
    inventory: Mapping[str, Any] | Sequence[Mapping[str, Any]] | str | Path,
    output_dir: str | Path = "results",
    **kwargs: Any,
) -> dict[str, str]:
    inventory_data = load_strategy_inventory(inventory) if isinstance(inventory, (str, Path)) else inventory
    report = build_enterprise_health_report(inventory_data, **kwargs)
    directory = Path(output_dir)
    return {
        "json": write_enterprise_health_json(report, directory / "enterprise_health.json"),
        "markdown": write_enterprise_health_markdown(report, directory / "enterprise_health.md"),
    }
