"""Read-only Enterprise Executive Dashboard for AI CIO operations.

Consumes existing Enterprise report artifacts only. It does not discover plugins,
schedule strategies, allocate capital, request market data, or execute trades.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

MODULE_NAME = "enterprise_executive_dashboard"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
ENTERPRISE_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

REQUIRED_INPUTS = ("strategy_inventory.json", "enterprise_health.json")
OPTIONAL_INPUTS = (
    "runtime_snapshot.json",
    "event_statistics.json",
    "plugin_registry.json",
    "runtime_metrics.json",
    "scheduler_status.json",
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path, *, required: bool) -> tuple[dict[str, Any], Optional[str]]:
    if not path.is_file():
        label = "required" if required else "optional"
        return {}, f"missing {label} input: {path.name}"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, f"invalid input {path.name}: {exc}"
    if not isinstance(value, dict):
        return {}, f"invalid input {path.name}: root must be an object"
    return value, None


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _build_strategy_summary(inventory: Mapping[str, Any], health: Mapping[str, Any]) -> list[dict[str, Any]]:
    health_by_id = {
        str(item.get("strategy_id", "UNKNOWN")): item
        for item in _list(health.get("strategies"))
        if isinstance(item, Mapping)
    }
    strategies: list[dict[str, Any]] = []
    for raw in _list(inventory.get("strategies")):
        if not isinstance(raw, Mapping):
            continue
        strategy_id = str(raw.get("strategy_id", "UNKNOWN"))
        health_item = _dict(health_by_id.get(strategy_id))
        strategies.append({
            "strategy_id": strategy_id,
            "strategy_name": str(raw.get("strategy_name", strategy_id)),
            "strategy_type": str(raw.get("strategy_type", "UNKNOWN")),
            "version": str(raw.get("version", "UNKNOWN")),
            "lifecycle_status": str(raw.get("lifecycle_status", "UNKNOWN")),
            "certification_level": str(raw.get("certification_level", "UNKNOWN")),
            "runtime_status": str(raw.get("runtime_status", "UNKNOWN")),
            "health_status": str(health_item.get("classification", raw.get("health_status", "UNKNOWN"))),
            "health_score": int(health_item.get("health_score", 0) or 0),
            "readiness": str(raw.get("readiness", "UNKNOWN")),
            "output_count": int(raw.get("output_count", 0) or 0),
            "contract_complete": bool(raw.get("contract_complete", False)),
            "paper_safe": (
                _bool(raw.get("paper_trade_mode"), False)
                and not _bool(raw.get("live_trading_enabled"), True)
                and not _bool(raw.get("broker_execution_enabled"), True)
            ),
        })
    return sorted(strategies, key=lambda item: item["strategy_id"])


def build_executive_dashboard(
    input_dir: str | Path = "results",
    *,
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    directory = Path(input_dir)
    inventory, inventory_error = _read_json(directory / REQUIRED_INPUTS[0], required=True)
    health, health_error = _read_json(directory / REQUIRED_INPUTS[1], required=True)
    errors = [message for message in (inventory_error, health_error) if message]
    warnings: list[str] = []
    optional_data: dict[str, dict[str, Any]] = {}
    for filename in OPTIONAL_INPUTS:
        document, message = _read_json(directory / filename, required=False)
        if message:
            warnings.append(message)
        else:
            optional_data[filename] = document

    strategies = _build_strategy_summary(inventory, health)
    health_summary = _dict(health.get("summary"))
    enterprise_health_status = str(health.get("enterprise_status", health.get("overall_status", "UNKNOWN")))
    paper_safe = all(item["paper_safe"] for item in strategies) and not errors
    critical_alerts = [
        f"{item['strategy_id']}: health is {item['health_status']}"
        for item in strategies
        if item["health_status"] in {"CRITICAL", "UNSAFE"}
    ]
    critical_alerts.extend(errors)
    warning_alerts = list(warnings)
    warning_alerts.extend(
        f"{item['strategy_id']}: contract incomplete"
        for item in strategies
        if not item["contract_complete"]
    )
    warning_alerts.extend(
        f"{item['strategy_id']}: health is {item['health_status']}"
        for item in strategies
        if item["health_status"] in {"WARNING", "DEGRADED"}
    )

    if not paper_safe:
        enterprise_status = "UNSAFE"
    elif errors:
        enterprise_status = "ERROR"
    elif critical_alerts:
        enterprise_status = "CRITICAL"
    elif enterprise_health_status in {"DEGRADED", "WARNING"} or warning_alerts:
        enterprise_status = "DEGRADED"
    elif enterprise_health_status in {"HEALTHY", "OK"}:
        enterprise_status = "HEALTHY"
    else:
        enterprise_status = enterprise_health_status

    inventory_summary = _dict(inventory.get("summary"))
    runtime_snapshot = _dict(optional_data.get("runtime_snapshot.json"))
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "enterprise_version": ENTERPRISE_VERSION,
        "generated_at_utc": generated_at_utc or _now_utc(),
        "enterprise_summary": {
            "enterprise_status": enterprise_status,
            "enterprise_health_status": enterprise_health_status,
            "registered_strategy_count": len(strategies),
            "paper_trade_mode": True,
            "live_trading_enabled": False,
            "broker_execution_enabled": False,
        },
        "strategy_summary": strategies,
        "health_summary": {
            "healthy_count": int(health_summary.get("healthy_count", 0) or 0),
            "warning_count": int(health_summary.get("warning_count", 0) or 0),
            "degraded_count": int(health_summary.get("degraded_count", 0) or 0),
            "critical_count": int(health_summary.get("critical_count", 0) or 0),
            "offline_count": int(health_summary.get("offline_count", 0) or 0),
            "average_health_score": float(health_summary.get("average_health_score", 0.0) or 0.0),
        },
        "runtime_summary": {
            "running_strategy_count": int(inventory_summary.get("running_count", 0) or 0),
            "contract_complete_count": int(inventory_summary.get("contract_complete_count", 0) or 0),
            "runtime_status": str(runtime_snapshot.get("runtime_status", "UNKNOWN")),
            "plugin_count": int(runtime_snapshot.get("plugin_count", len(strategies)) or 0),
            "optional_inputs_loaded": sorted(optional_data),
        },
        "alerts": {
            "critical": sorted(set(critical_alerts)),
            "warnings": sorted(set(warning_alerts)),
            "informational": [f"registered strategies: {len(strategies)}"],
        },
        "paper_safety": {
            "status": "SAFE" if paper_safe else "UNSAFE",
            "paper_trade_mode": True,
            "live_trading_enabled": False,
            "broker_execution_enabled": False,
            "safe_strategy_count": sum(item["paper_safe"] for item in strategies),
            "strategy_count": len(strategies),
        },
        "metadata": {
            "required_inputs": list(REQUIRED_INPUTS),
            "optional_inputs": list(OPTIONAL_INPUTS),
            "read_only": True,
            "allocation_allowed": False,
            "scheduling_allowed": False,
            "brokerage_communication_allowed": False,
        },
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
    }


def write_executive_dashboard_json(dashboard: Mapping[str, Any], output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(dashboard), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def render_executive_dashboard_markdown(dashboard: Mapping[str, Any]) -> str:
    enterprise = _dict(dashboard.get("enterprise_summary"))
    health = _dict(dashboard.get("health_summary"))
    runtime = _dict(dashboard.get("runtime_summary"))
    alerts = _dict(dashboard.get("alerts"))
    safety = _dict(dashboard.get("paper_safety"))
    lines = [
        "# Enterprise Executive Dashboard",
        "",
        "## Enterprise Summary",
        "",
        f"- Status: **{enterprise.get('enterprise_status', 'UNKNOWN')}**",
        f"- Enterprise Health: {enterprise.get('enterprise_health_status', 'UNKNOWN')}",
        f"- Registered Strategies: {enterprise.get('registered_strategy_count', 0)}",
        f"- Generated: {dashboard.get('generated_at_utc', 'UNKNOWN')}",
        "",
        "## Strategy Summary",
        "",
        "| Strategy | Type | Version | Runtime | Health | Score | Ready | Outputs |",
        "|---|---|---:|---|---|---:|---|---:|",
    ]
    for item in _list(dashboard.get("strategy_summary")):
        lines.append(
            f"| {item['strategy_name']} (`{item['strategy_id']}`) | {item['strategy_type']} | "
            f"{item['version']} | {item['runtime_status']} | {item['health_status']} | "
            f"{item['health_score']} | {item['readiness']} | {item['output_count']} |"
        )
    lines.extend([
        "",
        "## Health Summary",
        "",
        f"- Healthy: {health.get('healthy_count', 0)}",
        f"- Warning: {health.get('warning_count', 0)}",
        f"- Degraded: {health.get('degraded_count', 0)}",
        f"- Critical: {health.get('critical_count', 0)}",
        f"- Offline: {health.get('offline_count', 0)}",
        f"- Average Score: {health.get('average_health_score', 0.0)}",
        "",
        "## Runtime Summary",
        "",
        f"- Runtime Status: {runtime.get('runtime_status', 'UNKNOWN')}",
        f"- Running Strategies: {runtime.get('running_strategy_count', 0)}",
        f"- Plugins: {runtime.get('plugin_count', 0)}",
        f"- Contract Complete: {runtime.get('contract_complete_count', 0)}",
        "",
        "## Enterprise Alerts",
        "",
    ])
    for label, values in (("Critical", alerts.get("critical", [])), ("Warnings", alerts.get("warnings", [])), ("Informational", alerts.get("informational", []))):
        lines.append(f"### {label}")
        lines.append("")
        lines.extend([f"- {value}" for value in values] or ["- None"])
        lines.append("")
    lines.extend([
        "## Paper Safety",
        "",
        f"- Status: **{safety.get('status', 'UNKNOWN')}**",
        "- `paper_trade_mode=True`",
        "- `live_trading_enabled=False`",
        "- `broker_execution_enabled=False`",
        "",
        "## Metadata",
        "",
        f"- Module: `{dashboard.get('module_name', MODULE_NAME)}`",
        f"- Module Version: {dashboard.get('module_version', MODULE_VERSION)}",
        f"- Schema Version: {dashboard.get('schema_version', SCHEMA_VERSION)}",
        f"- Enterprise Version: {dashboard.get('enterprise_version', ENTERPRISE_VERSION)}",
        "",
    ])
    return "\n".join(lines)


def write_executive_dashboard_markdown(dashboard: Mapping[str, Any], output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_executive_dashboard_markdown(dashboard), encoding="utf-8")
    return str(path)


def build_and_write_executive_dashboard(
    input_dir: str | Path = "results",
    output_dir: str | Path = "results",
    *,
    generated_at_utc: Optional[str] = None,
) -> dict[str, str]:
    dashboard = build_executive_dashboard(input_dir, generated_at_utc=generated_at_utc)
    directory = Path(output_dir)
    return {
        "json": write_executive_dashboard_json(dashboard, directory / "executive_dashboard.json"),
        "markdown": write_executive_dashboard_markdown(dashboard, directory / "executive_dashboard.md"),
    }
