#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    path = root / "inputs" / "enterprise_weekly_market_observations.json"
    if not path.is_file():
        raise SystemExit(f"Discovery observations are unavailable: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    rows = report.get("observations", [])
    forms = Counter(
        evidence.get("form", "NOT_REPORTED")
        for row in rows
        for evidence in row.get("source_evidence", [])
    )
    print("File:", path)
    print("Generated:", report.get("generated_at"))
    print("Observations:", len(rows))
    print("Warnings:", len(report.get("warnings", [])))
    print("Forms:", dict(forms))
    print("Nomination eligible:", sum(row.get("nomination_eligible") is True for row in rows))
    print("Evidence only:", sum(row.get("nomination_eligible") is False for row in rows))
    print("First 20 symbols:", [row.get("underlying_symbol") for row in rows[:20]])
    for warning in report.get("warnings", []):
        print("WARNING:", warning)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
