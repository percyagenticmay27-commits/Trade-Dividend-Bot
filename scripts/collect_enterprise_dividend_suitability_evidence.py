from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise_dividend_suitability_evidence import collect_suitability_evidence
from market_data_provider import MarketDataService


def _monitoring_report(active_mapping: dict, reviewed_catalog: dict) -> dict:
    """Build the evidence-monitoring universe without changing Watchlist admission.

    Current Discovery mappings remain present, while reviewed INCOME_ETF mappings
    are also refreshed even when their underlying is absent from this Discovery run.
    Catalog membership is monitoring authorization only; it never activates or
    admits a candidate to the Dividend Watchlist.
    """
    candidates = [dict(row) for row in active_mapping.get("candidates", []) if isinstance(row, dict)]
    seen = {
        str(row.get("income_symbol") or "").strip().upper()
        for row in candidates
        if row.get("income_symbol")
    }
    monitored_income_vehicles = []
    for raw in reviewed_catalog.get("mappings", []):
        if not isinstance(raw, dict):
            continue
        if raw.get("reviewed") is not True or str(raw.get("status") or "").upper() != "REVIEWED":
            continue
        if str(raw.get("mapping_type") or "").upper() != "INCOME_ETF":
            continue
        symbol = str(raw.get("income_symbol") or "").strip().upper()
        if not symbol:
            continue
        monitored_income_vehicles.append(symbol)
        if symbol not in seen:
            candidates.append(dict(raw))
            seen.add(symbol)
    return {
        **active_mapping,
        "candidates": candidates,
        "monitoring_only_income_vehicles": sorted(set(monitored_income_vehicles)),
    }


def main() -> int:
    mapping = json.loads((ROOT / "results/enterprise_dividend_income_mapping.json").read_text(encoding="utf-8"))
    reviewed_catalog = json.loads((ROOT / "configs/dividend_discovery_income_mappings.json").read_text(encoding="utf-8"))
    profiles = json.loads((ROOT / "configs/dividend_suitability_profiles.json").read_text(encoding="utf-8"))
    monitoring = _monitoring_report(mapping, reviewed_catalog)
    report = collect_suitability_evidence(monitoring, profiles, MarketDataService(root_path=str(ROOT)))
    report["monitoring_only_income_vehicles"] = monitoring["monitoring_only_income_vehicles"]
    report["monitoring_policy"] = "REVIEWED_INCOME_ETFS_CONTINUE_REFRESH_OUTSIDE_CURRENT_DISCOVERY"
    report["automatic_activation_allowed"] = False
    output = ROOT / "inputs" / "dividend_suitability_evidence.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Dividend suitability evidence: {len(report['vehicles'])} vehicle(s); "
        f"{len(report['warnings'])} warning(s); "
        f"{len(report['monitoring_only_income_vehicles'])} reviewed income ETF(s) monitored"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
