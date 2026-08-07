"""Refresh Dividend-owned evidence required by Enterprise dashboards.

This module is a reporting-only bridge between the legacy operational paper cycle
and the newer Dividend intelligence/reporting pipeline. It never moves capital,
places orders, changes allocations, or enables broker execution.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
AUTOMATIC_ACTIVATION_ALLOWED = False
REPORTING_ONLY = True


def refresh_dividend_daily_evidence(root_dir: str | Path = ".") -> dict[str, Any]:
    """Generate Dividend intelligence evidence and canonical Enterprise KPI evidence.

    Execution order matters:
    1. Run the approved Dividend intelligence stages so ranking and pairing
       artifacts exist.
    2. Build candidate discovery after those reports are available.
    3. Reconstruct realized DIVIDEND-001 paper performance from the authoritative
       operational paper_trade_log.csv.
    4. Publish canonical DIVIDEND-001 KPI evidence for Enterprise dashboards.

    The routine is reporting-only. Existing paper state and allocations are not
    modified by this bridge.
    """
    from run_daily_dividend_cycle import run_daily_dividend_cycle
    from candidate_discovery_engine import write_candidate_discovery
    from src.dividend_bot.dividend_paper_trade_performance import (
        write_dividend_paper_trade_performance,
    )
    from src.dividend_bot.dividend_strategy_kpi_evidence import (
        write_dividend_strategy_kpi_evidence,
    )

    root = Path(root_dir)
    cycle = run_daily_dividend_cycle(root_path=str(root))
    candidate = write_candidate_discovery(root_path=str(root))
    performance_path = write_dividend_paper_trade_performance(
        root_dir=root,
        output_path="results/strategy_performance_analytics.json",
    )
    evidence_path = write_dividend_strategy_kpi_evidence(root_dir=root)

    return {
        "status": "COMPLETE" if not cycle.get("errors") else "PARTIAL",
        "daily_dividend_cycle_status": cycle.get("run_status"),
        "candidate_count": int(candidate.get("candidate_count", 0) or 0),
        "watchlist_count": int(candidate.get("watchlist_count", 0) or 0),
        "performance_evidence_path": str(performance_path),
        "kpi_evidence_path": str(evidence_path),
        "errors": list(cycle.get("errors", [])),
        "warnings": list(cycle.get("warnings", [])),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "order_placement_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
        "reporting_only": True,
    }
