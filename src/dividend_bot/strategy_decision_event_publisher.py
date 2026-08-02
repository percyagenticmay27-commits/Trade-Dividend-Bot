"""Append-only, paper-only publication boundary for strategy decision events.

Strategies publish their own decision evidence here. The publisher validates each
entry against the shared Decision Journal contract, prevents cross-strategy writes,
deduplicates by decision_id, and atomically updates the strategy-owned source file.
It does not calculate scores, select investments, move capital, or execute trades.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping

from .strategy_decision_journal import normalize_decision

MODULE_NAME = "strategy_decision_event_publisher"
MODULE_VERSION = "1.0.0"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
READ_ONLY_CONSUMER = True

STRATEGY_CONFIG = {
    "DIVIDEND-001": {
        "strategy_kind": "DIVIDEND",
        "source_name": "dividend_strategy_decisions.json",
    },
    "SWING-001": {
        "strategy_kind": "SWING",
        "source_name": "swing_strategy_decisions.json",
    },
}


class DecisionEventPublicationError(ValueError):
    """Raised when a strategy attempts to publish an invalid decision event."""


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _read_existing(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DecisionEventPublicationError(
            f"Existing decision source could not be read: {path}: {exc}"
        ) from exc
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, Mapping):
        rows = payload.get("decisions", [])
    else:
        raise DecisionEventPublicationError("Existing decision source must be JSON object or list")
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise DecisionEventPublicationError("Existing decision source contains invalid decisions")
    return [dict(row) for row in rows]


def publish_strategy_decision_event(
    event: Mapping[str, Any],
    *,
    results_dir: str | Path = "results",
    replace_existing: bool = False,
) -> dict[str, Any]:
    """Validate and publish one strategy-owned decision event.

    Duplicate decision IDs are idempotent when payloads match. A conflicting
    duplicate is rejected unless replace_existing=True is explicitly supplied.
    """
    if not isinstance(event, Mapping):
        raise DecisionEventPublicationError("event must be an object")
    strategy_id = str(event.get("strategy_id") or "").strip()
    config = STRATEGY_CONFIG.get(strategy_id)
    if config is None:
        raise DecisionEventPublicationError(f"Unsupported strategy_id: {strategy_id or 'missing'}")

    normalized = normalize_decision(
        event,
        strategy_id=strategy_id,
        strategy_kind=str(config["strategy_kind"]),
    )
    source_path = Path(results_dir) / str(config["source_name"])
    existing = _read_existing(source_path)

    decision_id = normalized["decision_id"]
    match_index = next(
        (index for index, row in enumerate(existing) if str(row.get("decision_id")) == decision_id),
        None,
    )
    publication_status = "PUBLISHED"
    if match_index is not None:
        current = normalize_decision(
            existing[match_index],
            strategy_id=strategy_id,
            strategy_kind=str(config["strategy_kind"]),
        )
        if current == normalized:
            publication_status = "ALREADY_PUBLISHED"
        elif replace_existing:
            existing[match_index] = normalized
            publication_status = "REPLACED"
        else:
            raise DecisionEventPublicationError(
                f"Conflicting duplicate decision_id rejected: {decision_id}"
            )
    else:
        existing.append(normalized)

    existing.sort(key=lambda row: str(row.get("decision_timestamp") or ""), reverse=True)
    payload = {
        "schema_version": "1.0",
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "strategy_id": strategy_id,
        "strategy_kind": config["strategy_kind"],
        "sort_order": "NEWEST_FIRST",
        "decision_count": len(existing),
        "decisions": existing,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
    }
    if publication_status != "ALREADY_PUBLISHED":
        _atomic_write(source_path, payload)

    return {
        "publication_status": publication_status,
        "strategy_id": strategy_id,
        "strategy_kind": config["strategy_kind"],
        "decision_id": decision_id,
        "decision_count": len(existing),
        "path": str(source_path),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
    }
