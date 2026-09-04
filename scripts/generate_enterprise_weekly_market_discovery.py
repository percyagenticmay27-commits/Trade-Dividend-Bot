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
    """Refresh retained candidate context without reconfirming a research-only nomination."""
    fresh_rows = {
        str(row.get("underlying_symbol") or "").strip().upper(): row
        for row in observations
        if isinstance(row, dict) and str(row.get("underlying_symbol") or "").strip()
    }
    for row in previous:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("underlying_symbol") or "").strip().upper()
        fresh = fresh_rows.get(symbol)
        if not isinstance(fresh, dict):
            continue
        for key in ("financial_health", "theme_strength", "market_evidence"):
            block = fresh.get(key)
            if isinstance(block, dict):
                row[key] = block
        fresh_themes = [str(value).strip() for value in fresh.get("themes", []) if str(value).strip()]
        if fresh_themes:
            row["themes"] = fresh_themes
        fresh_evidence = fresh.get("source_evidence") or fresh.get("evidence_sources")
        if isinstance(fresh_evidence, list) and fresh_evidence:
            row["source_evidence"] = list(fresh_evidence)
        # Deliberately do not copy nomination_eligible or discovery_status. A research-only
        # observation may refresh evidence for an already-retained candidate, but it may not
        # reconfirm the nomination or alter the retained lifecycle state.


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
