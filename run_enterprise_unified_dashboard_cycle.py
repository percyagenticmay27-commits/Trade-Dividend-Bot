"""Run one paper-only Enterprise unified dashboard reporting cycle."""
from __future__ import annotations

import argparse
from typing import Sequence

from src.dividend_bot.enterprise_unified_dashboard_cycle import (
    run_unified_dashboard_cycle,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate, refresh, and validate Enterprise dashboard artifacts"
    )
    parser.add_argument("--root-dir", default=".")
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--state-dir", default="state")
    parser.add_argument(
        "--required-strategy",
        action="append",
        dest="required_strategies",
        default=None,
    )
    args = parser.parse_args(argv)
    summary = run_unified_dashboard_cycle(
        root_dir=args.root_dir,
        results_dir=args.results_dir,
        state_dir=args.state_dir,
        required_strategy_ids=(
            args.required_strategies
            if args.required_strategies is not None
            else ("DIVIDEND-001", "SWING-001")
        ),
    )
    print(f"Cycle status: {summary['cycle_status']}")
    for name, step in summary["steps"].items():
        print(f"{name}: {step['status']}")
    print(f"Errors: {len(summary['errors'])}")
    print(f"Warnings: {len(summary['warnings'])}")
    for error in summary["errors"]:
        print(f"ERROR: {error}")
    for warning in summary["warnings"]:
        print(f"WARNING: {warning}")
    return 0 if summary["cycle_status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
