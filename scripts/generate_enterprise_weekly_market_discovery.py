#!/usr/bin/env python3
"""Generate weekly discovery artifacts from normalized, collected observations."""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise_discovery_catalyst_evidence import attach_candidate_catalyst_classification
from enterprise_discovery_theme_strength import build_theme_strength_block
from enterprise_weekly_market_discovery import _evidence_analysis, _normalize_evidence, write_weekly_discovery

HISTORY_EVIDENCE_LOOKBACK_DAYS = 14


def _recent_history_evidence(
    history_path: Path,
    active_symbols: set[str],
    *,
    generated_at: datetime,
    lookback_days: int = HISTORY_EVIDENCE_LOOKBACK_DAYS,
) -> dict[str, list[dict]]:
    """Recover still-current evidence from the append-only discovery audit history.

    History is recovery evidence only: it may restore source records that disappeared from a
    retained snapshot, but it never restores nomination eligibility or lifecycle state.
    Evidence is bounded by its own mentioned/published date so old stories cannot be revived
    merely because a newer history snapshot happened to contain them.
    """
    recovered: dict[str, list[dict]] = {symbol: [] for symbol in active_symbols}
    if not history_path.is_file() or not active_symbols:
        return recovered
    cutoff = generated_at.astimezone(timezone.utc).date() - timedelta(days=lookback_days)
    for raw_line in history_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            snapshot = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(snapshot, dict):
            continue
        symbol = str(snapshot.get("underlying_symbol") or "").strip().upper()
        if symbol not in active_symbols:
            continue
        evidence = snapshot.get("source_evidence") or snapshot.get("evidence_sources") or []
        if not isinstance(evidence, list):
            continue
        for item in evidence:
            if not isinstance(item, dict):
                continue
            raw_date = str(item.get("mentioned_on") or item.get("published_at") or "")[:10]
            try:
                mentioned = date.fromisoformat(raw_date)
            except ValueError:
                continue
            if cutoff <= mentioned <= generated_at.date():
                recovered[symbol].append(item)
    return {symbol: _normalize_evidence(items) for symbol, items in recovered.items() if items}


def _merge_fresh_shared_evidence(
    observations: list[dict],
    previous: list[dict],
    *,
    generated_at: datetime | None = None,
    history_evidence: dict[str, list[dict]] | None = None,
) -> None:
    """Refresh retained candidate context without reconfirming a research-only nomination."""
    fresh_rows = {
        str(row.get("underlying_symbol") or "").strip().upper(): row
        for row in observations
        if isinstance(row, dict) and str(row.get("underlying_symbol") or "").strip()
    }
    stamp = generated_at or datetime.now(timezone.utc)
    history_evidence = history_evidence or {}
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
        recovered_evidence = history_evidence.get(symbol, [])
        merged_evidence = _normalize_evidence([*recovered_evidence, *retained_evidence, *fresh_evidence])
        if merged_evidence:
            row["source_evidence"] = merged_evidence
            analysis = _evidence_analysis(merged_evidence)
            row["independent_source_count"] = analysis["independent_source_count"]
            row["source_confluence"] = analysis
            row["evidence_stance_summary"] = analysis["stance_summary"]

        # Recovered history must pass the same governed catalyst classifier as fresh
        # observations before Theme Strength can consume any explicit catalyst claim.
        classifier_report = {"observations": [row], "warnings": []}
        attach_candidate_catalyst_classification(classifier_report)
        if classifier_report.get("warnings"):
            existing = row.setdefault("evidence_warnings", [])
            if isinstance(existing, list):
                existing.extend(classifier_report["warnings"])
                row["evidence_warnings"] = list(dict.fromkeys(str(value) for value in existing))

        row.pop("theme_strength", None)
        theme_strength = build_theme_strength_block(row, generated_at=stamp)
        if isinstance(theme_strength, dict):
            row["theme_strength"] = theme_strength

        # Deliberately do not copy nomination_eligible or discovery_status. Research and
        # audit evidence may refresh a retained candidate, but neither can promote it.


def main() -> int:
    root = ROOT
    input_path = root / "inputs" / "enterprise_weekly_market_observations.json"
    previous_path = root / "results" / "enterprise_weekly_market_discovery.json"
    history_path = root / "state" / "enterprise_market_discovery_history.jsonl"
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
    active_symbols = {
        str(row.get("underlying_symbol") or "").strip().upper()
        for row in previous
        if isinstance(row, dict) and str(row.get("underlying_symbol") or "").strip()
    }
    history_evidence = _recent_history_evidence(
        history_path,
        active_symbols,
        generated_at=generated_at,
    )
    _merge_fresh_shared_evidence(
        observations,
        previous,
        generated_at=generated_at,
        history_evidence=history_evidence,
    )
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
