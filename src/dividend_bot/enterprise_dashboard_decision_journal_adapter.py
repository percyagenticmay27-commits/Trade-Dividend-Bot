"""Attach strategy-owned Decision Journals to Enterprise dashboard KPI rows.

This adapter is read-only and paper-only. It matches canonical journal artifacts
to KPI rows strictly by strategy_id and never imports strategy production code,
changes calculations, moves capital, contacts a broker, or places orders.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True
READ_ONLY = True

DEFAULT_JOURNAL_PATTERN = "*_strategy_decision_journal.json"


def _read_journal(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, f"Invalid strategy Decision Journal {path}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"Invalid strategy Decision Journal {path}: root must be an object"
    return payload, None


def _journal_safety_error(payload: Mapping[str, Any], path: Path) -> str | None:
    if payload.get("paper_trade_mode") is not True:
        return f"Unsafe strategy Decision Journal rejected: {path}: paper_trade_mode must be true"
    if payload.get("live_trading_enabled") is not False:
        return f"Unsafe strategy Decision Journal rejected: {path}: live_trading_enabled must be false"
    if payload.get("broker_execution_enabled") is not False:
        return f"Unsafe strategy Decision Journal rejected: {path}: broker_execution_enabled must be false"
    if payload.get("read_only") is not True:
        return f"Unsafe strategy Decision Journal rejected: {path}: read_only must be true"
    return None


def _cross_strategy_error(payload: Mapping[str, Any], path: Path) -> str | None:
    strategy_id = str(payload.get("strategy_id") or "").strip()
    if not strategy_id:
        return f"Invalid strategy Decision Journal {path}: strategy_id is required"
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        return f"Invalid strategy Decision Journal {path}: decisions must be a list"
    for decision in decisions:
        if not isinstance(decision, Mapping):
            return f"Invalid strategy Decision Journal {path}: decision entries must be objects"
        entry_strategy_id = str(decision.get("strategy_id") or strategy_id).strip()
        if entry_strategy_id != strategy_id:
            return (
                f"Cross-strategy Decision Journal entry rejected: {path}: "
                f"expected {strategy_id}, got {entry_strategy_id}"
            )
    return None


def load_strategy_decision_journals(
    results_dir: str | Path,
    *,
    pattern: str = DEFAULT_JOURNAL_PATTERN,
) -> tuple[dict[str, dict[str, Any]], dict[str, str], list[str]]:
    """Load safe canonical journals into a deterministic strategy-id index."""
    directory = Path(results_dir)
    journals: dict[str, dict[str, Any]] = {}
    paths: dict[str, str] = {}
    warnings: list[str] = []

    if not directory.is_dir():
        return journals, paths, warnings

    for path in sorted(directory.glob(pattern)):
        payload, warning = _read_journal(path)
        if warning:
            warnings.append(warning)
            continue
        safety_error = _journal_safety_error(payload, path)
        if safety_error:
            warnings.append(safety_error)
            continue
        strategy_error = _cross_strategy_error(payload, path)
        if strategy_error:
            warnings.append(strategy_error)
            continue

        strategy_id = str(payload["strategy_id"]).strip()
        if strategy_id in journals:
            warnings.append(
                f"Duplicate strategy Decision Journal ignored: {strategy_id}: {path}"
            )
            continue
        journals[strategy_id] = payload
        paths[strategy_id] = str(path)

    return journals, paths, sorted(set(warnings))


def attach_strategy_decision_journals(
    strategy_kpis: Sequence[Mapping[str, Any]],
    *,
    results_dir: str | Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Copy KPI v1.0 rows and add optional strategy-scoped journal presentation data."""
    journals, paths, warnings = load_strategy_decision_journals(results_dir)
    enriched: list[dict[str, Any]] = []

    for source_row in strategy_kpis:
        row = dict(source_row)
        strategy_id = str(row.get("strategy_id") or "").strip()
        journal = journals.get(strategy_id)
        journal_path = paths.get(strategy_id)
        if journal is None:
            embedded = row.get("decision_journal")
            if isinstance(embedded, Mapping):
                safety_error = _journal_safety_error(
                    embedded, Path(f"embedded:{strategy_id}")
                )
                strategy_error = _cross_strategy_error(
                    embedded, Path(f"embedded:{strategy_id}")
                )
                if safety_error or strategy_error:
                    warnings.append(str(safety_error or strategy_error))
                else:
                    journal = dict(embedded)
                    journal_path = "EMBEDDED_HOST_EVIDENCE"
        if journal is None:
            row["decision_journal"] = None
            row["decision_journal_status"] = "NOT_REPORTED"
            row["decision_count"] = 0
            row["decision_journal_path"] = None
        else:
            decision_count = int(journal.get("decision_count", 0) or 0)
            row["decision_journal"] = dict(journal)
            row["decision_journal_status"] = (
                "AVAILABLE" if decision_count else "EMPTY"
            )
            row["decision_count"] = decision_count
            row["decision_journal_path"] = journal_path
        enriched.append(row)

    return enriched, warnings
