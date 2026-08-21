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
from src.dividend_bot.discovery_leadership import enrich_swing_discovery_bucket


def main() -> int:
    root = ROOT
    input_path = root / "inputs" / "enterprise_weekly_market_observations.json"
    previous_path = root / "results" / "enterprise_weekly_market_discovery.json"
    swing_bucket_path = root / "results" / "enterprise_swing_discovery_bucket.json"
    history_dir = root / "historical_data" / "daily"
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
    report = write_weekly_discovery(
        root,
        observations,
        previous,
        generated_at=datetime.now(timezone.utc),
    )

    # Leadership is additive discovery evidence only. The base producer preserves
    # the established SWING-001 schema; this pass enriches that artifact using
    # existing local authoritative history and never performs a network fetch.
    swing_bucket = json.loads(swing_bucket_path.read_text(encoding="utf-8"))
    enriched_bucket = enrich_swing_discovery_bucket(
        swing_bucket,
        report,
        observations,
        history_dir=history_dir,
    )
    swing_bucket_path.write_text(
        json.dumps(enriched_bucket, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Enterprise weekly discovery: {len(report['candidates'])} candidate(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
