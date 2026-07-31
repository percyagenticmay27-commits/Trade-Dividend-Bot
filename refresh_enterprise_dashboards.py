"""Refresh read-only Enterprise dashboard artifacts for the AI CIO portal.

This launcher consumes existing report artifacts only. It does not discover trades,
allocate capital, approve requests, communicate with a broker, or enable live mode.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.dividend_bot.enterprise_executive_dashboard import (
    build_executive_dashboard,
    render_executive_dashboard_markdown,
)
from src.dividend_bot.enterprise_investor_dashboard_integration import (
    build_enterprise_investor_dashboard,
    render_enterprise_investor_dashboard_markdown,
)

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
DEFAULT_INVESTOR_SOURCE_CANDIDATES = (
    "enterprise_dividend_investor_dashboard.json",
    "dividend_investor_dashboard.json",
    "investor_portfolio_report.json",
)


def _read_mapping(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.is_file():
        return {}, None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, f"invalid dashboard source {path}: {exc}"
    if not isinstance(value, dict):
        return {}, f"invalid dashboard source {path}: root must be an object"
    return value, None


def _atomic_write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
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
    return _atomic_write_text(
        path,
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
    )


def _first_investor_source(
    results_dir: Path,
    candidates: Sequence[str | Path],
) -> tuple[dict[str, Any], Path | None, list[str]]:
    warnings: list[str] = []
    for candidate in candidates:
        path = Path(candidate)
        if not path.is_absolute():
            path = results_dir / path
        payload, warning = _read_mapping(path)
        if warning:
            warnings.append(warning)
            continue
        if payload:
            return payload, path, warnings
    warnings.append("No existing investor dashboard source artifact was available; a PARTIAL reporting artifact was produced with explicit data warnings.")
    return {}, None, warnings


def refresh_enterprise_dashboards(
    *,
    results_dir: str | Path = DEFAULT_RESULTS_DIR,
    investor_source_candidates: Sequence[str | Path] = DEFAULT_INVESTOR_SOURCE_CANDIDATES,
) -> dict[str, Any]:
    """Build and atomically publish portal dashboard artifacts.

    Missing Enterprise inputs produce explicit report errors or warnings but do not
    fabricate portfolio data and do not affect the allocation service state.
    """
    directory = Path(results_dir)
    directory.mkdir(parents=True, exist_ok=True)

    executive = build_executive_dashboard(input_dir=directory)
    executive_json = _atomic_write_json(directory / DEFAULT_EXECUTIVE_JSON, executive)
    executive_markdown = _atomic_write_text(
        directory / DEFAULT_EXECUTIVE_MARKDOWN,
        render_executive_dashboard_markdown(executive),
    )

    investor_source, investor_source_path, launcher_warnings = _first_investor_source(
        directory, investor_source_candidates
    )
    investor = build_enterprise_investor_dashboard(dividend_dashboard=investor_source)
    investor_json = _atomic_write_json(directory / DEFAULT_INVESTOR_JSON, investor)
    investor_markdown = _atomic_write_text(
        directory / DEFAULT_INVESTOR_MARKDOWN,
        render_enterprise_investor_dashboard_markdown(investor),
    )

    warnings = list(launcher_warnings)
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
        "investor_source": str(investor_source_path) if investor_source_path else None,
        "paths": {
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
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    args = parser.parse_args(argv)

    try:
        summary = refresh_enterprise_dashboards(results_dir=args.results_dir)
    except Exception as exc:  # genuine host publication failure
        print(f"Dashboard refresh failed: {exc}")
        return 1

    print(f"Executive dashboard: {summary['paths']['executive_json']}")
    print(f"Investor dashboard: {summary['paths']['investor_json']}")
    print(f"Executive status: {summary['executive_dashboard_status']}")
    print(f"Investor status: {summary['investor_dashboard_status']}")
    print(f"Investor source: {summary['investor_source'] or 'none'}")
    for warning in summary["warnings"]:
        print(f"WARNING: {warning}")
    for error in summary["errors"]:
        print(f"ERROR: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
