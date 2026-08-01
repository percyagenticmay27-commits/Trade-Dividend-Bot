"""Build read-only per-strategy KPI evidence from the Enterprise registry.

The host consumes declared JSON/CSV artifacts only. It does not import strategy code,
change allocations, move capital, or execute broker actions.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True

_PATH_KEYS = {
    "path", "report_path", "output_path", "artifact_path", "registration_path",
    "portfolio_path", "watchlist_path", "holdings_path", "positions_path",
    "performance_path", "income_path", "health_path", "readiness_path",
}
_CONTAINER_KEYS = {
    "artifacts", "outputs", "reports", "evidence", "evidence_paths",
    "dashboard_artifacts", "published_artifacts", "reporting_contracts",
}


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first(mapping: Mapping[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    for key in keys:
        if mapping.get(key) not in (None, ""):
            return mapping[key]
    return default


def _declared_paths(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _PATH_KEYS and isinstance(item, str) and item.strip():
                found.append(item.strip())
            elif key in _CONTAINER_KEYS:
                found.extend(_declared_paths(item))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                found.append(item.strip())
            else:
                found.extend(_declared_paths(item))
    return sorted(set(found))


def _capability_names(plugin: Mapping[str, Any]) -> list[str]:
    raw = plugin.get("capabilities")
    names: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.strip():
                names.append(item.strip())
            elif isinstance(item, Mapping):
                name = _first(item, ("capability_id", "name", "display_name"))
                if name not in (None, ""):
                    names.append(str(name).strip())
    elif isinstance(raw, Mapping):
        names.extend(str(key).strip() for key, enabled in raw.items() if enabled)
    return sorted(set(name for name in names if name))


def _artifact_declarations(plugin: Mapping[str, Any]) -> list[dict[str, Any]]:
    declarations: list[dict[str, Any]] = []
    for key in ("dashboard_artifacts", "published_artifacts", "artifacts"):
        raw = plugin.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            declarations.append({
                "artifact_id": str(_first(item, ("artifact_id", "report_id", "name"), "UNKNOWN")),
                "artifact_type": str(_first(item, ("artifact_type", "report_type", "type"), "UNKNOWN")),
                "path": _first(item, ("path", "report_path", "artifact_path", "output_path")),
                "format": str(_first(item, ("format", "file_format"), "UNKNOWN")),
                "authoritative": bool(item.get("authoritative", False)),
                "required": bool(item.get("required", False)),
            })
    declarations.sort(key=lambda item: (item["artifact_id"], str(item.get("path") or "")))
    return declarations


def _safe_path(raw: str, root_dir: Path) -> Path | None:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root_dir / candidate
    try:
        resolved = candidate.resolve(strict=False)
    except OSError:
        return None
    return resolved if resolved.suffix.lower() in {".json", ".csv"} else None


def _read_artifact(path: Path) -> Any:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _walk_mappings(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_mappings(child)


def _metric(payloads: Sequence[Any], keys: Sequence[str]) -> float | None:
    for payload in payloads:
        for mapping in _walk_mappings(payload):
            value = _first(mapping, keys)
            parsed = _number(value)
            if parsed is not None:
                return parsed
    return None


def _count(payloads: Sequence[Any], keys: Sequence[str]) -> int | None:
    for payload in payloads:
        for mapping in _walk_mappings(payload):
            for key in keys:
                value = mapping.get(key)
                if isinstance(value, list):
                    return len(value)
                parsed = _number(value)
                if parsed is not None:
                    return int(parsed)
    return None


def build_strategy_kpis(
    *,
    registry: Mapping[str, Any],
    strategy_allocations: Mapping[str, Any] | None = None,
    root_dir: str | Path = ".",
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return deterministic KPI rows for every registered strategy plugin."""
    root = Path(root_dir)
    allocations = dict(strategy_allocations or {})
    plugins = registry.get("strategy_plugins")
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    if not isinstance(plugins, list):
        return rows, ["Enterprise registry does not contain strategy_plugins."]

    for plugin in plugins:
        if not isinstance(plugin, Mapping):
            continue
        strategy_id = str(_first(plugin, ("strategy_id", "plugin_id", "service_id"), "UNKNOWN"))
        display_name = str(_first(plugin, ("display_name", "strategy_name", "name"), strategy_id))
        capability_names = _capability_names(plugin)
        artifact_declarations = _artifact_declarations(plugin)
        payloads: list[Any] = []
        accepted_paths: list[str] = []
        for raw_path in _declared_paths(plugin):
            path = _safe_path(raw_path, root)
            if path is None:
                warnings.append(f"{strategy_id}: unsupported evidence path {raw_path}")
                continue
            if not path.is_file():
                warnings.append(f"{strategy_id}: declared evidence is missing: {path}")
                continue
            try:
                payloads.append(_read_artifact(path))
                accepted_paths.append(str(path))
            except (OSError, UnicodeError, json.JSONDecodeError, csv.Error) as exc:
                warnings.append(f"{strategy_id}: invalid evidence {path}: {exc}")

        allocated = _number(allocations.get(strategy_id))
        if allocated is None:
            allocated = _metric(payloads, ("allocated_cash", "allocated_capital", "paper_value", "allocation_value")) or 0.0
        portfolio_value = _metric(payloads, ("portfolio_value", "market_value", "current_value", "total_value"))
        realized = _metric(payloads, ("realized_gain", "realized_profit", "realized_pnl", "net_profit"))
        unrealized = _metric(payloads, ("unrealized_gain", "unrealized_profit", "unrealized_pnl"))
        income = _metric(payloads, ("dividend_income", "income_received", "total_income", "projected_annual_income"))
        watchlist = _count(payloads, ("watchlist", "watchlist_count", "candidate_count", "candidates"))
        positions = _count(payloads, ("positions", "holdings", "open_positions", "position_count", "holding_count"))
        opportunity = _metric(payloads, ("opportunity_quality", "opportunity_quality_score", "average_opportunity_score"))
        win_rate = _metric(payloads, ("win_rate", "win_rate_percent"))

        rows.append({
            "strategy_id": strategy_id,
            "display_name": display_name,
            "strategy_type": str(_first(plugin, ("strategy_type", "plugin_type", "bot_type"), "STRATEGY")),
            "lifecycle_status": str(_first(plugin, ("lifecycle_status", "service_lifecycle", "status"), "UNKNOWN")),
            "runtime_status": str(_first(plugin, ("runtime_status", "status"), "UNKNOWN")),
            "health_status": str(_first(plugin, ("health_status", "health"), "UNKNOWN")),
            "readiness": str(_first(plugin, ("readiness", "readiness_status", "status"), "UNKNOWN")),
            "capability_count": len(capability_names),
            "capabilities": capability_names,
            "published_artifact_count": len(artifact_declarations),
            "published_artifacts": artifact_declarations,
            "allocated_capital": round(allocated, 2),
            "portfolio_value": round(portfolio_value, 2) if portfolio_value is not None else None,
            "realized_gain": round(realized, 2) if realized is not None else None,
            "unrealized_gain": round(unrealized, 2) if unrealized is not None else None,
            "income": round(income, 2) if income is not None else None,
            "watchlist_count": watchlist,
            "position_count": positions,
            "opportunity_quality": round(opportunity, 2) if opportunity is not None else None,
            "win_rate_percent": round(win_rate, 2) if win_rate is not None else None,
            "evidence_paths": sorted(set(accepted_paths)),
            "evidence_status": "AVAILABLE" if accepted_paths else "REGISTRY_ONLY",
        })

    rows.sort(key=lambda item: item["strategy_id"])
    return rows, sorted(set(warnings))
