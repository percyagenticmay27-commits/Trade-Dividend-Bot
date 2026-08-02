"""Execute and accept one real paper-only Enterprise dashboard cycle."""
from __future__ import annotations

import argparse
from typing import Sequence

from src.dividend_bot.enterprise_unified_dashboard_cycle_acceptance import (
    run_and_accept_unified_dashboard_cycle,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Execute and accept a real unified Enterprise dashboard cycle"
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
    report = run_and_accept_unified_dashboard_cycle(
        root_dir=args.root_dir,
        results_dir=args.results_dir,
        state_dir=args.state_dir,
        required_strategy_ids=(
            args.required_strategies
            if args.required_strategies is not None
            else ("DIVIDEND-001", "SWING-001")
        ),
    )
    print(f"Acceptance status: {report['acceptance_status']}")
    print(f"Cycle status: {report['cycle_status']}")
    print(f"Required artifacts: {report['required_artifact_count']}")
    print(f"Protected state unchanged: {report['protected_state_unchanged']}")
    print(f"Errors: {len(report['errors'])}")
    print(f"Warnings: {len(report['warnings'])}")
    for error in report["errors"]:
        print(f"ERROR: {error}")
    for warning in report["warnings"]:
        print(f"WARNING: {warning}")
    return 0 if report["acceptance_status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
