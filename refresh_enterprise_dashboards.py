"""Refresh read-only Enterprise dashboard artifacts for the AI CIO portal."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.dividend_bot.enterprise_dashboard_evidence_adapter import build_dashboard_evidence
from src.dividend_bot.enterprise_executive_dashboard import build_executive_dashboard, render_executive_dashboard_markdown
from src.dividend_bot.enterprise_investor_dashboard_integration import build_enterprise_investor_dashboard, render_enterprise_investor_dashboard_markdown

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True

DEFAULT_RESULTS_DIR = Path("results")
DEFAULT_EXECUTIVE_JSON = "ai_cio_executive_dashboard.json"
DEFAULT_EXECUTIVE_MARKDOWN = "ai_cio_executive_dashboard.md"
DEFAULT_INVESTOR_JSON = "enterprise_investor_dashboard.json"
DEFAULT_INVESTOR_MARKDOWN = "enterprise_investor_dashboard.md"


def _atomic_write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return path


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    return _atomic_write_text(path, json.dumps(dict(payload), indent=2, sort_keys=True) + "\n")


def refresh_enterprise_dashboards(*, results_dir: str | Path = DEFAULT_RESULTS_DIR, root_dir: str | Path = ".", state_dir: str | Path = "state", investor_source_candidates: Sequence[str | Path] = ()) -> dict[str, Any]:
    """Publish dashboard artifacts from existing host evidence only."""
    directory = Path(results_dir)
    directory.mkdir(parents=True, exist_ok=True)

    evidence = build_dashboard_evidence(root_dir=root_dir, results_dir=directory, state_dir=state_dir)
    _atomic_write_json(directory / "strategy_inventory.json", evidence["strategy_inventory"])
    _atomic_write_json(directory / "enterprise_health.json", evidence["enterprise_health"])

    executive = build_executive_dashboard(input_dir=directory)
    executive_json = _atomic_write_json(directory / DEFAULT_EXECUTIVE_JSON, executive)
    executive_markdown = _atomic_write_text(directory / DEFAULT_EXECUTIVE_MARKDOWN, render_executive_dashboard_markdown(executive))

    investor_evidence = evidence["investor_evidence"]
    investor = build_enterprise_investor_dashboard(
        portfolio_summary=investor_evidence.get("portfolio_summary"),
        holdings=investor_evidence.get("holdings"),
        payment_history=investor_evidence.get("payment_history"),
        upcoming_payments=investor_evidence.get("upcoming_payments"),
        review_flags=investor_evidence.get("review_flags"),
    )
    investor_json = _atomic_write_json(directory / DEFAULT_INVESTOR_JSON, investor)
    investor_markdown = _atomic_write_text(directory / DEFAULT_INVESTOR_MARKDOWN, render_enterprise_investor_dashboard_markdown(investor))

    warnings = list(evidence.get("warnings", []))
    warnings.extend(str(item) for item in executive.get("warnings", []) if item)
    warnings.extend(str(item) for item in investor.get("warnings", []) if item)
    errors = [str(item) for item in executive.get("errors", []) if item]
    return {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "executive_dashboard_status": executive.get("enterprise_summary", {}).get("enterprise_status", "UNKNOWN"),
        "investor_dashboard_status": investor.get("dashboard_status", "UNKNOWN"),
        "investor_source": "enterprise_dashboard_evidence_adapter",
        "registered_strategy_count": executive.get("enterprise_summary", {}).get("registered_strategy_count", 0),
        "paths": {
            "strategy_inventory": str(directory / "strategy_inventory.json"),
            "enterprise_health": str(directory / "enterprise_health.json"),
            "executive_json": str(executive_json),
            "executive_markdown": str(executive_markdown),
            "investor_json": str(investor_json),
            "investor_markdown": str(investor_markdown),
        },
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh read-only AI CIO portal dashboards")
    parser.add_argument("--root-dir", default=".")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--state-dir", default="state")
    args = parser.parse_args(argv)
    try:
        summary = refresh_enterprise_dashboards(root_dir=args.root_dir, results_dir=args.results_dir, state_dir=args.state_dir)
    except Exception as exc:
        print(f"Dashboard refresh failed: {exc}")
        return 1
    print(f"Executive dashboard: {summary['paths']['executive_json']}")
    print(f"Investor dashboard: {summary['paths']['investor_json']}")
    print(f"Registered strategies: {summary['registered_strategy_count']}")
    print(f"Executive status: {summary['executive_dashboard_status']}")
    print(f"Investor status: {summary['investor_dashboard_status']}")
    for warning in summary["warnings"]:
        print(f"WARNING: {warning}")
    for error in summary["errors"]:
        print(f"ERROR: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
