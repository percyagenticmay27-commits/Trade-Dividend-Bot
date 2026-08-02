"""Run the isolated Phase 7.2 Enterprise backup recovery drill."""
from __future__ import annotations

import argparse
from typing import Sequence

from src.dividend_bot.enterprise_backup_recovery_validation import (
    run_backup_recovery_drill,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an isolated, non-destructive Enterprise recovery drill"
    )
    parser.add_argument("--root-dir", default=".")
    parser.add_argument("--results-dir", default="results")
    args = parser.parse_args(argv)
    report = run_backup_recovery_drill(
        root_dir=args.root_dir, results_dir=args.results_dir
    )
    print(f"Recovery status: {report['recovery_status']}")
    print(f"Restore test: {report['restore_test_status']}")
    print(f"Critical files: {report['critical_file_count']}")
    print(f"Restored files: {report['restored_file_count']}")
    print(f"Source unchanged: {report['source_files_unchanged']}")
    for error in report["errors"]:
        print(f"ERROR: {error}")
    return 0 if report["recovery_status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
