#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise_discovery_source_collector import collect_credential_free_observations, load_json_if_present
from enterprise_discovery_market_evidence import attach_candidate_market_evidence
from market_data_provider import MarketDataService


def main() -> int:
    root = ROOT
    config_path = root / "configs" / "enterprise_discovery_sources.json"
    if not config_path.is_file():
        raise SystemExit(f"Discovery source configuration is unavailable: {config_path}")
    user_agent = os.environ.get("AI_CIO_DISCOVERY_USER_AGENT", "").strip()
    if not user_agent:
        raise SystemExit("AI_CIO_DISCOVERY_USER_AGENT is required (application name and operator contact; it is not a secret)")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    sources = config.get("sources", []) if isinstance(config, dict) else []
    market = load_json_if_present(root / "market_data_snapshot.json") or load_json_if_present(root / "results/market_data_snapshot.json")
    report = collect_credential_free_observations(
        sources,
        as_of=datetime.now(timezone.utc),
        user_agent=user_agent,
        youtube_api_key=os.environ.get("YOUTUBE_API_KEY", "").strip(),
        market_snapshot=market,
    )
    report = attach_candidate_market_evidence(report, MarketDataService(root_path=str(root)))
    output = root / "inputs" / "enterprise_weekly_market_observations.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Enterprise discovery: {len(report['observations'])} observation(s); {len(report['warnings'])} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
