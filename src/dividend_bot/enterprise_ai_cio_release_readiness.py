"""Enterprise AI CIO V1 release-readiness assessment.

Read-only and paper-only. This module validates the presence and basic contract
shape of Stage 10-17 outputs. It never executes strategies, changes policy,
allocates capital, contacts brokers, or places orders.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

MODULE_NAME = "enterprise_ai_cio_release_readiness"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

REQUIRED_OUTPUTS = (
    "strategy_inventory.json",
    "enterprise_health.json",
    "executive_dashboard.json",
    "ai_cio_portfolio_manager.json",
    "cross_strategy_risk.json",
    "capital_allocation_review.json",
    "strategy_performance_analytics.json",
    "learning_feedback.json",
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON contract: {path}") from exc
    if not isinstance(value, Mapping):
        raise ValueError(f"JSON contract must be an object: {path}")
    return value


def build_release_readiness(results_dir: str | Path, *, generated_at_utc: str | None = None) -> dict[str, Any]:
    root = Path(results_dir)
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []

    for filename in REQUIRED_OUTPUTS:
        path = root / filename
        if not path.exists():
            checks.append({"file": filename, "status": "MISSING"})
            blockers.append(f"missing required output: {filename}")
            continue
        try:
            payload = _load_json(path)
        except ValueError as exc:
            checks.append({"file": filename, "status": "INVALID"})
            blockers.append(str(exc))
            continue
        checks.append({"file": filename, "status": "PRESENT", "keys": sorted(payload.keys())})

    dashboard_path = root / "executive_dashboard.json"
    if dashboard_path.exists():
        try:
            dashboard = _load_json(dashboard_path)
            paper = dashboard.get("paper_safety", {})
            if isinstance(paper, Mapping):
                safe = (
                    paper.get("paper_trade_mode") is True
                    and paper.get("live_trading_enabled") is False
                    and paper.get("broker_execution_enabled") is False
                )
                if not safe:
                    blockers.append("executive dashboard paper-safety contract is unsafe")
            status = str((dashboard.get("enterprise_summary") or {}).get("enterprise_status") or "UNKNOWN").upper()
            if status in {"UNSAFE", "CRITICAL"}:
                blockers.append(f"enterprise status blocks release: {status}")
            elif status not in {"HEALTHY", "WARNING", "DEGRADED", "UNKNOWN"}:
                warnings.append(f"unrecognized enterprise status: {status}")
        except ValueError:
            pass

    ready = not blockers
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at_utc or _now_utc(),
        "release_name": "ENTERPRISE_AI_CIO_V1",
        "release_status": "READY_FOR_FREEZE" if ready else "BLOCKED",
        "required_output_count": len(REQUIRED_OUTPUTS),
        "present_output_count": sum(1 for item in checks if item["status"] == "PRESENT"),
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "governance": {
            "paper_trade_mode": True,
            "live_trading_enabled": False,
            "broker_execution_enabled": False,
            "automatic_release_enabled": False,
            "manual_review_required": True,
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Enterprise AI CIO V1 Release Readiness",
        "",
        f"- Release status: **{report.get('release_status', 'UNKNOWN')}**",
        f"- Outputs present: {report.get('present_output_count', 0)}/{report.get('required_output_count', 0)}",
        "- Paper trade mode: True",
        "- Live trading enabled: False",
        "- Broker execution enabled: False",
        "",
        "## Contract Checks",
    ]
    for item in report.get("checks", []):
        lines.append(f"- {item.get('file')}: {item.get('status')}")
    lines.extend(["", "## Blockers"])
    lines.extend(f"- {value}" for value in report.get("blockers", []))
    if not report.get("blockers"):
        lines.append("- None")
    lines.extend(["", "## Warnings"])
    lines.extend(f"- {value}" for value in report.get("warnings", []))
    if not report.get("warnings"):
        lines.append("- None")
    lines.extend(["", "## Governance", "", "Manual review and merge approval are required. This report never releases, deploys, allocates capital, or executes trades."])
    return "\n".join(lines) + "\n"


def build_and_write_release_readiness(results_dir: str | Path) -> dict[str, Any]:
    root = Path(results_dir)
    root.mkdir(parents=True, exist_ok=True)
    report = build_release_readiness(root)
    (root / "enterprise_ai_cio_release_readiness.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "enterprise_ai_cio_release_readiness.md").write_text(render_markdown(report), encoding="utf-8")
    return report
