"""Run the final Phase 7.4 deployment validation and documentation freeze."""
from __future__ import annotations

import argparse
from typing import Sequence

from src.dividend_bot.enterprise_deployment_release_gate import (
    validate_and_write_deployment_release,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate paper-only deployment readiness and freeze documentation"
    )
    parser.add_argument("--root-dir", default=".")
    parser.add_argument("--results-dir", default="results")
    args = parser.parse_args(argv)
    report = validate_and_write_deployment_release(
        root_dir=args.root_dir, results_dir=args.results_dir
    )
    print(f"Release status: {report['release_status']}")
    print(f"Stability soak: {report['soak_status']}")
    print(f"Documentation freeze: {report['documentation_freeze_status']}")
    print(f"Frozen files: {report['freeze_file_count']}")
    for error in report["errors"]:
        print(f"ERROR: {error}")
    for warning in report["warnings"]:
        print(f"WARNING: {warning}")
    return 1 if report["release_status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
