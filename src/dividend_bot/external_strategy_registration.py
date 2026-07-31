"""Host-side adapter for external paper-only strategy registrations.

The AI CIO host consumes JSON registration contracts only. This module never
imports external strategy production code, executes trades, contacts brokers,
or moves capital.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "1.0"
REQUIRED_TRUE_FLAGS = (
    "paper_trade_mode",
    "paper_compatible",
    "advisory_only",
    "reporting_only",
    "governance_review_required",
)
REQUIRED_FALSE_FLAGS = (
    "live_trading_enabled",
    "broker_execution_enabled",
    "capital_movement_enabled",
    "automatic_activation_allowed",
    "direct_database_writes",
)


def _warning(code: str, message: str, *, strategy_id: str = "", path: str = "", required: bool = False) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "strategy_id": strategy_id,
        "registration_path": path,
        "required": required,
    }


def load_external_registration_config(path: str | Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    config_path = Path(path)
    if not config_path.is_file():
        return [], [_warning("CONFIG_MISSING", f"External strategy configuration not found: {config_path}", path=str(config_path))]
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], [_warning("CONFIG_INVALID", f"Unable to load external strategy configuration: {exc}", path=str(config_path))]
    if not isinstance(payload, Mapping) or payload.get("schema_version") != SCHEMA_VERSION:
        return [], [_warning("CONFIG_SCHEMA_INVALID", "External strategy configuration schema is invalid.", path=str(config_path))]
    registrations = payload.get("registrations", [])
    if not isinstance(registrations, list):
        return [], [_warning("CONFIG_REGISTRATIONS_INVALID", "registrations must be a list.", path=str(config_path))]
    return [dict(item) for item in registrations if isinstance(item, Mapping)], []


def normalize_external_strategy_registration(registration: Mapping[str, Any], *, expected_strategy_id: str = "") -> dict[str, Any]:
    strategy_id = str(registration.get("strategy_id") or registration.get("plugin_id") or "").strip()
    display_name = str(registration.get("display_name") or registration.get("name") or "").strip()
    if not strategy_id:
        raise ValueError("strategy_id is required")
    if expected_strategy_id and strategy_id != expected_strategy_id:
        raise ValueError(f"strategy_id mismatch: expected {expected_strategy_id}, received {strategy_id}")
    if not display_name:
        raise ValueError("display_name or name is required")
    for flag in REQUIRED_TRUE_FLAGS:
        if registration.get(flag) is not True:
            raise ValueError(f"{flag} must be true")
    for flag in REQUIRED_FALSE_FLAGS:
        if registration.get(flag) is not False:
            raise ValueError(f"{flag} must be false")
    if registration.get("enabled") is not True:
        raise ValueError("enabled must be true")
    plugin_type = str(registration.get("plugin_type") or registration.get("service_type") or "STRATEGY").upper()
    if plugin_type not in {"STRATEGY", "STRATEGY_PLUGIN"}:
        raise ValueError("plugin_type/service_type must identify a strategy plugin")
    return {
        "strategy_id": strategy_id,
        "display_name": display_name,
        "plugin_type": "STRATEGY",
        "strategy_plugin": True,
        "status": str(registration.get("status") or "READY").upper(),
        "enabled": True,
        "version": str(registration.get("version") or registration.get("module_version") or "1.0.0"),
        "health": str(registration.get("health") or registration.get("health_status") or "UNKNOWN").upper(),
        "paper_trade_mode": True,
        "paper_compatible": True,
        "advisory_only": True,
        "reporting_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
        "governance_review_required": True,
        "direct_database_writes": False,
        "source_registration": str(registration.get("registration_path") or "external-json-contract"),
    }


def load_external_strategy_plugins(
    config_path: str | Path,
    *,
    existing_strategy_ids: Sequence[str] = (),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entries, warnings = load_external_registration_config(config_path)
    accepted: list[dict[str, Any]] = []
    seen = {str(item) for item in existing_strategy_ids}
    for entry in entries:
        strategy_id = str(entry.get("strategy_id") or "").strip()
        registration_path = str(entry.get("registration_path") or "").strip()
        required = bool(entry.get("required", False))
        if not registration_path:
            warnings.append(_warning("REGISTRATION_PATH_MISSING", "registration_path is required.", strategy_id=strategy_id, required=required))
            continue
        path = Path(registration_path)
        if not path.is_file():
            warnings.append(_warning("REGISTRATION_MISSING", f"External registration not found: {path}", strategy_id=strategy_id, path=str(path), required=required))
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, Mapping):
                raise ValueError("registration must be a JSON object")
            plugin = normalize_external_strategy_registration(payload, expected_strategy_id=strategy_id)
            sid = plugin["strategy_id"]
            if sid in seen:
                raise ValueError(f"duplicate strategy_id: {sid}")
            seen.add(sid)
            accepted.append(plugin)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            warnings.append(_warning("REGISTRATION_REJECTED", str(exc), strategy_id=strategy_id, path=str(path), required=required))
    accepted.sort(key=lambda item: item["strategy_id"])
    return accepted, warnings


def required_registration_failures(warnings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(item) for item in warnings if bool(item.get("required"))]
