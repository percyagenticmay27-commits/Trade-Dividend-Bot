"""Publish canonical read-only KPI evidence for the Dividend strategy.

This adapter normalizes existing Dividend-owned evidence into the Enterprise KPI
field names consumed by the AI CIO dashboard. It never places orders, moves
capital, changes allocations, or fabricates unavailable metrics.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .dividend_dashboard_evidence import build_dividend_dashboard_evidence

MODULE_NAME = "dividend_strategy_kpi_evidence"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
STRATEGY_ID = "DIVIDEND-001"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
AUTOMATIC_ACTIVATION_ALLOWED = False
REPORTING_ONLY = True

DEFAULT_OUTPUT = Path("results/dividend_strategy_kpi_evidence.json")
WATCHLIST_SOURCES = (
    Path("candidate_discovery.json"),
    Path("results/candidate_discovery.json"),
    Path("watchlist_report.json"),
    Path("results/watchlist_report.json"),
)
OPPORTUNITY_SOURCES = (
    Path("dividend_rankings.json"),
    Path("results/dividend_rankings.json"),
    Path("opportunity_pairing_report.json"),
    Path("results/opportunity_pairing_report.json"),
)
PERFORMANCE_SOURCES = (
    # Canonical DIVIDEND-001 closed-trade performance authority.
    Path("results/dividend_paper_trade_performance.json"),

    # Legacy compatibility fallbacks. These must never override the
    # strategy-owned canonical Dividend performance artifact above.
    Path("results/strategy_performance_analytics.json"),
    Path("strategy_performance_analytics.json"),
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _walk_mappings(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_mappings(child)


def _first_metric(payload: Any, keys: Sequence[str]) -> float | None:
    for mapping in _walk_mappings(payload):
        for key in keys:
            if key not in mapping:
                continue
            parsed = _number(mapping.get(key))
            if parsed is not None:
                return parsed
    return None


def _load_first(root: Path, candidates: Sequence[Path]) -> tuple[Any | None, Path | None]:
    for relative in candidates:
        path = relative if relative.is_absolute() else root / relative
        if not path.is_file():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8")), path
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
    return None, None


def _watchlist_count(payload: Any) -> tuple[int | None, str | None]:
    if payload is None:
        return None, None
    direct = _first_metric(payload, ("watchlist_count",))
    if direct is not None:
        return max(0, int(direct)), "DECLARED_WATCHLIST_COUNT"

    if isinstance(payload, Mapping):
        watchlist = payload.get("watchlist")
        if isinstance(watchlist, list):
            return len(watchlist), "WATCHLIST_LIST_COUNT"
        candidates = payload.get("candidates")
        if isinstance(candidates, list):
            flagged = [
                item for item in candidates
                if isinstance(item, Mapping) and item.get("on_watchlist") is True
            ]
            if flagged:
                return len(flagged), "CANDIDATE_WATCHLIST_FLAG_COUNT"
    return None, None


def _opportunity_quality(payload: Any) -> tuple[float | None, str | None]:
    if payload is None:
        return None, None

    direct = _first_metric(
        payload,
        ("opportunity_quality", "opportunity_quality_score", "average_opportunity_score"),
    )
    if direct is not None:
        return min(100.0, max(0.0, direct)), "DECLARED_OPPORTUNITY_QUALITY"

    if isinstance(payload, Mapping):
        rankings = payload.get("rankings")
        if isinstance(rankings, list):
            scores = [
                _number(item.get("overall_score"))
                for item in rankings
                if isinstance(item, Mapping)
            ]
            scores = [score for score in scores if score is not None]
            if scores:
                return min(100.0, max(0.0, max(scores))), "BEST_DIVIDEND_RANKING_OVERALL_SCORE"

        opportunities = payload.get("opportunities")
        if isinstance(opportunities, list):
            scores = [
                _number(item.get("combined_score"))
                for item in opportunities
                if isinstance(item, Mapping)
            ]
            scores = [score for score in scores if score is not None]
            if scores:
                return min(100.0, max(0.0, max(scores))), "BEST_OPPORTUNITY_PAIRING_COMBINED_SCORE"
    return None, None


def _win_rate(payload: Any) -> tuple[float | None, str | None]:
    """Return DIVIDEND-001's explicit win rate; never infer one from returns."""
    if payload is None:
        return None, None

    if isinstance(payload, Mapping):
        direct_strategy_id = str(payload.get("strategy_id") or "").strip().upper()
        if direct_strategy_id in {STRATEGY_ID, "DIVIDEND"}:
            value = _first_metric(payload, ("win_rate_percent", "win_rate_pct", "win_rate"))
            if value is not None:
                return min(100.0, max(0.0, value)), "DECLARED_DIVIDEND_WIN_RATE"

        for key in ("strategies", "strategy_performance", "performance", "results"):
            rows = payload.get(key)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, Mapping):
                    continue
                strategy_id = str(row.get("strategy_id") or "").strip().upper()
                if strategy_id not in {STRATEGY_ID, "DIVIDEND"}:
                    continue
                value = _first_metric(row, ("win_rate_percent", "win_rate_pct", "win_rate"))
                if value is not None:
                    return min(100.0, max(0.0, value)), "DECLARED_DIVIDEND_WIN_RATE"
    return None, None


