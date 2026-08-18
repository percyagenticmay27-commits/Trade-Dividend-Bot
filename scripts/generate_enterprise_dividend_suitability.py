from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise_dividend_suitability import write_suitability_report


def main() -> int:
    report = write_suitability_report(
        ROOT / "results" / "enterprise_dividend_income_mapping.json",
        ROOT / "configs" / "dividend_suitability_evidence.json",
        ROOT / "results" / "enterprise_dividend_suitability.json",
    )
    print(
        "Dividend suitability: "
        f"{report['eligible_for_paper_review_count']} eligible; "
        f"{report['watch_only_count']} watch only; "
        f"{report['rejected_count']} rejected; "
        f"{report['evidence_required_count']} evidence required"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
