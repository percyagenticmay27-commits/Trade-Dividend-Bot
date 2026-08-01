"""Publish Phase 3 intelligence into existing Enterprise dashboard artifacts."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.dividend_bot.enterprise_dashboard_intelligence_publisher import (
    build_dashboard_intelligence_publication,
)

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True

DEFAULT_RESULTS_DIR = Path("results")
EXECUTIVE_JSON = "ai_cio_executive_dashboard.json"
INVESTOR_JSON = "enterprise_investor_dashboard.json"
STRATEGY_KPIS_JSON = "enterprise_strategy_kpis.json"
INTELLIGENCE_JSON = "enterprise_dashboard_intelligence.json"
INTERPRETATION_JSON = "enterprise_ai_cio_strategy_interpretation.json"
COMPARISON_JSON = "enterprise_strategy_comparison.json"
CONTRIBUTORS_JSON = "enterprise_contributor_details.json"


def _read_mapping(path: Path, *, required: bool = True) -> dict[str, Any]:
    if not path.is_file():
        if required:
            raise FileNotFoundError(f"Required publication input not found: {path}")
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Publication input root must be an object: {path}")
    return value


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            json.dump(dict(payload), handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return path


def publish_enterprise_dashboard_intelligence(
    *, results_dir: str | Path = DEFAULT_RESULTS_DIR
) -> dict[str, Any]:
    """Attach and publish Phase 3 intelligence using current dashboard outputs."""
    directory = Path(results_dir)
    executive = _read_mapping(directory / EXECUTIVE_JSON)
    investor = _read_mapping(directory / INVESTOR_JSON)
    kpi_document = _read_mapping(directory / STRATEGY_KPIS_JSON)

    discovery = kpi_document.get("strategy_discovery")
    if not isinstance(discovery, Mapping):
        discovery = executive.get("strategy_discovery")
    if not isinstance(discovery, Mapping):
        discovery = investor.get("strategy_discovery")
    if not isinstance(discovery, Mapping):
        discovery = {}

    raw_kpis = kpi_document.get("strategies")
    strategy_kpis = (
        [dict(item) for item in raw_kpis if isinstance(item, Mapping)]
        if isinstance(raw_kpis, list)
        else []
    )

    payloads, warnings = build_dashboard_intelligence_publication(
        strategy_discovery=discovery,
        strategy_kpis=strategy_kpis,
        executive_dashboard=executive,
        investor_dashboard=investor,
    )

    paths = {
        "executive_dashboard": _atomic_write_json(
            directory / EXECUTIVE_JSON, payloads["executive_dashboard"]
        ),
        "investor_dashboard": _atomic_write_json(
            directory / INVESTOR_JSON, payloads["investor_dashboard"]
        ),
        "enterprise_dashboard_intelligence": _atomic_write_json(
            directory / INTELLIGENCE_JSON,
            payloads["enterprise_dashboard_intelligence"],
        ),
        "ai_cio_strategy_interpretation": _atomic_write_json(
            directory / INTERPRETATION_JSON,
            payloads["ai_cio_strategy_interpretation"],
        ),
        "enterprise_strategy_comparison": _atomic_write_json(
            directory / COMPARISON_JSON,
            payloads["enterprise_strategy_comparison"],
        ),
        "enterprise_contributor_details": _atomic_write_json(
            directory / CONTRIBUTORS_JSON,
            payloads["enterprise_contributor_details"],
        ),
    }

    return {
        "published": True,
        "registered_strategy_count": payloads[
            "enterprise_dashboard_intelligence"
        ].get("registered_strategy_count", 0),
        "strategy_ids": payloads["enterprise_dashboard_intelligence"].get(
            "strategy_ids", []
        ),
        "paths": {key: str(value) for key, value in paths.items()},
        "warnings": warnings,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "read_only": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Publish read-only Phase 3 Enterprise dashboard intelligence"
    )
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    args = parser.parse_args(argv)
    try:
        summary = publish_enterprise_dashboard_intelligence(
            results_dir=args.results_dir
        )
    except Exception as exc:
        print(f"Enterprise intelligence publication failed: {exc}")
        return 1

    print(f"Registered strategies: {summary['registered_strategy_count']}")
    print("Strategy IDs: " + ", ".join(summary["strategy_ids"]))
    for name, path in summary["paths"].items():
        print(f"{name}: {path}")
    for warning in summary["warnings"]:
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
