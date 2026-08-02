"""Evidence-first generators for strategy-scoped Decision Journal artifacts.

The generator never invents decisions. It reads compatible strategy-owned source
records when available and otherwise publishes a valid empty journal with an
explicit warning so the UI renderer can still operate safely.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable, Mapping, Sequence

from .strategy_decision_journal import build_strategy_decision_journal

MODULE_NAME = "strategy_decision_journal_generator"
MODULE_VERSION = "1.0.0"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
READ_ONLY = True

DIVIDEND_STRATEGY_ID = "DIVIDEND-001"
SWING_STRATEGY_ID = "SWING-001"

DEFAULT_DIVIDEND_SOURCES = (
    "dividend_strategy_decisions.json",
    "dividend_decision_journal_source.json",
    "dividend_decisions.json",
)
DEFAULT_SWING_SOURCES = (
    "swing_strategy_decisions.json",
    "swing_decision_journal_source.json",
    "swing_decisions.json",
)


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _extract_rows(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]
    if not isinstance(payload, Mapping):
        return []
    for key in ("decisions", "entries", "journal_entries", "records"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, Mapping)]
    return []


def _read_source_rows(
    source_paths: Iterable[Path], *, strategy_id: str
) -> tuple[list[Mapping[str, Any]], list[str], list[str]]:
    rows: list[Mapping[str, Any]] = []
    warnings: list[str] = []
    used_sources: list[str] = []

    for path in source_paths:
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"Decision source could not be read: {path}: {exc}")
            continue

        extracted = _extract_rows(payload)
        if not extracted:
            warnings.append(f"Decision source contained no compatible records: {path}")
            continue

        accepted = 0
        for row in extracted:
            row_strategy_id = str(row.get("strategy_id") or "").strip()
            if row_strategy_id and row_strategy_id != strategy_id:
                continue
            rows.append(dict(row))
            accepted += 1
        if accepted:
            used_sources.append(str(path))

    return rows, warnings, used_sources


def _resolve_sources(
    results_dir: Path,
    supplied: Sequence[str | Path] | None,
    defaults: Sequence[str],
) -> list[Path]:
    values: Sequence[str | Path] = supplied if supplied is not None else defaults
    resolved: list[Path] = []
    for value in values:
        path = Path(value)
        resolved.append(path if path.is_absolute() else results_dir / path)
    return resolved


def generate_strategy_decision_journal(
    *,
    results_dir: str | Path,
    strategy_id: str,
    strategy_kind: str,
    strategy_name: str,
    output_name: str,
    source_paths: Sequence[str | Path] | None = None,
    default_source_names: Sequence[str] = (),
) -> dict[str, Any]:
    """Generate one validated journal from recorded evidence or a safe empty state."""
    results = Path(results_dir)
    sources = _resolve_sources(results, source_paths, default_source_names)
    rows, warnings, used_sources = _read_source_rows(sources, strategy_id=strategy_id)

    journal = build_strategy_decision_journal(
        strategy_id=strategy_id,
        strategy_kind=strategy_kind,
        strategy_name=strategy_name,
        decisions=rows,
    )
    journal["generated_by"] = MODULE_NAME
    journal["generator_version"] = MODULE_VERSION
    journal["evidence_source_count"] = len(used_sources)
    journal["evidence_sources"] = used_sources
    journal["evidence_status"] = "AVAILABLE" if rows else "NOT_REPORTED"

    if not rows:
        warnings.append(
            f"No {strategy_kind.upper()} decision evidence was available; "
            "published a safe empty strategy Decision Journal."
        )

    output_path = results / output_name
    _atomic_write_json(output_path, journal)
    return {
        "strategy_id": strategy_id,
        "strategy_kind": strategy_kind.upper(),
        "decision_count": journal["decision_count"],
        "evidence_status": journal["evidence_status"],
        "path": str(output_path),
        "sources": used_sources,
        "warnings": sorted(set(warnings)),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "read_only": True,
    }


def generate_all_strategy_decision_journals(
    *,
    results_dir: str | Path = "results",
    dividend_sources: Sequence[str | Path] | None = None,
    swing_sources: Sequence[str | Path] | None = None,
) -> dict[str, Any]:
    """Generate the current Dividend and Swing journal artifacts."""
    dividend = generate_strategy_decision_journal(
        results_dir=results_dir,
        strategy_id=DIVIDEND_STRATEGY_ID,
        strategy_kind="DIVIDEND",
        strategy_name="Dividend Income Strategy",
        output_name="dividend_strategy_decision_journal.json",
        source_paths=dividend_sources,
        default_source_names=DEFAULT_DIVIDEND_SOURCES,
    )
    swing = generate_strategy_decision_journal(
        results_dir=results_dir,
        strategy_id=SWING_STRATEGY_ID,
        strategy_kind="SWING",
        strategy_name="Swing Trading Strategy",
        output_name="swing_strategy_decision_journal.json",
        source_paths=swing_sources,
        default_source_names=DEFAULT_SWING_SOURCES,
    )
    warnings = sorted(set(dividend["warnings"] + swing["warnings"]))
    return {
        "generation_complete": True,
        "journals": {
            DIVIDEND_STRATEGY_ID: dividend,
            SWING_STRATEGY_ID: swing,
        },
        "paths": {
            "dividend_decision_journal": dividend["path"],
            "swing_decision_journal": swing["path"],
        },
        "decision_count": dividend["decision_count"] + swing["decision_count"],
        "warnings": warnings,
        "errors": [],
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "read_only": True,
    }
