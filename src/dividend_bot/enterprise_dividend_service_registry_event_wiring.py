"""Enterprise Dividend Service Registry and Event Wiring.

Registers paper-only Dividend services, validates subscriptions and dependency
order, and builds deterministic idempotent event-routing records. This module
never invokes services, places orders, contacts a broker, or moves capital.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from .external_strategy_registration import (
    load_external_strategy_plugins,
    required_registration_failures,
)

MODULE_NAME = "enterprise_dividend_service_registry_event_wiring"
MODULE_VERSION = "1.1.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ADVISORY_ONLY = True
REGISTRY_ONLY = True
EVENT_ROUTING_ONLY = True

SERVICE_ORDER = (
    "LIFECYCLE", "INCOME", "FORECAST", "ANALYTICS", "REPORTING",
    "DASHBOARD", "ALERTS", "REVIEWS", "LEARNING", "CIO_ADVISORY",
    "REPLACEMENT", "STRATEGY_HEALTH", "DAILY_CYCLE",
)
SERVICE_STATUSES = {"REGISTERED", "DISABLED", "DEGRADED", "UNAVAILABLE"}
DEFAULT_OUTPUT_FILES = {
    "json": "enterprise_dividend_service_registry.json",
    "markdown": "enterprise_dividend_service_registry.md",
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    text = str(value or default).strip()
    return text.upper() if text else default


def _event_id(event_type: str, source_service: str, correlation_id: str, payload_hash: str) -> str:
    raw = "|".join((event_type, source_service, correlation_id, payload_hash))
    return f"DIV-EVENT-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20].upper()}"


def _payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_service(service: Mapping[str, Any]) -> dict[str, Any]:
    name = _upper(service.get("service_name") or service.get("name"), "")
    if name not in SERVICE_ORDER:
        raise ValueError(f"Unsupported Dividend service: {name}")
    dependencies = [_upper(item, "") for item in service.get("dependencies", []) if str(item).strip()]
    invalid = [item for item in dependencies if item not in SERVICE_ORDER]
    if invalid:
        raise ValueError(f"Unsupported dependencies for {name}: {invalid}")
    if any(SERVICE_ORDER.index(dep) >= SERVICE_ORDER.index(name) for dep in dependencies):
        raise ValueError(f"Service {name} has invalid forward dependency")
    status = _upper(service.get("status"), "REGISTERED")
    if status not in SERVICE_STATUSES:
        raise ValueError(f"Unsupported service status: {status}")
    subscriptions = sorted({_upper(item, "") for item in service.get("subscriptions", []) if str(item).strip()})
    publications = sorted({_upper(item, "") for item in service.get("publications", []) if str(item).strip()})
    return {
        "service_name": name,
        "sequence": SERVICE_ORDER.index(name) + 1,
        "module_name": str(service.get("module_name") or f"enterprise_dividend_{name.lower()}"),
        "module_version": str(service.get("module_version") or "1.0.0"),
        "status": status,
        "enabled": bool(service.get("enabled", status != "DISABLED")),
        "dependencies": sorted(set(dependencies), key=SERVICE_ORDER.index),
        "subscriptions": subscriptions,
        "publications": publications,
        "input_artifacts": sorted({str(item) for item in service.get("input_artifacts", []) if str(item).strip()}),
        "output_artifacts": sorted({str(item) for item in service.get("output_artifacts", []) if str(item).strip()}),
        "idempotent": bool(service.get("idempotent", True)),
        "replay_supported": bool(service.get("replay_supported", True)),
        "paper_trade_mode": True,
    }


def default_dividend_strategy_plugins() -> list[dict[str, Any]]:
    """Return the canonical paper-only Dividend strategy plugin registration."""
    return [{
        "strategy_id": "dividend",
        "display_name": "Dividend Income Strategy",
        "plugin_type": "STRATEGY",
        "strategy_plugin": True,
        "status": "READY",
        "enabled": True,
        "version": "1.0.0",
        "health": "HEALTHY",
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
    }]


def default_dividend_services() -> list[dict[str, Any]]:
    event_names = {
        "LIFECYCLE": "DIVIDEND_LIFECYCLE_UPDATED",
        "INCOME": "DIVIDEND_INCOME_UPDATED",
        "FORECAST": "DIVIDEND_FORECAST_UPDATED",
        "ANALYTICS": "DIVIDEND_ANALYTICS_UPDATED",
        "REPORTING": "DIVIDEND_REPORTING_UPDATED",
        "DASHBOARD": "DIVIDEND_DASHBOARD_UPDATED",
        "ALERTS": "DIVIDEND_ALERTS_UPDATED",
        "REVIEWS": "DIVIDEND_REVIEWS_UPDATED",
        "LEARNING": "DIVIDEND_LEARNING_UPDATED",
        "CIO_ADVISORY": "DIVIDEND_CIO_ADVISORY_UPDATED",
        "REPLACEMENT": "DIVIDEND_REPLACEMENT_UPDATED",
        "STRATEGY_HEALTH": "DIVIDEND_STRATEGY_HEALTH_UPDATED",
        "DAILY_CYCLE": "DIVIDEND_DAILY_CYCLE_COMPLETED",
    }
    services: list[dict[str, Any]] = []
    previous: Optional[str] = None
    previous_event: Optional[str] = None
    for name in SERVICE_ORDER:
        services.append(_normalize_service({
            "service_name": name,
            "dependencies": [previous] if previous else [],
            "subscriptions": [previous_event] if previous_event else ["DIVIDEND_CYCLE_REQUESTED"],
            "publications": [event_names[name]],
            "module_name": f"enterprise_dividend_{name.lower()}_integration",
        }))
        previous = name
        previous_event = event_names[name]
    return services


def build_service_registry(
    *,
    services: Optional[Sequence[Mapping[str, Any]]] = None,
    generated_at_utc: Optional[str] = None,
    external_registration_config: Optional[str | Path] = None,
) -> dict[str, Any]:
    generated_at = generated_at_utc or _now_utc()
    normalized = default_dividend_services() if services is None else [
        _normalize_service(item) for item in services if isinstance(item, Mapping)
    ]
    normalized.sort(key=lambda item: item["sequence"])
    seen: set[str] = set()
    for service in normalized:
        name = service["service_name"]
        if name in seen:
            raise ValueError(f"Duplicate Dividend service: {name}")
        seen.add(name)
    publishers: dict[str, list[str]] = {}
    subscribers: dict[str, list[str]] = {}
    for service in normalized:
        for event_type in service["publications"]:
            publishers.setdefault(event_type, []).append(service["service_name"])
        for event_type in service["subscriptions"]:
            subscribers.setdefault(event_type, []).append(service["service_name"])
    warnings = [
        f"No registered publisher for subscribed event {event_type}."
        for event_type in subscribers
        if event_type != "DIVIDEND_CYCLE_REQUESTED" and event_type not in publishers
    ]
    strategy_plugins = default_dividend_strategy_plugins()
    external_warnings: list[dict[str, Any]] = []
    accepted_external_count = 0
    if external_registration_config is not None:
        external_plugins, external_warnings = load_external_strategy_plugins(
            external_registration_config,
            existing_strategy_ids=[item["strategy_id"] for item in strategy_plugins],
        )
        required_failures = required_registration_failures(external_warnings)
        if required_failures:
            messages = "; ".join(str(item.get("message")) for item in required_failures)
            raise ValueError(f"Required external strategy registration failed: {messages}")
        strategy_plugins.extend(external_plugins)
        accepted_external_count = len(external_plugins)
        warnings.extend(str(item.get("message")) for item in external_warnings)
    strategy_plugins.sort(key=lambda item: (item["strategy_id"] != "dividend", item["strategy_id"]))
    registry_hash = hashlib.sha256(json.dumps(normalized, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "advisory_only": True,
        "registry_only": True,
        "event_routing_only": True,
        "registry_hash": registry_hash,
        "summary": {
            "service_count": len(normalized),
            "enabled_count": sum(1 for item in normalized if item["enabled"]),
            "disabled_count": sum(1 for item in normalized if not item["enabled"]),
            "event_type_count": len(set(publishers) | set(subscribers)),
            "warning_count": len(warnings),
            "strategy_plugin_count": len(strategy_plugins),
            "accepted_external_strategy_count": accepted_external_count,
        },
        "services": normalized,
        "strategy_plugins": strategy_plugins,
        "publishers": {key: sorted(value, key=SERVICE_ORDER.index) for key, value in sorted(publishers.items())},
        "subscribers": {key: sorted(value, key=SERVICE_ORDER.index) for key, value in sorted(subscribers.items())},
        "warnings": warnings,
        "external_registration_warnings": external_warnings,
        "governance": {
            "service_invocation_allowed": False,
            "order_execution_allowed": False,
            "capital_movement_allowed": False,
            "policy_changes_allowed": False,
        },
    }


def route_dividend_event(
    *,
    registry: Mapping[str, Any],
    event_type: str,
    source_service: str,
    payload: Optional[Mapping[str, Any]] = None,
    correlation_id: str = "CURRENT",
    occurred_at_utc: Optional[str] = None,
    processed_event_ids: Optional[Sequence[str]] = None,
) -> dict[str, Any]:
    event_type = _upper(event_type, "")
    source_service = _upper(source_service, "")
    payload_data = dict(payload or {})
    payload_digest = _payload_hash(payload_data)
    event_id = _event_id(event_type, source_service, correlation_id, payload_digest)
    occurred_at = occurred_at_utc or _now_utc()
    services = {item["service_name"]: item for item in registry.get("services", []) if isinstance(item, Mapping)}
    if source_service not in services:
        raise ValueError(f"Source service is not registered: {source_service}")
    if event_type not in services[source_service].get("publications", []):
        raise ValueError(f"Service {source_service} does not publish {event_type}")
    duplicate = event_id in set(processed_event_ids or [])
    subscribers = [] if duplicate else [
        name for name in registry.get("subscribers", {}).get(event_type, [])
        if name in services and services[name].get("enabled", False)
    ]
    return {
        "event_id": event_id,
        "event_type": event_type,
        "source_service": source_service,
        "correlation_id": correlation_id,
        "occurred_at_utc": occurred_at,
        "payload_hash": payload_digest,
        "payload": payload_data,
        "duplicate": duplicate,
        "routing_status": "DUPLICATE_IGNORED" if duplicate else ("ROUTED" if subscribers else "NO_SUBSCRIBERS"),
        "subscriber_services": subscribers,
        "paper_trade_mode": True,
        "immutable": True,
    }


def render_service_registry_markdown(registry: Mapping[str, Any]) -> str:
    lines = [
        "# Enterprise Dividend Service Registry and Event Wiring", "",
        f"- Registry hash: `{registry.get('registry_hash', '')}`",
        f"- Services: **{registry.get('summary', {}).get('service_count', 0)}**",
        f"- Strategy plugins: **{registry.get('summary', {}).get('strategy_plugin_count', 0)}**",
        f"- Paper trade mode: `{registry.get('paper_trade_mode')}`", "",
        "## Registered Services", "",
        "| # | Service | Status | Enabled | Subscriptions | Publications |",
        "|---:|---|---|---|---|---|",
    ]
    for service in registry.get("services", []):
        lines.append(
            f"| {service.get('sequence')} | {service.get('service_name')} | {service.get('status')} | "
            f"{service.get('enabled')} | {', '.join(service.get('subscriptions', [])) or '-'} | "
            f"{', '.join(service.get('publications', [])) or '-'} |"
        )
    lines.extend(["", "## Strategy Plugins", ""])
    for plugin in registry.get("strategy_plugins", []):
        lines.append(
            f"- **{plugin.get('display_name')}** (`{plugin.get('strategy_id')}`): "
            f"{plugin.get('status')} / {plugin.get('health')} / paper-only"
        )
    lines.extend(["", "## Warnings", ""])
    warnings = list(registry.get("warnings") or [])
    lines.extend([f"- {item}" for item in warnings] if warnings else ["- None"])
    lines.extend([
        "", "## Governance", "",
        "This registry is paper-only and routing-only. It cannot invoke trading services, place orders, move capital, or change policy.", "",
    ])
    return "\n".join(lines)


def _atomic_write_text(path: Path, content: str) -> None:
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def write_service_registry(registry: Mapping[str, Any], output_dir: Path | str) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / DEFAULT_OUTPUT_FILES["json"]
    markdown_path = output_path / DEFAULT_OUTPUT_FILES["markdown"]
    _atomic_write_text(json_path, json.dumps(dict(registry), indent=2, sort_keys=True) + "\n")
    _atomic_write_text(markdown_path, render_service_registry_markdown(registry))
    return {"json": str(json_path), "markdown": str(markdown_path)}


def build_and_write_service_registry(output_dir: Path | str, **kwargs: Any) -> dict[str, Any]:
    registry = build_service_registry(**kwargs)
    registry["output_files"] = write_service_registry(registry, output_dir)
    return registry
