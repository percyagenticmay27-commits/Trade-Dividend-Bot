#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise_dividend_manual_review_queue import write_manual_review_queue


def main() -> int:
    report = write_manual_review_queue(
        ROOT / "results" / "enterprise_dividend_suitability.json",
        ROOT / "results" / "enterprise_dividend_manual_review_queue.json",
    )
    print(
        f"Dividend manual review queue: {report['queue_count']} pending; "
        f"{report['excluded_count']} excluded"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
