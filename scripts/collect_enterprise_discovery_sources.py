#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise_discovery_catalyst_extractor import enrich_observations_with_catalyst_events
from enterprise_discovery_catalyst_evidence import attach_candidate_catalyst_classification
from enterprise_discovery_financial_health import attach_candidate_financial_health
from enterprise_discovery_issuer_evidence import collect_issuer_primary_evidence, attach_issuer_primary_evidence
from enterprise_discovery_issuer_research import build_issuer_research_registry, attach_issuer_research_registry
from enterprise_discovery_source_collector import collect_credential_free_observations, load_json_if_present
from enterprise_discovery_market_evidence import attach_candidate_market_evidence
from enterprise_discovery_official_macro_sources import collect_official_macro_evidence, attach_official_macro_evidence
from enterprise_discovery_sec_catalyst_events import enrich_report_with_sec_reviewed_events
from enterprise_discovery_sec_event_review_candidates import enrich_report_with_sec_event_review_candidates
from enterprise_discovery_targeted_sec_enrichment import enrich_active_candidates_with_sec_submissions
from enterprise_discovery_theme_strength import attach_candidate_theme_strength
from market_data_provider import MarketDataService

APPROVED_THEME_CONTEXT = {
    "AI INFRASTRUCTURE",
    "DATA CENTERS",
    "SEMICONDUCTORS",
    "NUCLEAR POWER",
    "ENERGY STORAGE",
    "ROBOTICS",
    "QUANTUM COMPUTING",
    "CYBERSECURITY",
    "BITCOIN MINING",
    "CLOUD COMPUTING",
    "DEFENSE TECH",
    "CLEAN ENERGY",
    "HYDROGEN",
    "ELECTRIC VEHICLES",
}


def _active_candidates(root: Path) -> dict[str, dict]:
    """Return retained active candidate context keyed by underlying symbol."""
    payload = load_json_if_present(root / "results" / "enterprise_weekly_market_discovery.json") or {}
    rows = payload.get("candidates", []) if isinstance(payload, dict) else []
    result: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("underlying_symbol") or "").strip().upper()
        if symbol:
            result[symbol] = row
    return result


def _active_candidate_symbols(root: Path) -> set[str]:
    """Backward-compatible symbol-only view of retained active candidates."""
    return set(_active_candidates(root))


def _hydrate_retained_theme_context(
    report: dict,
    active_candidates: Mapping[str, Mapping[str, object]],
) -> dict:
    """Carry authoritative theme context into same-symbol research refreshes.

    Prefer the retained active-candidate theme label. If legacy retention has already
    lost that label, allow only an exact match between the current authoritative
    market industry classification and Swing's approved theme vocabulary. This is
    evidence-backed classification reuse, not a new inferred theme or nomination.
    """
    for row in report.get("observations", []):
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("underlying_symbol") or "").strip().upper()
        retained = active_candidates.get(symbol)
        if not isinstance(retained, Mapping):
            continue
        current_themes = [str(value).strip() for value in row.get("themes", []) if str(value).strip()]
        if current_themes:
            continue
        retained_themes = [str(value).strip() for value in retained.get("themes", []) if str(value).strip()]
        if retained_themes:
            row["themes"] = retained_themes
            continue
        market = row.get("market_evidence")
        if not isinstance(market, Mapping):
            continue
        industry = str(market.get("industry") or "").strip()
        if industry and industry.upper() in APPROVED_THEME_CONTEXT:
            row["themes"] = [industry]
    return report


def _refresh_financial_health_for_active_candidates(
    report: dict,
    service: MarketDataService,
    active_symbols: set[str],
) -> dict:
    """Backward-compatible Financial Health-only retained-candidate refresh helper."""
    original_states: list[tuple[dict, object]] = []
    for row in report.get("observations", []):
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("underlying_symbol") or "").strip().upper()
        if symbol in active_symbols and row.get("nomination_eligible") is False:
            original_states.append((row, row.get("nomination_eligible")))
            row["nomination_eligible"] = True
    try:
        return attach_candidate_financial_health(report, service)
    finally:
        for row, original in original_states:
            row["nomination_eligible"] = original


def _refresh_shared_evidence_for_active_candidates(
    report: dict,
    service: MarketDataService,
    active_symbols: set[str],
    *,
    generated_at: datetime,
    active_candidates: Mapping[str, Mapping[str, object]] | None = None,
) -> dict:
    """Refresh retained candidates without converting research evidence into a nomination."""
    if active_candidates:
        report = _hydrate_retained_theme_context(report, active_candidates)

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
        if active_candidates:
            report = _hydrate_retained_theme_context(report, active_candidates)
        report = attach_candidate_financial_health(report, service)
    finally:
        for row, original in original_states:
            row["nomination_eligible"] = original

    # SEC item codes first become non-scoring REVIEW_REQUIRED research candidates.
    # They still cannot create reviewed/scored events. Only explicit reviewed SEC
    # event metadata can cross the existing producer/extractor/classifier boundary.
    report = enrich_report_with_sec_event_review_candidates(report)
    report = enrich_report_with_sec_reviewed_events(report)
    report = enrich_observations_with_catalyst_events(report)
    report = attach_candidate_catalyst_classification(report)
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

    # Tier-1 official macro/regulatory feeds are collected separately at report level.
    # They are deliberately non-scoring and have no symbol linkage here. A later
    # governed layer must establish explicit relevance before they can affect a symbol.
    official_config = load_json_if_present(root / "configs" / "enterprise_discovery_official_macro_sources.json") or {}
    official_sources = official_config.get("sources", []) if isinstance(official_config, dict) else []
    if official_sources:
        macro_report = collect_official_macro_evidence(
            official_sources,
            as_of=generated_at,
            user_agent=user_agent,
        )
        report = attach_official_macro_evidence(report, macro_report)

    service = MarketDataService(root_path=str(root))
    active_candidates = _active_candidates(root)

    # Verified issuer profiles and their first-party research pages are report-level
    # primary evidence only. Collection proves reachability and explicit symbol linkage;
    # it cannot create a catalyst, nomination, Theme Strength point, or favorable stance.
    issuer_config = load_json_if_present(root / "configs" / "enterprise_discovery_issuer_research_profiles.json") or {}
    issuer_profiles = issuer_config.get("profiles", []) if isinstance(issuer_config, dict) else []
    if issuer_profiles:
        issuer_registry = build_issuer_research_registry(issuer_profiles)
        report = attach_issuer_research_registry(report, issuer_registry)
        issuer_report = collect_issuer_primary_evidence(
            issuer_registry.get("profiles", {}).values(),
            active_symbols=set(active_candidates),
            as_of=generated_at,
            user_agent=user_agent,
        )
        report = attach_issuer_primary_evidence(report, issuer_report)

    # The daily SEC index remains broad discovery. Detailed submissions metadata is
    # fetched only for retained active candidates already present in this collection.
    # This can add structured item codes, but it cannot infer or emit catalyst events.
    report = enrich_active_candidates_with_sec_submissions(
        report,
        set(active_candidates),
        as_of=generated_at,
        user_agent=user_agent,
    )

    report = _refresh_shared_evidence_for_active_candidates(
        report,
        service,
        set(active_candidates),
        generated_at=generated_at,
        active_candidates=active_candidates,
    )
    output = root / "inputs" / "enterprise_weekly_market_observations.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Enterprise discovery: {len(report['observations'])} observation(s); {len(report['warnings'])} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
