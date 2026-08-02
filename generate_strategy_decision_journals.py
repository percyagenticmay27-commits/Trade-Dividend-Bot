"""Generate current strategy Decision Journal JSON artifacts."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from src.dividend_bot.strategy_decision_journal_generator import (
    generate_all_strategy_decision_journals,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate read-only Dividend and Swing Decision Journals"
    )
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--dividend-source", action="append", default=None)
    parser.add_argument("--swing-source", action="append", default=None)
    args = parser.parse_args(argv)

    summary = generate_all_strategy_decision_journals(
        results_dir=Path(args.results_dir),
        dividend_sources=args.dividend_source,
        swing_sources=args.swing_source,
    )
    print(f"Generation complete: {summary['generation_complete']}")
    print(f"Decision count: {summary['decision_count']}")
    for name, path in summary["paths"].items():
        print(f"{name}: {path}")
    for warning in summary["warnings"]:
        print(f"WARNING: {warning}")
    for error in summary["errors"]:
        print(f"ERROR: {error}")
    return 0 if summary["generation_complete"] and not summary["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
