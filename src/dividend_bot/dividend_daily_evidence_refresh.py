"""Refresh Dividend-owned evidence required by Enterprise dashboards.

This module is a reporting-only bridge between the legacy operational paper cycle
and the newer Dividend intelligence/reporting pipeline. It never moves capital,
places orders, changes allocations, or enables broker execution.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
AUTOMATIC_ACTIVATION_ALLOWED = False
REPORTING_ONLY = True


def _read_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, dict) else {}


def refresh_dividend_daily_evidence(root_dir: str | Path = ".") -> dict[str, Any]:
    """Generate Dividend intelligence evidence and canonical Enterprise KPI evidence.

    Execution order matters:
    1. Run the approved Dividend intelligence stages and refresh market evidence.
    2. Rebuild per-symbol momentum from that same market snapshot.
    3. Rebuild Dividend Ranking so monitoring decisions use current evidence.
    4. Build the explicit Dividend strategy watchlist from ranked, non-held candidates.
    5. Build candidate discovery so WATCHLIST is visible as an authoritative source.
    6. Reconstruct realized DIVIDEND-001 paper performance.
    7. Publish canonical income/payment evidence.
    8. Publish the current holding-level portfolio snapshot from paper state.
    9. Publish canonical DIVIDEND-001 KPI evidence for Enterprise dashboards.

    The routine is reporting-only. Existing paper state and allocations are not
    modified by this bridge.
    """
    from run_daily_dividend_cycle import run_daily_dividend_cycle
    from candidate_discovery_engine import write_candidate_discovery
    from dividend_ranking_engine import build_dividend_ranking_report
    from dividend_watchlist_engine import write_dividend_watchlist
    from src.dividend_bot.market_momentum_evidence import write_market_momentum_report
    from src.dividend_bot.dividend_paper_trade_performance import (
        write_dividend_paper_trade_performance,
    )
    from src.dividend_bot.dividend_strategy_kpi_evidence import (
        write_dividend_strategy_kpi_evidence,
    )
    from src.dividend_bot.dividend_income_payment_evidence import (
        write_income_payment_evidence,
    )
    from src.dividend_bot.dividend_portfolio_snapshot_evidence import (
        write_portfolio_snapshot_evidence,
    )

    root = Path(root_dir)
    cycle = run_daily_dividend_cycle(root_path=str(root))

    market_snapshot = _read_mapping(root / "market_data_snapshot.json")
    momentum_path = write_market_momentum_report(
        market_snapshot,
        root_dir=root,
        output_path="momentum_score_report.json",
    )
    ranking = build_dividend_ranking_report(root_path=str(root))
    (root / "dividend_rankings.json").write_text(
        json.dumps(ranking, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    watchlist = write_dividend_watchlist(root_path=root)
    candidate = write_candidate_discovery(root_path=str(root))
    performance_path = write_dividend_paper_trade_performance(
        root_dir=root,
        output_path="results/dividend_paper_trade_performance.json",
    )
    income_evidence = write_income_payment_evidence(root)
    portfolio_snapshot_path = write_portfolio_snapshot_evidence(root)
    evidence_path = write_dividend_strategy_kpi_evidence(root_dir=root)

    momentum_entries = _read_mapping(momentum_path).get("entries", [])
    return {
        "status": "COMPLETE" if not cycle.get("errors") else "PARTIAL",
        "daily_dividend_cycle_status": cycle.get("run_status"),
        "candidate_count": int(candidate.get("candidate_count", 0) or 0),
        "watchlist_count": int(watchlist.get("watchlist_count", 0) or 0),
        "watchlist_evidence_path": str(root / "watchlist_report.json"),
        "momentum_symbol_count": len(momentum_entries) if isinstance(momentum_entries, list) else 0,
        "ranking_count": int(ranking.get("ranking_count", 0) or 0),
        "momentum_evidence_path": str(momentum_path),
        "performance_evidence_path": str(performance_path),
        "portfolio_snapshot_path": str(portfolio_snapshot_path),
        "payment_history_path": income_evidence["payment_history_path"],
        "upcoming_payments_path": income_evidence["upcoming_payments_path"],
        "payment_record_count": income_evidence["payment_record_count"],
        "upcoming_payment_record_count": income_evidence["upcoming_record_count"],
        "payment_evidence_status": income_evidence["payment_evidence_status"],
        "upcoming_evidence_status": income_evidence["upcoming_evidence_status"],
        "kpi_evidence_path": str(evidence_path),
        "errors": list(cycle.get("errors", [])) + list(watchlist.get("errors", [])),
        "warnings": list(cycle.get("warnings", [])) + list(watchlist.get("warnings", [])),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "order_placement_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
        "reporting_only": True,
    }
