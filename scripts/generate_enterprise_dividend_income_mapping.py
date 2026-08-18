#!/usr/bin/env python3
"""Generate the advisory Dividend discovery income-mapping report."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise_dividend_income_mapping import write_income_mapping_report


def main() -> int:
    report = write_income_mapping_report(
        ROOT / "results" / "enterprise_dividend_discovery_bucket.json",
        ROOT / "configs" / "dividend_discovery_income_mappings.json",
        ROOT / "results" / "enterprise_dividend_income_mapping.json",
    )
    print(
        "Dividend income mapping: "
        f"{report['reviewed_mapping_count']} reviewed; "
        f"{report['research_required_count']} research required"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
