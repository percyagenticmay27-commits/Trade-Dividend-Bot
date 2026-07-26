"""Platform V1 release validation for the paper-only Trade Dividend Bot."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "platform_v1_release"
MODULE_VERSION = "1.1.0"
SCHEMA_VERSION = "1.0"
RELEASE_VERSION = "1.0.0"
RELEASE_TAG = "dividend-platform-v1.0.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

REQUIRED_RELEASE_FILES = (
    "docs/PLATFORM_V1_DIVIDEND_FREEZE.md",
    "docs/CLOUD_READINESS_AND_DIGITALOCEAN_DEPLOYMENT.md",
    "docs/PAPER_PRODUCTION_ACCEPTANCE_TEST.md",
    "docs/PAPER_CAPITAL_ALLOCATION_UI.md",
    "docs/DASHBOARD_AND_WORKFLOW_SCOPE_FREEZE.md",
    "src/dividend_bot/cloud_readiness.py",
    "src/dividend_bot/scheduled_report_email.py",
    "src/dividend_bot/enterprise_html_dashboard.py",
    "src/dividend_bot/paper_cash_account.py",
    "src/dividend_bot/paper_capital_allocation.py",
    "src/dividend_bot/paper_capital_allocation_server.py",
    "src/dividend_bot/paper_production_acceptance.py",
)

REQUIRED_RUNTIME_ARTIFACTS = (
    "state/paper_cash_account.json",
    "state/paper_cash_transactions.jsonl",
    "state/paper_allocation_requests.jsonl",
    "results/html/index.html",
    "logs/dividend_bot.jsonl",
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_files(root_dir: str | Path, required_files: Sequence[str]) -> dict[str, Any]:
    root = Path(root_dir)
    missing = sorted(name for name in required_files if not (root / name).is_file())
    empty = sorted(name for name in required_files if (root / name).is_file() and (root / name).stat().st_size == 0)
    return {
        "status": "READY" if not missing and not empty else "NOT_READY",
        "missing_files": missing,
        "empty_files": empty,
        "checked_files": list(required_files),
    }


def validate_release_files(root_dir: str | Path, required_files: Sequence[str] = REQUIRED_RELEASE_FILES) -> dict[str, Any]:
    return validate_files(root_dir, required_files)


def build_release_manifest(
    root_dir: str | Path,
    *,
    acceptance_status: str,
    cloud_status: str,
    combined_test_total: int,
    runtime_artifacts_required: bool = False,
    generated_at_utc: Optional[str] = None,
    required_files: Sequence[str] = REQUIRED_RELEASE_FILES,
    runtime_artifacts: Sequence[str] = REQUIRED_RUNTIME_ARTIFACTS,
) -> dict[str, Any]:
    files = validate_files(root_dir, required_files)
    runtime = validate_files(root_dir, runtime_artifacts) if runtime_artifacts_required else {
        "status": "NOT_REQUIRED",
        "missing_files": [],
        "empty_files": [],
        "checked_files": list(runtime_artifacts),
    }
    accepted = str(acceptance_status).upper() == "ACCEPTED"
    cloud_ready = str(cloud_status).upper() == "HEALTHY"
    tests_valid = int(combined_test_total) > 0
    runtime_ready = runtime["status"] in {"READY", "NOT_REQUIRED"}
    ready = files["status"] == "READY" and accepted and cloud_ready and tests_valid and runtime_ready
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "release_version": RELEASE_VERSION,
        "release_tag": RELEASE_TAG,
        "generated_at_utc": generated_at_utc or _now_utc(),
        "status": "RELEASE_READY" if ready else "RELEASE_BLOCKED",
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "release_checks": {
            "files": files,
            "runtime_artifacts": runtime,
            "paper_production_acceptance": str(acceptance_status).upper(),
            "cloud_readiness": str(cloud_status).upper(),
            "combined_test_total": int(combined_test_total),
        },
        "included_workflows": [
            "paper_cash_account",
            "paper_cash_funding_ui",
            "strategy_plugin_discovery",
            "paper_capital_allocation",
            "dashboard_and_workflow_scope_freeze",
        ],
        "governance": {
            "order_execution_allowed": False,
            "brokerage_communication_allowed": False,
            "capital_movement_allowed": False,
            "automatic_policy_changes_allowed": False,
            "future_live_mode_investor_controlled": True,
            "investor_approval_required": True,
        },
        "deferred_scope": ["Swing", "Options", "Futures", "Robinhood live execution"],
    }


def write_release_manifest(manifest: Mapping[str, Any], output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def render_release_markdown(manifest: Mapping[str, Any]) -> str:
    checks = manifest["release_checks"]
    return "\n".join([
        "# Trade Dividend Bot Platform V1 Release",
        "",
        f"- Release Version: {manifest['release_version']}",
        f"- Release Tag: `{manifest['release_tag']}`",
        f"- Status: **{manifest['status']}**",
        f"- Combined Test Total: {checks['combined_test_total']}",
        f"- Cloud Readiness: {checks['cloud_readiness']}",
        f"- Paper Production Acceptance: {checks['paper_production_acceptance']}",
        "",
        "## Included Final Workflows",
        "",
        *[f"- {name}" for name in manifest["included_workflows"]],
        "",
        "## Permanent Safety Boundaries",
        "",
        "- Paper trading only",
        "- No brokerage communication or execution",
        "- No real capital movement",
        "- Investor controls any future live-mode transition",
        "- Investor approval remains required",
        "",
    ])


def write_release_markdown(manifest: Mapping[str, Any], output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_release_markdown(manifest), encoding="utf-8")
    return str(path)
