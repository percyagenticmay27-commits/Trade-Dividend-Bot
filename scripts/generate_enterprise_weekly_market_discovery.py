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

from enterprise_discovery_theme_strength import build_theme_strength_block
from enterprise_weekly_market_discovery import _evidence_analysis, _normalize_evidence, write_weekly_discovery


def _merge_fresh_shared_evidence(
    observations: list[dict],
    previous: list[dict],
    *,
    generated_at: datetime | None = None,
) -> None:
    """Refresh retained candidate context without reconfirming a research-only nomination.

    Retained candidates can receive fresh research-only evidence. Merge that evidence with
    the retained evidence set, recompute confluence from the merged set, and then rebuild
    Theme Strength from the same evidence that will actually be published. This prevents
    stale confluence metadata from disagreeing with the published source_evidence list.
    """
    fresh_rows = {
        str(row.get("underlying_symbol") or "").strip().upper(): row
        for row in observations
        if isinstance(row, dict) and str(row.get("underlying_symbol") or "").strip()
    }
    stamp = generated_at or datetime.now(timezone.utc)
    for row in previous:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("underlying_symbol") or "").strip().upper()
        fresh = fresh_rows.get(symbol)
        if not isinstance(fresh, dict):
            continue

        for key in ("financial_health", "market_evidence"):
            block = fresh.get(key)
            if isinstance(block, dict):
                row[key] = block

        retained_themes = [str(value).strip() for value in row.get("themes", []) if str(value).strip()]
        fresh_themes = [str(value).strip() for value in fresh.get("themes", []) if str(value).strip()]
        if retained_themes or fresh_themes:
            row["themes"] = sorted(set(retained_themes + fresh_themes))

        retained_evidence_raw = row.get("source_evidence") or row.get("evidence_sources") or []
        fresh_evidence_raw = fresh.get("source_evidence") or fresh.get("evidence_sources") or []
        retained_evidence = retained_evidence_raw if isinstance(retained_evidence_raw, list) else []
        fresh_evidence = fresh_evidence_raw if isinstance(fresh_evidence_raw, list) else []
        merged_evidence = _normalize_evidence([*retained_evidence, *fresh_evidence])
        if merged_evidence:
            row["source_evidence"] = merged_evidence
            analysis = _evidence_analysis(merged_evidence)
            row["independent_source_count"] = analysis["independent_source_count"]
            row["source_confluence"] = analysis
            row["evidence_stance_summary"] = analysis["stance_summary"]

        # Rebuild Theme Strength from the merged evidence context. Never retain a stale
        # block if the now-published evidence cannot support a complete current score.
        row.pop("theme_strength", None)
        theme_strength = build_theme_strength_block(row, generated_at=stamp)
        if isinstance(theme_strength, dict):
            row["theme_strength"] = theme_strength

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
    generated_at = datetime.now(timezone.utc)
    _merge_fresh_shared_evidence(observations, previous, generated_at=generated_at)
    report = write_weekly_discovery(
        root,
        observations,
        previous,
        generated_at=generated_at,
    )
    print(f"Enterprise weekly discovery: {len(report['candidates'])} candidate(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
