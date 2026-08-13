"""Publish the canonical Dividend portfolio snapshot for Enterprise dashboards.

The snapshot is derived from current paper state through the existing Dividend
dashboard evidence builder. It is reporting-only and never mutates paper state.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .dividend_dashboard_evidence import build_dividend_dashboard_evidence

PAPER_TRADE_MODE = True
REPORTING_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
DEFAULT_OUTPUT = Path("results/portfolio_snapshot.json")


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_portfolio_snapshot_evidence(
    dashboard_evidence: Mapping[str, Any],
    *,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    holdings = dashboard_evidence.get("holdings")
    records = [
        dict(item) for item in holdings
        if isinstance(item, Mapping)
    ] if isinstance(holdings, list) else []
    return {
        "schema_version": "1.0",
        "generated_at_utc": generated_at_utc or _now_utc(),
        "strategy_id": "DIVIDEND-001",
        "evidence_status": "AVAILABLE" if records else "AVAILABLE_EMPTY",
        "record_count": len(records),
        "records": records,
        "portfolio_value": dashboard_evidence.get("portfolio_value"),
        "active_position_count": dashboard_evidence.get("active_position_count", 0),
        "reserve_position_count": dashboard_evidence.get("reserve_position_count", 0),
        "source": "paper_state.json",
        "empty_state_reason": (
            None if records
            else "No current paper holdings or SGOV reserve positions are recorded."
        ),
        "paper_trade_mode": True,
        "reporting_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
    }


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            json.dump(dict(payload), handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return path


def write_portfolio_snapshot_evidence(
    root_dir: str | Path = ".",
    output_path: str | Path = DEFAULT_OUTPUT,
) -> Path:
    root = Path(root_dir)
    target = Path(output_path)
    if not target.is_absolute():
        target = root / target
    evidence = build_dividend_dashboard_evidence(root)
    return _atomic_write_json(
        target,
        build_portfolio_snapshot_evidence(evidence),
    )
