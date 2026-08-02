"""Publish the canonical paper-only Enterprise strategy registry."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping

MODULE_NAME = "enterprise_strategy_registry_publisher"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
DEFAULT_SOURCE = Path("config/enterprise_strategy_registry.json")
DEFAULT_TARGET = Path("results/enterprise_dividend_service_registry.json")
REQUIRED_STRATEGIES = ("DIVIDEND-001", "SWING-001")


def _read_mapping(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Registry root must be an object: {path}")
    return payload


def _plugins(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = payload.get("strategy_plugins")
    if not isinstance(value, list):
        raise ValueError("Registry strategy_plugins must be a list")
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _strategy_id(plugin: Mapping[str, Any]) -> str:
    return str(plugin.get("strategy_id") or "").strip().upper()


def _safety_errors(plugin: Mapping[str, Any]) -> list[str]:
    strategy_id = _strategy_id(plugin) or "UNKNOWN"
    errors: list[str] = []
    for field, expected in (
        ("paper_trade_mode", True),
        ("paper_compatible", True),
        ("advisory_only", True),
        ("reporting_only", True),
        ("live_trading_enabled", False),
        ("broker_execution_enabled", False),
        ("capital_movement_enabled", False),
        ("automatic_activation_allowed", False),
        ("direct_database_writes", False),
    ):
        if plugin.get(field) is not expected:
            errors.append(f"{strategy_id}: {field} must be {expected}")
    return errors


def validate_registry_source(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    plugins = _plugins(payload)
    ids = [_strategy_id(item) for item in plugins]
    if any(not item for item in ids):
        errors.append("Every strategy plugin must have a strategy_id")
    if len(ids) != len(set(ids)):
        errors.append("Duplicate strategy IDs are not allowed")
    for required in REQUIRED_STRATEGIES:
        if required not in ids:
            errors.append(f"Required canonical strategy is missing: {required}")
    for plugin in plugins:
        errors.extend(_safety_errors(plugin))
    return sorted(set(errors))


def _atomic_write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)
    return path


def publish_enterprise_strategy_registry(
    *,
    root_dir: str | Path = ".",
    source_path: str | Path = DEFAULT_SOURCE,
    target_path: str | Path = DEFAULT_TARGET,
) -> dict[str, Any]:
    root = Path(root_dir).resolve()
    source = Path(source_path)
    target = Path(target_path)
    source = source if source.is_absolute() else root / source
    target = target if target.is_absolute() else root / target
    canonical = _read_mapping(source)
    errors = validate_registry_source(canonical)
    if errors:
        return {
            "publish_status": "BLOCKED",
            "strategy_ids": [],
            "preserved_strategy_ids": [],
            "errors": errors,
            "target_path": str(target),
            "paper_trade_mode": True,
            "live_trading_enabled": False,
            "broker_execution_enabled": False,
            "capital_movement_enabled": False,
            "reporting_only": True,
        }

    existing: dict[str, Any] = {}
    if target.is_file():
        try:
            existing = _read_mapping(target)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            existing = {}
    canonical_plugins = _plugins(canonical)
    canonical_ids = {_strategy_id(item) for item in canonical_plugins}
    preserved = [
        item for item in _plugins(existing)
        if _strategy_id(item) and _strategy_id(item) not in canonical_ids
    ] if existing.get("strategy_plugins") is not None else []
    merged = sorted(
        [*preserved, *canonical_plugins], key=lambda item: _strategy_id(item)
    )
    document = {
        **canonical,
        "strategy_plugins": merged,
        "registry_source": str(source.relative_to(root)),
        "publisher_module": MODULE_NAME,
        "publisher_version": MODULE_VERSION,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
    }
    _atomic_write(target, json.dumps(document, indent=2, sort_keys=True) + "\n")
    return {
        "publish_status": "PASSED",
        "strategy_ids": [_strategy_id(item) for item in merged],
        "preserved_strategy_ids": [_strategy_id(item) for item in preserved],
        "errors": [],
        "target_path": str(target),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
    }
