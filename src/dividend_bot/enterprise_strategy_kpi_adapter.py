"""Build read-only per-strategy KPI evidence from Enterprise discovery.

The host consumes declared JSON/CSV artifacts plus canonical host-owned Dividend
KPI evidence. It does not import external strategy code, change allocations, move
capital, or execute broker actions.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.dividend_bot.dividend_dashboard_evidence import (
    build_dividend_dashboard_evidence,
)
from src.dividend_bot.dividend_strategy_kpi_evidence import (
    build_dividend_strategy_kpi_evidence,
)
from src.dividend_bot.enterprise_strategy_discovery import (
    discover_registered_strategies,
)

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
_STRATEGY_ID_ALIASES = {
    "dividend": "DIVIDEND-001",
    "dividend-001": "DIVIDEND-001",
    "dividend_001": "DIVIDEND-001",
    "swing": "SWING-001",
    "swing-001": "SWING-001",
    "swing_001": "SWING-001",
}


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _canonical_strategy_id(value: Any) -> str:
    raw = str(value).strip()
    return _STRATEGY_ID_ALIASES.get(raw.lower(), raw)


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
    return resolved if resolved.suffix.lower() in {".json", ".csv", ".md", ".markdown", ".html"} else None


def _canonical_field_name(value: Any) -> str:
    """Normalize artifact field names without changing their values."""
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _read_artifact(path: Path) -> Any:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix.lower() in {".md", ".markdown", ".html"}:
        return {
            "artifact_text": path.read_text(encoding="utf-8"),
            "artifact_format": path.suffix.lower().lstrip(".").upper(),
            "source_path": str(path),
        }
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {
                _canonical_field_name(key): value
                for key, value in row.items()
                if key is not None
            }
            for row in csv.DictReader(handle)
        ]


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


def _append_host_dividend_evidence(
    *,
    strategy_id: str,
    root: Path,
    payloads: list[Any],
    accepted_paths: list[str],
) -> Mapping[str, Any] | None:
    """Add normalized host-owned Dividend KPI evidence without fabricating metrics."""
    if strategy_id != "DIVIDEND-001":
        return None
    evidence = build_dividend_strategy_kpi_evidence(root)
    payloads.append(evidence)
    sources = evidence.get("metric_sources")
    if isinstance(sources, Mapping):
        for value in sources.values():
            if isinstance(value, str) and value.strip():
                accepted_paths.append(value.strip())
    return evidence


def _host_dividend_dashboard_evidence(
    *,
    strategy_id: str,
    root: Path,
    accepted_paths: list[str],
) -> Mapping[str, Any] | None:
    """Return detailed host-owned Dividend dashboard evidence when source files exist."""
    if strategy_id != "DIVIDEND-001":
        return None
    evidence = build_dividend_dashboard_evidence(root)
    sources = evidence.get("evidence_sources")
    if isinstance(sources, list):
        for value in sources:
            if isinstance(value, str) and value.strip():
                accepted_paths.append(value.strip())
    return evidence


def _detail_list(evidence: Mapping[str, Any] | None, key: str) -> list[dict[str, Any]]:
    if not isinstance(evidence, Mapping):
        return []
    value = evidence.get(key)
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _mapping_at(value: Any, *keys: str) -> Mapping[str, Any] | None:
    current = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current if isinstance(current, Mapping) else None


def _strategy_owned_payloads(
    payloads: Sequence[Any],
    strategy_id: str,
) -> list[Mapping[str, Any]]:
    """Return only payload sections owned by the requested strategy."""
    owned: list[Mapping[str, Any]] = []
    for payload in payloads:
        if not isinstance(payload, Mapping):
            continue
        reported_id = _first(payload, ("strategy_id", "service_id", "plugin_id"))
        if reported_id in (None, "") or _canonical_strategy_id(reported_id) == strategy_id:
            owned.append(payload)
        for collection_key in ("strategy_kpis", "strategies"):
            collection = payload.get(collection_key)
            if not isinstance(collection, list):
                continue
            for item in collection:
                if not isinstance(item, Mapping):
                    continue
                item_id = _first(item, ("strategy_id", "service_id", "plugin_id"))
                if item_id not in (None, "") and _canonical_strategy_id(item_id) == strategy_id:
                    owned.append(item)
    return owned


def _strategy_watchlist_count(
    payloads: Sequence[Any],
    strategy_id: str,
) -> int | None:
    for payload in _strategy_owned_payloads(payloads, strategy_id):
        watchlist = _mapping_at(payload, "dashboard_sections", "watchlist")
        if watchlist is None:
            continue
        parsed = _number(watchlist.get("count"))
        if parsed is not None:
            return int(parsed)
    return None


def _strategy_watchlist_detail(
    payloads: Sequence[Any],
    strategy_id: str,
) -> list[dict[str, Any]]:
    """Read authoritative candidate rows without deriving detail from a count."""
    owned = _strategy_owned_payloads(payloads, strategy_id)
    primary_rows_published = False
    for payload in owned:
        watchlist = _mapping_at(payload, "dashboard_sections", "watchlist")
        evidence = _mapping_at(watchlist, "evidence") if watchlist is not None else None
        rows = evidence.get("rows") if evidence is not None else None
        if isinstance(rows, list):
            primary_rows_published = True
            normalized = [
                dict(item) for item in rows if isinstance(item, Mapping)
            ]
            if normalized:
                return normalized

    # An explicitly published primary rows collection is authoritative even when
    # every declaring artifact reports it empty. Do not revive stale fallback rows.
    if primary_rows_published:
        return []

    # Backward-compatible Swing contract used before dashboard_sections became
    # authoritative. This is intentionally evaluated only when no primary rows
    # collection was published by any strategy-owned artifact.
    for payload in owned:
        evidence = _mapping_at(
            payload,
            "strategy_intelligence",
            "watchlist_evidence",
        )
        rows = evidence.get("rows") if evidence is not None else None
        if isinstance(rows, list):
            normalized = [
                dict(item) for item in rows if isinstance(item, Mapping)
            ]
            if normalized:
                return normalized
    return []


def build_strategy_kpis(
    *,
    registry: Mapping[str, Any],
    strategy_allocations: Mapping[str, Any] | None = None,
    root_dir: str | Path = ".",
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return KPI rows for every strategy discovered from the registry.

    Discovery owns strategy enumeration, identity normalization, duplicate handling,
    and deterministic ordering. This adapter reads declared evidence and the
    canonical host-owned Dividend normalization layers for DIVIDEND-001.
    """
    root = Path(root_dir).resolve(strict=False)
    allocations = dict(strategy_allocations or {})
    discovered, discovery_warnings = discover_registered_strategies(registry)
    rows: list[dict[str, Any]] = []
    warnings: list[str] = list(discovery_warnings)

    for strategy in discovered:
        plugin = strategy.get("plugin")
        if not isinstance(plugin, Mapping):
            warnings.append(
                f"{strategy.get('strategy_id', 'UNKNOWN')}: discovered plugin metadata is unavailable."
            )
            continue

        strategy_id = _canonical_strategy_id(strategy["strategy_id"])
        display_name = str(strategy["display_name"])
        capability_names = _capability_names(plugin)
        artifact_declarations = _artifact_declarations(plugin)
        payloads: list[Any] = []
        accepted_paths: list[str] = []
        repository_root_raw = plugin.get("repository_root")
        evidence_root = (
            Path(str(repository_root_raw)).resolve(strict=False)
            if isinstance(repository_root_raw, str) and repository_root_raw.strip()
            else root
        )

        for raw_path in _declared_paths(plugin):
            path = _safe_path(raw_path, evidence_root)
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

        host_dividend_evidence = _append_host_dividend_evidence(
            strategy_id=strategy_id,
            root=root,
            payloads=payloads,
            accepted_paths=accepted_paths,
        )
        dashboard_evidence = _host_dividend_dashboard_evidence(
            strategy_id=strategy_id,
            root=root,
            accepted_paths=accepted_paths,
        )
        dashboard_sources_available = bool(
            isinstance(dashboard_evidence, Mapping)
            and dashboard_evidence.get("evidence_sources")
        )

        allocated = _number(allocations.get(strategy_id))
        if allocated is None:
            allocated = _metric(
                payloads,
                ("allocated_cash", "allocated_capital", "paper_value", "allocation_value"),
            ) or 0.0

        dashboard_portfolio = (
            _number(dashboard_evidence.get("portfolio_value"))
            if dashboard_sources_available and isinstance(dashboard_evidence, Mapping)
            else None
        )
        portfolio_value = dashboard_portfolio
        if portfolio_value is None:
            portfolio_value = _metric(
                payloads,
                ("portfolio_value", "market_value", "current_value", "total_value"),
            )

        dashboard_realized = (
            _number(dashboard_evidence.get("realized_gain"))
            if dashboard_sources_available and isinstance(dashboard_evidence, Mapping)
            else None
        )
        realized = dashboard_realized
        if realized is None:
            realized = _metric(
                payloads,
                ("realized_gain", "realized_profit", "realized_pnl", "net_profit"),
            )

        dashboard_unrealized = (
            _number(dashboard_evidence.get("unrealized_gain"))
            if dashboard_sources_available and isinstance(dashboard_evidence, Mapping)
            else None
        )
        unrealized = dashboard_unrealized
        if unrealized is None:
            unrealized = _metric(
                payloads,
                ("unrealized_gain", "unrealized_profit", "unrealized_pnl"),
            )

        dashboard_income = (
            _number(dashboard_evidence.get("income"))
            if dashboard_sources_available and isinstance(dashboard_evidence, Mapping)
            else None
        )
        income = dashboard_income
        if income is None:
            income = _metric(
                payloads,
                ("dividend_income", "income_received", "total_income", "projected_annual_income"),
            )

        projected_annual_income = (
            _number(dashboard_evidence.get("projected_annual_income"))
            if dashboard_sources_available and isinstance(dashboard_evidence, Mapping)
            else None
        )
        if projected_annual_income is None:
            projected_annual_income = _metric(payloads, ("projected_annual_income",))

        gross_distribution_income = (
            _number(dashboard_evidence.get("gross_distribution_income"))
            if dashboard_sources_available and isinstance(dashboard_evidence, Mapping)
            else None
        )
        income_adjustments = (
            _number(dashboard_evidence.get("income_adjustments"))
            if dashboard_sources_available and isinstance(dashboard_evidence, Mapping)
            else None
        )
        net_income_received = (
            _number(dashboard_evidence.get("net_income_received"))
            if dashboard_sources_available and isinstance(dashboard_evidence, Mapping)
            else None
        )
        realized_income_event_count = (
            _number(dashboard_evidence.get("realized_income_event_count"))
            if dashboard_sources_available and isinstance(dashboard_evidence, Mapping)
            else None
        )
        positive_income_event_count = (
            _number(dashboard_evidence.get("positive_income_event_count"))
            if dashboard_sources_available and isinstance(dashboard_evidence, Mapping)
            else None
        )
        negative_income_event_count = (
            _number(dashboard_evidence.get("negative_income_event_count"))
            if dashboard_sources_available and isinstance(dashboard_evidence, Mapping)
            else None
        )
        income_accounting_method = (
            dashboard_evidence.get("income_accounting_method")
            if dashboard_sources_available and isinstance(dashboard_evidence, Mapping)
            else None
        )
        income_evidence_source = (
            dashboard_evidence.get("income_evidence_source")
            if dashboard_sources_available and isinstance(dashboard_evidence, Mapping)
            else None
        )

        if host_dividend_evidence is not None:
            host_watchlist = _number(host_dividend_evidence.get("watchlist_count"))
            watchlist = int(host_watchlist) if host_watchlist is not None else None
            opportunity = _number(host_dividend_evidence.get("opportunity_quality"))
            win_rate = _number(host_dividend_evidence.get("win_rate_percent"))
        else:
            watchlist = _strategy_watchlist_count(payloads, strategy_id)
            if watchlist is None:
                watchlist = _count(
                    payloads,
                    ("watchlist", "watchlist_count", "candidate_count", "candidates"),
                )
            opportunity = _metric(
                payloads,
                ("opportunity_quality", "opportunity_quality_score", "average_opportunity_score"),
            )
            win_rate = _metric(payloads, ("win_rate", "win_rate_percent", "win_rate_pct"))

        if dashboard_sources_available and isinstance(dashboard_evidence, Mapping):
            dashboard_positions = _number(dashboard_evidence.get("position_count"))
            positions = int(dashboard_positions) if dashboard_positions is not None else None
        else:
            positions = _count(
                payloads,
                (
                    "positions",
                    "holdings",
                    "open_positions",
                    "open_buckets",
                    "position_count",
                    "holding_count",
                ),
            )

        holdings = _detail_list(dashboard_evidence, "holdings")
        watchlist_detail = _detail_list(dashboard_evidence, "watchlist")
        if not watchlist_detail and strategy_id != "DIVIDEND-001":
            watchlist_detail = _strategy_watchlist_detail(payloads, strategy_id)
        income_events = _detail_list(dashboard_evidence, "income_events")
        alerts = _detail_list(dashboard_evidence, "alerts")
        risk_flags = _detail_list(dashboard_evidence, "risk_flags")
        decision_journal_source = (
            dashboard_evidence.get("decision_journal")
            if isinstance(dashboard_evidence, Mapping)
            else None
        )
        if not isinstance(decision_journal_source, Mapping) and isinstance(host_dividend_evidence, Mapping):
            decision_journal_source = host_dividend_evidence.get("decision_journal")
        decision_journal = (
            dict(decision_journal_source)
            if isinstance(decision_journal_source, Mapping)
            else None
        )
        decision_journal_status = "AVAILABLE" if decision_journal is not None else "NOT_REPORTED"
        decision_count = (
            int(_number(decision_journal.get("decision_count")) or 0)
            if decision_journal is not None
            else 0
        )
        performance_detail = (
            dict(dashboard_evidence.get("performance_detail"))
            if dashboard_sources_available
            and isinstance(dashboard_evidence, Mapping)
            and isinstance(dashboard_evidence.get("performance_detail"), Mapping)
            else {}
        )

        rows.append({
            "strategy_id": strategy_id,
            "display_name": display_name,
            "strategy_type": strategy["strategy_type"],
            "lifecycle_status": strategy["lifecycle_status"],
            "runtime_status": strategy["runtime_status"],
            "health_status": strategy["health_status"],
            "readiness": strategy["readiness"],
            "enabled": bool(strategy["enabled"]),
            "paper_trade_mode": bool(strategy["paper_trade_mode"]),
            "paper_compatible": bool(strategy["paper_compatible"]),
            "advisory_only": bool(strategy["advisory_only"]),
            "reporting_only": bool(strategy["reporting_only"]),
            "capability_count": len(capability_names),
            "capabilities": capability_names,
            "published_artifact_count": len(artifact_declarations),
            "published_artifacts": artifact_declarations,
            "allocated_capital": round(allocated, 2),
            "portfolio_value": round(portfolio_value, 2) if portfolio_value is not None else None,
            "realized_gain": round(realized, 2) if realized is not None else None,
            "unrealized_gain": round(unrealized, 2) if unrealized is not None else None,
            "income": round(income, 2) if income is not None else None,
            "projected_annual_income": round(projected_annual_income, 2) if projected_annual_income is not None else None,
            "gross_distribution_income": round(gross_distribution_income, 2) if gross_distribution_income is not None else None,
            "income_adjustments": round(income_adjustments, 2) if income_adjustments is not None else None,
            "net_income_received": round(net_income_received, 2) if net_income_received is not None else None,
            "realized_income_event_count": int(realized_income_event_count) if realized_income_event_count is not None else None,
            "positive_income_event_count": int(positive_income_event_count) if positive_income_event_count is not None else None,
            "negative_income_event_count": int(negative_income_event_count) if negative_income_event_count is not None else None,
            "income_accounting_method": income_accounting_method,
            "income_evidence_source": income_evidence_source,
            "watchlist_count": watchlist,
            "position_count": positions,
            "opportunity_quality": round(opportunity, 2) if opportunity is not None else None,
            "win_rate_percent": round(win_rate, 2) if win_rate is not None else None,
            "holdings": holdings,
            "positions": holdings,
            "watchlist": watchlist_detail,
            "income_events": income_events,
            "decision_journal_status": decision_journal_status,
            "decision_count": decision_count,
            "decision_journal": decision_journal,
            "performance_detail": performance_detail,
            "alerts": alerts,
            "risk_flags": risk_flags,
            "evidence_paths": sorted(set(accepted_paths)),
            "evidence_root": str(evidence_root),
            "external_evidence": evidence_root != root.resolve(strict=False),
            "evidence_status": "AVAILABLE" if accepted_paths else "REGISTRY_ONLY",
        })

    return rows, sorted(set(warnings))