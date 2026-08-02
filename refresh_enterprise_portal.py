"""Run the complete read-only Enterprise portal refresh in one command.

This orchestrator preserves the tested base dashboard refresh, publishes Phase 3
intelligence from those exact artifacts, and then generates strategy-scoped
Decision Journal artifacts for the current Dividend and Swing KPI workspaces.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Sequence

from publish_enterprise_dashboard_intelligence import (
    publish_enterprise_dashboard_intelligence,
)
from refresh_enterprise_dashboards import refresh_enterprise_dashboards
from src.dividend_bot.strategy_decision_journal_generator import (
    generate_all_strategy_decision_journals,
)

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True


def refresh_enterprise_portal(
    *,
    root_dir: str | Path = ".",
    results_dir: str | Path = "results",
    state_dir: str | Path = "state",
) -> dict[str, Any]:
    """Refresh dashboards, intelligence, and strategy journals atomically per file."""
    root = Path(root_dir)
    requested_results = Path(results_dir)
    resolved_results = (
        requested_results if requested_results.is_absolute() else root / requested_results
    )

    dashboard_summary = refresh_enterprise_dashboards(
        root_dir=root,
        results_dir=requested_results,
        state_dir=state_dir,
    )
    intelligence_summary = publish_enterprise_dashboard_intelligence(
        results_dir=resolved_results,
    )
    journal_summary = generate_all_strategy_decision_journals(
        results_dir=resolved_results,
    )

    dashboard_ids = list(
        dashboard_summary.get("strategy_discovery_summary", {}).get("strategy_ids", [])
    )
    intelligence_ids = list(intelligence_summary.get("strategy_ids", []))
    warnings = (
        list(dashboard_summary.get("warnings", []))
        + list(intelligence_summary.get("warnings", []))
        + list(journal_summary.get("warnings", []))
    )
    errors = list(dashboard_summary.get("errors", [])) + list(
        journal_summary.get("errors", [])
    )

    if dashboard_ids != intelligence_ids:
        errors.append(
            "Enterprise portal refresh strategy IDs did not remain identical between "
            "dashboard discovery and Phase 3 intelligence publication."
        )

    return {
        "refresh_complete": not errors,
        "dashboard_refresh": dashboard_summary,
        "intelligence_publication": intelligence_summary,
        "decision_journal_generation": journal_summary,
        "registered_strategy_count": int(
            intelligence_summary.get("registered_strategy_count", 0) or 0
        ),
        "strategy_ids": intelligence_ids,
        "paths": {
            **dict(dashboard_summary.get("paths", {})),
            **{
                f"intelligence_{key}": value
                for key, value in intelligence_summary.get("paths", {}).items()
            },
            **{
                f"journal_{key}": value
                for key, value in journal_summary.get("paths", {}).items()
            },
        },
        "warnings": sorted(set(str(item) for item in warnings if item)),
        "errors": sorted(set(str(item) for item in errors if item)),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "read_only": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refresh all read-only Enterprise portal dashboard artifacts"
    )
    parser.add_argument("--root-dir", default=".")
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--state-dir", default="state")
    args = parser.parse_args(argv)

    try:
        summary = refresh_enterprise_portal(
            root_dir=args.root_dir,
            results_dir=args.results_dir,
            state_dir=args.state_dir,
        )
    except Exception as exc:
        print(f"Enterprise portal refresh failed: {exc}")
        return 1

    print(f"Refresh complete: {summary['refresh_complete']}")
    print(f"Registered strategies: {summary['registered_strategy_count']}")
    print("Strategy IDs: " + (", ".join(summary["strategy_ids"]) or "none"))
    for name, path in summary["paths"].items():
        print(f"{name}: {path}")
    for warning in summary["warnings"]:
        print(f"WARNING: {warning}")
    for error in summary["errors"]:
        print(f"ERROR: {error}")
    return 0 if summary["refresh_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
