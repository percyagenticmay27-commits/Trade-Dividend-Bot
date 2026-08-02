"""Run the Phase 7.1 paper-only production-hardening baseline audit."""
from __future__ import annotations

import argparse
from typing import Sequence

from src.dividend_bot.enterprise_production_hardening_audit import (
    audit_and_write_production_hardening,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit Enterprise production hardening without changing runtime state"
    )
    parser.add_argument("--root-dir", default=".")
    parser.add_argument("--results-dir", default="results")
    args = parser.parse_args(argv)
    report = audit_and_write_production_hardening(
        root_dir=args.root_dir,
        results_dir=args.results_dir,
    )
    print(f"Hardening status: {report['hardening_status']}")
    print(f"Evidence package: {report['package_status']}")
    print(
        "Package SHA-256 verified: "
        f"{report['package_expected_sha256'] == report['package_actual_sha256']}"
    )
    print(f"Errors: {len(report['errors'])}")
    print(f"Warnings: {len(report['warnings'])}")
    for error in report["errors"]:
        print(f"ERROR: {error}")
    for warning in report["warnings"]:
        print(f"WARNING: {warning}")
    return 1 if report["hardening_status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
