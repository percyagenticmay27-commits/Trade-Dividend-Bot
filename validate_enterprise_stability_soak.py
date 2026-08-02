"""Capture and validate Phase 7.3 long-duration stability evidence."""
from __future__ import annotations

import argparse
from typing import Sequence

from src.dividend_bot.enterprise_stability_soak_validation import (
    capture_and_validate_stability_soak,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture and validate paper-only Enterprise soak evidence"
    )
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--minimum-samples", type=int, default=7)
    parser.add_argument("--minimum-hours", type=float, default=168.0)
    parser.add_argument("--maximum-gap-hours", type=float, default=36.0)
    args = parser.parse_args(argv)
    report = capture_and_validate_stability_soak(
        results_dir=args.results_dir,
        capture=not args.validate_only,
        minimum_samples=args.minimum_samples,
        minimum_duration_hours=args.minimum_hours,
        maximum_gap_hours=args.maximum_gap_hours,
    )
    print(f"Soak status: {report['soak_status']}")
    print(f"Samples: {report['sample_count']} / {report['minimum_samples']}")
    print(
        f"Duration: {report['duration_hours']} / "
        f"{report['minimum_duration_hours']} hours"
    )
    for error in report["errors"]:
        print(f"ERROR: {error}")
    for warning in report["warnings"]:
        print(f"WARNING: {warning}")
    return 1 if report["soak_status"] == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
