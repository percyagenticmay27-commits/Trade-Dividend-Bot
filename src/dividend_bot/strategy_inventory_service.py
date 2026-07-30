"""Read-only AI CIO inventory of Enterprise strategy contracts.

The service consumes published strategy contract directories. It does not discover
provider implementations, import strategy-private modules, schedule work, allocate
capital, or execute trades.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

MODULE_NAME = "strategy_inventory_service"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REQUIRED_CONTRACTS = ("manifest.json", "status.json", "health.json", "outputs.json")


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    if not path.is_file():
        return None, f"missing contract: {path.name}"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"invalid contract {path.name}: {exc}"
    if not isinstance(value, dict):
        return None, f"invalid contract {path.name}: root must be an object"
    return value, None


def _first(mapping: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = mapping.get(name)
        if value is not None:
            return value
    return default


def _text(value: Any, default: str = "UNKNOWN") -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def _string_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(sorted({_text(item, "") for item in value if _text(item, "")}))


@dataclass(frozen=True)
class StrategyInventoryItem:
    strategy_id: str
    strategy_name: str
    strategy_type: str
    version: str
    lifecycle_status: str
    certification_level: str
    runtime_status: str
    health_status: str
    readiness: str
    latest_cycle_id: Optional[str]
    latest_successful_run: Optional[str]
    last_heartbeat: Optional[str]
    capabilities: tuple[str, ...]
    required_enterprise_services: tuple[str, ...]
    output_count: int
    contract_directory: str
    contract_complete: bool
    paper_trade_mode: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    warnings: tuple[str, ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for key in ("capabilities", "required_enterprise_services", "warnings", "errors"):
            result[key] = list(result[key])
        return result


@dataclass(frozen=True)
class StrategyInventory:
    generated_at_utc: str
    strategies: tuple[StrategyInventoryItem, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        items = [item.to_dict() for item in self.strategies]
        return {
            "module_name": MODULE_NAME,
            "module_version": MODULE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": self.generated_at_utc,
            "paper_trade_mode": True,
            "live_trading_enabled": False,
            "broker_execution_enabled": False,
            "summary": build_summary(self.strategies),
            "strategies": items,
            "warnings": list(self.warnings),
        }


def build_inventory_item(contract_dir: str | Path) -> StrategyInventoryItem:
    directory = Path(contract_dir)
    documents: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for filename in REQUIRED_CONTRACTS:
        document, error = _read_json(directory / filename)
        if error:
            errors.append(error)
        else:
            documents[filename] = document or {}

    manifest = documents.get("manifest.json", {})
    status = documents.get("status.json", {})
    health = documents.get("health.json", {})
    outputs = documents.get("outputs.json", {})
    strategy_id = _text(_first(manifest, "strategy_id", "bot_id", default=directory.name))
    warnings = list(_string_list(health.get("warnings"))) + list(_string_list(status.get("warnings")))

    paper_mode = bool(_first(manifest, "paper_trade_mode", default=False))
    live_enabled = bool(_first(manifest, "live_trading_enabled", default=True))
    broker_enabled = bool(_first(manifest, "broker_execution_enabled", default=True))
    if not paper_mode:
        errors.append("paper_trade_mode must be true")
    if live_enabled:
        errors.append("live_trading_enabled must be false")
    if broker_enabled:
        errors.append("broker_execution_enabled must be false")

    raw_output_count = _first(outputs, "output_count", default=None)
    if isinstance(raw_output_count, int) and raw_output_count >= 0:
        output_count = raw_output_count
    else:
        output_count = sum(
            len(value) for value in outputs.values() if isinstance(value, list)
        )

    return StrategyInventoryItem(
        strategy_id=strategy_id,
        strategy_name=_text(_first(manifest, "strategy_name", "bot_name", default=strategy_id)),
        strategy_type=_text(_first(manifest, "strategy_type", "bot_type")),
        version=_text(_first(manifest, "version", "strategy_version", default="0.0.0")),
        lifecycle_status=_text(_first(manifest, "lifecycle_status")),
        certification_level=_text(_first(manifest, "certification_level")),
        runtime_status=_text(_first(status, "runtime_status", "status")),
        health_status=_text(_first(health, "overall_status", "health_status", "status")),
        readiness=_text(_first(health, "readiness", "ready", default="UNKNOWN")),
        latest_cycle_id=_first(status, "latest_cycle_id", "cycle_id"),
        latest_successful_run=_first(status, "latest_successful_run", "last_successful_run"),
        last_heartbeat=_first(health, "last_heartbeat", "heartbeat_at"),
        capabilities=_string_list(manifest.get("capabilities")),
        required_enterprise_services=_string_list(manifest.get("required_enterprise_services")),
        output_count=output_count,
        contract_directory=str(directory),
        contract_complete=not any(message.startswith("missing contract") for message in errors),
        paper_trade_mode=paper_mode,
        live_trading_enabled=live_enabled,
        broker_execution_enabled=broker_enabled,
        warnings=tuple(sorted(set(warnings))),
        errors=tuple(sorted(set(errors))),
    )


def build_summary(items: Sequence[StrategyInventoryItem]) -> dict[str, int]:
    return {
        "strategy_count": len(items),
        "contract_complete_count": sum(item.contract_complete for item in items),
        "healthy_count": sum(item.health_status == "OK" for item in items),
        "warning_count": sum(bool(item.warnings) or item.health_status == "WARNING" for item in items),
        "error_count": sum(bool(item.errors) or item.health_status == "ERROR" for item in items),
        "running_count": sum(item.runtime_status == "RUNNING" for item in items),
        "paper_safe_count": sum(
            item.paper_trade_mode and not item.live_trading_enabled and not item.broker_execution_enabled
            for item in items
        ),
    }


def build_strategy_inventory(
    contract_directories: Iterable[str | Path],
    *,
    generated_at_utc: Optional[str] = None,
) -> StrategyInventory:
    items = sorted(
        (build_inventory_item(path) for path in contract_directories),
        key=lambda item: item.strategy_id,
    )
    duplicate_ids = sorted({item.strategy_id for item in items if sum(x.strategy_id == item.strategy_id for x in items) > 1})
    warnings = tuple(f"duplicate strategy_id: {strategy_id}" for strategy_id in duplicate_ids)
    return StrategyInventory(generated_at_utc or _now_utc(), tuple(items), warnings)


def write_strategy_inventory_json(inventory: StrategyInventory, output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inventory.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def render_strategy_inventory_markdown(inventory: StrategyInventory) -> str:
    summary = build_summary(inventory.strategies)
    lines = [
        "# Enterprise Strategy Inventory",
        "",
        f"- Generated: {inventory.generated_at_utc}",
        f"- Strategies: {summary['strategy_count']}",
        f"- Contract Complete: {summary['contract_complete_count']}",
        f"- Healthy: {summary['healthy_count']}",
        f"- Errors: {summary['error_count']}",
        f"- Paper Safe: {summary['paper_safe_count']}",
        "",
        "| Strategy | Type | Version | Lifecycle | Runtime | Health | Certification | Outputs |",
        "|---|---|---:|---|---|---|---|---:|",
    ]
    for item in inventory.strategies:
        lines.append(
            f"| {item.strategy_name} (`{item.strategy_id}`) | {item.strategy_type} | {item.version} | "
            f"{item.lifecycle_status} | {item.runtime_status} | {item.health_status} | "
            f"{item.certification_level} | {item.output_count} |"
        )
    findings = list(inventory.warnings)
    for item in inventory.strategies:
        findings.extend(f"{item.strategy_id}: {message}" for message in (*item.warnings, *item.errors))
    if findings:
        lines.extend(["", "## Findings", "", *[f"- {message}" for message in findings]])
    lines.append("")
    return "\n".join(lines)


def write_strategy_inventory_markdown(inventory: StrategyInventory, output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_strategy_inventory_markdown(inventory), encoding="utf-8")
    return str(path)


def build_and_write_strategy_inventory(
    contract_directories: Iterable[str | Path],
    output_dir: str | Path = "results",
    *,
    generated_at_utc: Optional[str] = None,
) -> dict[str, str]:
    inventory = build_strategy_inventory(contract_directories, generated_at_utc=generated_at_utc)
    directory = Path(output_dir)
    return {
        "json": write_strategy_inventory_json(inventory, directory / "strategy_inventory.json"),
        "markdown": write_strategy_inventory_markdown(inventory, directory / "strategy_inventory.md"),
    }
