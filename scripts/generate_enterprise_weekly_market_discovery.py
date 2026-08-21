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
from src.dividend_bot.discovery_leadership_snapshot import (
    enrich_swing_discovery_bucket_from_snapshot,
)


def _load_json_mapping(path: Path) -> dict:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    root = ROOT
    input_path = root / "inputs" / "enterprise_weekly_market_observations.json"
    previous_path = root / "results" / "enterprise_weekly_market_discovery.json"
    swing_bucket_path = root / "results" / "enterprise_swing_discovery_bucket.json"
    market_snapshot_path = root / "market_data_snapshot.json"
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

    # Discovery Leadership consumes the AI CIO-owned, read-only market snapshot.
    # It does not read Swing Bot data and does not perform a network fetch here.
    swing_bucket = _load_json_mapping(swing_bucket_path)
    market_snapshot = _load_json_mapping(market_snapshot_path)
    if market_snapshot:
        enriched_bucket = enrich_swing_discovery_bucket_from_snapshot(
            swing_bucket,
            report,
            observations,
            market_snapshot,
        )
        swing_bucket_path.write_text(
            json.dumps(enriched_bucket, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        print(
            "Discovery Leadership: market_data_snapshot.json missing; "
            "base SWING-001 bucket preserved without fabricated leadership evidence"
        )

    print(f"Enterprise weekly discovery: {len(report['candidates'])} candidate(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
