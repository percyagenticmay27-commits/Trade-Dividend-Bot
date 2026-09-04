#!/usr/bin/env python3
"""Generate weekly discovery artifacts from normalized, collected observations."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise_weekly_market_discovery import write_weekly_discovery


def _merge_fresh_shared_evidence(observations: list[dict], previous: list[dict]) -> None:
    """Refresh retained candidates without treating research-only evidence as a nomination."""
    fresh_financial_health = {
        str(row.get("underlying_symbol") or "").strip().upper(): row.get("financial_health")
        for row in observations
        if isinstance(row, dict) and isinstance(row.get("financial_health"), dict)
    }
    if not fresh_financial_health:
        return
    for row in previous:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("underlying_symbol") or "").strip().upper()
        block = fresh_financial_health.get(symbol)
        if isinstance(block, dict):
            row["financial_health"] = block


def main() -> int:
    root = ROOT
    input_path = root / "inputs" / "enterprise_weekly_market_observations.json"
    previous_path = root / "results" / "enterprise_weekly_market_discovery.json"
    if not input_path.is_file():
        raise SystemExit(
            "No normalized weekly observations are available; refusing to fabricate discovery candidates: "
            f"{input_path}"
        )
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    observations = payload.get("observations", []) if isinstance(payload, dict) else []
    previous = []
    if previous_path.is_file():
        prior_payload = json.loads(previous_path.read_text(encoding="utf-8"))
        previous = prior_payload.get("candidates", []) if isinstance(prior_payload, dict) else []
    _merge_fresh_shared_evidence(observations, previous)
    report = write_weekly_discovery(
        root,
        observations,
        previous,
        generated_at=datetime.now(timezone.utc),
    )
    print(f"Enterprise weekly discovery: {len(report['candidates'])} candidate(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
