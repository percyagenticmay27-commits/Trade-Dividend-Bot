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
from market_data_integration_engine import write_market_data_snapshot
from src.dividend_bot.discovery_leadership_snapshot import (
    enrich_swing_discovery_bucket_from_snapshot,
)
from src.dividend_bot.discovery_source_class_projection import (
    propagate_source_classes_to_swing_bucket,
)

BENCHMARK_SYMBOL = "SPY"


def _load_json_mapping(path: Path) -> dict:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _snapshot_symbols(snapshot: dict) -> set[str]:
    return {
        str(row.get("symbol") or "").strip().upper()
        for row in snapshot.get("records", [])
        if isinstance(row, dict) and str(row.get("symbol") or "").strip()
    }


def _required_leadership_symbols(report: dict) -> list[str]:
    symbols = {BENCHMARK_SYMBOL}
    for row in report.get("candidates", []):
        if not isinstance(row, dict) or row.get("nomination_eligible") is False:
            continue
        symbol = str(row.get("underlying_symbol") or "").strip().upper()
        if symbol:
            symbols.add(symbol)
    return sorted(symbols)


def _ensure_market_snapshot_coverage(root: Path, report: dict) -> dict:
    """Ensure AI CIO owns SPY + current nominee history before leadership scoring.

    The existing MarketDataService remains authoritative. This helper is cache-first,
    read-only market-data access; it never reads Swing Bot files and never touches a
    broker. Missing provider data remains explicit in the resulting partial snapshot.
    """
    snapshot_path = root / "market_data_snapshot.json"
    snapshot = _load_json_mapping(snapshot_path)
    required = _required_leadership_symbols(report)
    missing = sorted(set(required) - _snapshot_symbols(snapshot))
    if not missing:
        return snapshot

    print(
        "Discovery Leadership market coverage: refreshing AI CIO snapshot for "
        + ", ".join(missing)
    )
    refreshed = write_market_data_snapshot(
        root_path=str(root),
        symbols=required,
        force_refresh=False,
    )
    refreshed_symbols = _snapshot_symbols(refreshed)
    still_missing = sorted(set(required) - refreshed_symbols)
    if still_missing:
        print(
            "Discovery Leadership market coverage warning: still missing "
            + ", ".join(still_missing)
        )
    return refreshed


def main() -> int:
    root = ROOT
    input_path = root / "inputs" / "enterprise_weekly_market_observations.json"
    previous_path = root / "results" / "enterprise_weekly_market_discovery.json"
    swing_bucket_path = root / "results" / "enterprise_swing_discovery_bucket.json"
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
    # Ensure SPY plus current nominees are covered by the existing cache-backed
    # MarketDataService before scoring. No Swing Bot data is read.
    swing_bucket = _load_json_mapping(swing_bucket_path)
    market_snapshot = _ensure_market_snapshot_coverage(root, report)
    final_bucket = swing_bucket
    if market_snapshot:
        final_bucket = enrich_swing_discovery_bucket_from_snapshot(
            swing_bucket,
            report,
            observations,
            market_snapshot,
        )
    else:
        print(
            "Discovery Leadership: market_data_snapshot.json missing; "
            "base SWING-001 bucket preserved without fabricated leadership evidence"
        )

    # AI CIO owns source classification.  Propagate its normalized producer
    # authority into the SWING-001 evidence records after any leadership enrichment.
    # This is additive metadata only and never alters Discovery Leadership values.
    final_bucket = propagate_source_classes_to_swing_bucket(final_bucket, report)
    swing_bucket_path.write_text(
        json.dumps(final_bucket, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Enterprise weekly discovery: {len(report['candidates'])} candidate(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
