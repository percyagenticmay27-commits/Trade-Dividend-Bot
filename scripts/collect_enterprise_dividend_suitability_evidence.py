from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise_dividend_suitability_evidence import collect_suitability_evidence
from market_data_provider import MarketDataService


def main() -> int:
    mapping = json.loads((ROOT / "results/enterprise_dividend_income_mapping.json").read_text(encoding="utf-8"))
    profiles = json.loads((ROOT / "configs/dividend_suitability_profiles.json").read_text(encoding="utf-8"))
    report = collect_suitability_evidence(mapping, profiles, MarketDataService(root_path=str(ROOT)))
    output = ROOT / "inputs" / "dividend_suitability_evidence.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Dividend suitability evidence: {len(report['vehicles'])} vehicle(s); {len(report['warnings'])} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