def build_dividend_strategy_kpi_evidence(
    root_dir: str | Path = ".",
    *,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    root = Path(root_dir)
    dashboard_evidence = build_dividend_dashboard_evidence(root)
    decision_journal = dashboard_evidence.get("decision_journal")
    decision_journal = decision_journal if isinstance(decision_journal, Mapping) else None
    watchlist_payload, watchlist_path = _load_first(root, WATCHLIST_SOURCES)
    opportunity_payload, opportunity_path = _load_first(root, OPPORTUNITY_SOURCES)
    performance_payload, performance_path = _load_first(root, PERFORMANCE_SOURCES)

    watchlist_count, watchlist_method = _watchlist_count(watchlist_payload)
    opportunity_quality, opportunity_method = _opportunity_quality(opportunity_payload)
    win_rate_percent, win_rate_method = _win_rate(performance_payload)

    sources = {
        "watchlist_count": str(watchlist_path) if watchlist_path else None,
        "opportunity_quality": str(opportunity_path) if opportunity_path else None,
        "win_rate_percent": str(performance_path) if performance_path else None,
    }
    methods = {
        "watchlist_count": watchlist_method,
        "opportunity_quality": opportunity_method,
        "win_rate_percent": win_rate_method,
    }
    missing = [
        metric
        for metric, value in (
            ("watchlist_count", watchlist_count),
            ("opportunity_quality", opportunity_quality),
            ("win_rate_percent", win_rate_percent),
        )
        if value is None
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "generated_at_utc": generated_at_utc or _now_utc(),
        "strategy_id": STRATEGY_ID,
        "watchlist_count": watchlist_count,
        "opportunity_quality": round(opportunity_quality, 2) if opportunity_quality is not None else None,
        "win_rate_percent": round(win_rate_percent, 2) if win_rate_percent is not None else None,
        "decision_journal_status": "AVAILABLE" if decision_journal is not None else "NOT_REPORTED",
        "decision_count": int(decision_journal.get("decision_count", 0)) if decision_journal is not None else 0,
        "decision_journal": decision_journal,
        "metric_sources": sources,
        "calculation_methods": methods,
        "missing_metrics": missing,
        "evidence_status": "AVAILABLE" if not missing else ("PARTIAL" if len(missing) < 3 else "NOT_REPORTED"),
        "paper_trade_mode": True,
        "reporting_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "order_placement_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
        "investor_governance_required": True,
    }


def _atomic_write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return path


def write_dividend_strategy_kpi_evidence(
    root_dir: str | Path = ".",
    output_path: str | Path = DEFAULT_OUTPUT,
) -> Path:
    root = Path(root_dir)
    target = Path(output_path)
    if not target.is_absolute():
        target = root / target
    report = build_dividend_strategy_kpi_evidence(root)
    return _atomic_write(target, json.dumps(report, indent=2, sort_keys=True) + "\n")
