"""Validate the unified Enterprise AI CIO dashboard artifact set."""
from __future__ import annotations

import argparse
from typing import Sequence

from src.dividend_bot.enterprise_unified_dashboard_validation import (
    validate_and_write_unified_dashboard,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate read-only unified Enterprise dashboard artifacts"
    )
    parser.add_argument("--results-dir", default="results")
    parser.add_argument(
        "--required-strategy",
        action="append",
        dest="required_strategies",
        default=None,
    )
    args = parser.parse_args(argv)

    report = validate_and_write_unified_dashboard(
        results_dir=args.results_dir,
        required_strategy_ids=(
            args.required_strategies
            if args.required_strategies is not None
            else ("DIVIDEND-001", "SWING-001")
        ),
    )
    print(f"Validation status: {report['validation_status']}")
    print(f"Strategies: {', '.join(report['kpi_strategy_ids']) or 'none'}")
    print(f"Errors: {len(report['errors'])}")
    print(f"Warnings: {len(report['warnings'])}")
    for error in report["errors"]:
        print(f"ERROR: {error}")
    for warning in report["warnings"]:
        print(f"WARNING: {warning}")
    return 0 if report["validation_status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
