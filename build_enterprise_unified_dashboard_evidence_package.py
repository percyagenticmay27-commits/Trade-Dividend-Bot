"""Build the Phase 6.5 Enterprise unified dashboard evidence package."""
from __future__ import annotations

import argparse
from typing import Sequence

from src.dividend_bot.enterprise_unified_dashboard_evidence_package import (
    build_unified_dashboard_evidence_package,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run acceptance and package verified Enterprise dashboard evidence"
    )
    parser.add_argument("--root-dir", default=".")
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--state-dir", default="state")
    args = parser.parse_args(argv)
    report = build_unified_dashboard_evidence_package(
        root_dir=args.root_dir,
        results_dir=args.results_dir,
        state_dir=args.state_dir,
    )
    print(f"Package status: {report['package_status']}")
    print(f"Acceptance status: {report['acceptance_status']}")
    print(f"UI verification: {report['verification_status']}")
    print(f"Artifacts: {report['artifact_count']}")
    if report["package"]:
        print(f"Package: {report['package']['path']}")
        print(f"SHA-256: {report['package']['sha256']}")
    for error in report["errors"]:
        print(f"ERROR: {error}")
    for warning in report["warnings"]:
        print(f"WARNING: {warning}")
    return 0 if report["package_status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
