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

from enterprise_discovery_financial_health import attach_candidate_financial_health
from enterprise_discovery_source_collector import collect_credential_free_observations, load_json_if_present
from enterprise_discovery_market_evidence import attach_candidate_market_evidence
from enterprise_discovery_theme_strength import attach_candidate_theme_strength
from market_data_provider import MarketDataService


def _active_candidate_symbols(root: Path) -> set[str]:
    payload = load_json_if_present(root / "results" / "enterprise_weekly_market_discovery.json") or {}
    rows = payload.get("candidates", []) if isinstance(payload, dict) else []
    return {
        str(row.get("underlying_symbol") or "").strip().upper()
        for row in rows
        if isinstance(row, dict) and str(row.get("underlying_symbol") or "").strip()
    }


def _refresh_shared_evidence_for_active_candidates(
    report: dict,
    service: MarketDataService,
    active_symbols: set[str],
    *,
    generated_at: datetime,
) -> dict:
    """Refresh retained candidates without converting research evidence into a nomination."""
    original_states: list[tuple[dict, object]] = []
    for row in report.get("observations", []):
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("underlying_symbol") or "").strip().upper()
        if symbol in active_symbols and row.get("nomination_eligible") is False:
            original_states.append((row, row.get("nomination_eligible")))
            row["nomination_eligible"] = True
    try:
        report = attach_candidate_market_evidence(report, service)
        report = attach_candidate_financial_health(report, service)
    finally:
        for row, original in original_states:
            row["nomination_eligible"] = original
    return attach_candidate_theme_strength(report, generated_at=generated_at)


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
    generated_at = datetime.now(timezone.utc)
    report = collect_credential_free_observations(
        sources,
        as_of=generated_at,
        user_agent=user_agent,
        youtube_api_key=os.environ.get("YOUTUBE_API_KEY", "").strip(),
        alpha_vantage_api_key=os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip(),
        market_snapshot=market,
    )
    service = MarketDataService(root_path=str(root))
    report = _refresh_shared_evidence_for_active_candidates(
        report,
        service,
        _active_candidate_symbols(root),
        generated_at=generated_at,
    )
    output = root / "inputs" / "enterprise_weekly_market_observations.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Enterprise discovery: {len(report['observations'])} observation(s); {len(report['warnings'])} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
