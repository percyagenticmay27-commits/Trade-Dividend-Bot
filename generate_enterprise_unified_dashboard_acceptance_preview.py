"""Generate the Phase 6.4 operator acceptance evidence page."""
from __future__ import annotations

import argparse
from typing import Sequence

from src.dividend_bot.enterprise_unified_dashboard_acceptance_renderer import (
    generate_acceptance_evidence_preview,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a read-only unified dashboard acceptance HTML report"
    )
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)
    try:
        result = generate_acceptance_evidence_preview(
            results_dir=args.results_dir,
            output_path=args.output,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Acceptance evidence preview failed: {exc}")
        return 1
    print(f"Acceptance evidence preview: {result['path']}")
    print(f"Verification status: {result['verification_status']}")
    print("Safety: PAPER ONLY / READ ONLY")
    return 0 if result["verification_status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
