"""Paper-only AI CIO system integration and readiness reporting.

This module verifies that the completed AI CIO engines can be discovered, invoked in
an ordered workflow, and summarized without permitting brokerage execution or
automatic policy changes.
"""
from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "ai_cio_system_integrator"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_OUTPUT_FILES = {
    "json": "ai_cio_system_integration.json",
    "markdown": "ai_cio_system_integration.md",
    "html": "ai_cio_system_integration.html",
}

DEFAULT_WORKFLOW = (
    "candidate_discovery_engine",
    "single_instrument_total_wealth_evaluator",
    "decision_stability_engine",
    "opportunity_replacement_manager",
    "decision_journal_engine",
    "portfolio_lifecycle_manager",
    "wealth_attribution_engine",
    "ai_cio_performance_analytics",
    "portfolio_risk_intelligence",
    "earnings_event_manager",
    "market_intelligence_center",
    "ai_cio_executive_dashboard",
    "ai_cio_weekly_board_letter",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _module_status(module_name: str) -> dict[str, Any]:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # import readiness must be reported, not crash the audit
        return {
            "module": module_name,
            "status": "MISSING_OR_IMPORT_ERROR",
            "version": None,
            "paper_trade_mode": None,
            "live_trading_enabled": None,
            "broker_execution_enabled": None,
            "reporting_only": None,
            "public_entry_points": [],
            "error": f"{type(exc).__name__}: {exc}",
        }

    entry_points = []
    for name in dir(module):
        if name.startswith(("build_", "write_", "format_")) and callable(getattr(module, name, None)):
            entry_points.append(name)

    paper = bool(getattr(module, "PAPER_TRADE_MODE", True))
    live = bool(getattr(module, "LIVE_TRADING_ENABLED", False))
    broker = bool(getattr(module, "BROKER_EXECUTION_ENABLED", False))
    reporting = bool(getattr(module, "REPORTING_ONLY", True))
    safe = paper and not live and not broker

    return {
        "module": module_name,
        "status": "READY" if safe else "SAFETY_VIOLATION",
        "version": str(getattr(module, "MODULE_VERSION", "Unknown")),
        "paper_trade_mode": paper,
        "live_trading_enabled": live,
        "broker_execution_enabled": broker,
        "reporting_only": reporting,
        "public_entry_points": sorted(entry_points),
        "error": None,
    }


def build_ai_cio_system_integration(
    *,
    workflow: Optional[Sequence[str]] = None,
    module_payloads: Optional[Mapping[str, Mapping[str, Any]]] = None,
    execute_available_builders: bool = False,
) -> dict[str, Any]:
    """Build the platform integration and readiness report.

    When ``execute_available_builders`` is true, the integrator invokes a module's
    first public ``build_*`` function only when a payload for that module is supplied.
    This prevents accidental execution with invented data.
    """
    ordered = list(workflow or DEFAULT_WORKFLOW)
    if any(not isinstance(name, str) or not name.strip() for name in ordered):
        raise ValueError("workflow entries must be non-empty module names")
    payloads = _safe_mapping(module_payloads)

    modules = []
    execution_results = []
    for position, module_name in enumerate(ordered, start=1):
        status = _module_status(module_name)
        status["workflow_order"] = position
        modules.append(status)

        if not execute_available_builders or status["status"] != "READY" or module_name not in payloads:
            continue

        try:
            module = importlib.import_module(module_name)
            builders = [name for name in status["public_entry_points"] if name.startswith("build_") and "and_write" not in name]
            if not builders:
                raise RuntimeError("No build_* entry point is available")
            builder_name = builders[0]
            result = getattr(module, builder_name)(**dict(_safe_mapping(payloads[module_name])))
            execution_results.append({
                "module": module_name,
                "builder": builder_name,
                "status": "PASSED",
                "result_type": type(result).__name__,
                "error": None,
            })
        except Exception as exc:
            execution_results.append({
                "module": module_name,
                "builder": None,
                "status": "FAILED",
                "result_type": None,
                "error": f"{type(exc).__name__}: {exc}",
            })

    ready = sum(1 for item in modules if item["status"] == "READY")
    missing = sum(1 for item in modules if item["status"] == "MISSING_OR_IMPORT_ERROR")
    violations = sum(1 for item in modules if item["status"] == "SAFETY_VIOLATION")
    execution_failures = sum(1 for item in execution_results if item["status"] == "FAILED")
    required_total = len(modules)
    readiness_percent = round((ready / required_total * 100.0) if required_total else 100.0, 2)

    if violations or execution_failures:
        overall_status = "BLOCKED"
    elif missing:
        overall_status = "INCOMPLETE"
    else:
        overall_status = "READY_FOR_END_TO_END_QA"

    warnings = []
    if missing:
        warnings.append(f"{missing} workflow module(s) could not be imported.")
    if not execute_available_builders:
        warnings.append("Builder execution was not requested; this report is a structural readiness audit.")

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
        "overall_status": overall_status,
        "readiness_percent": readiness_percent,
        "workflow_module_count": required_total,
        "ready_module_count": ready,
        "missing_or_import_error_count": missing,
        "safety_violation_count": violations,
        "execution_failure_count": execution_failures,
        "workflow": modules,
        "execution_results": execution_results,
        "governance": {
            "automatic_policy_changes_allowed": False,
            "brokerage_execution_allowed": False,
            "sector_allocation_entitlement": False,
            "html_ui_modernization_deferred": True,
        },
        "next_phase": "Run complete end-to-end paper-cycle QA, freeze the integrated architecture, then begin HTML/UI modernization.",
        "warnings": warnings,
        "errors": [],
    }


def format_ai_cio_system_integration_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# AI CIO System Integration Report",
        "",
        "## Executive Summary",
        "",
        f"- **Overall Status:** {report.get('overall_status', 'UNKNOWN')}",
        f"- **Readiness:** {report.get('readiness_percent', 0):.2f}%",
        f"- **Ready Modules:** {report.get('ready_module_count', 0)} / {report.get('workflow_module_count', 0)}",
        f"- **Missing or Import Errors:** {report.get('missing_or_import_error_count', 0)}",
        f"- **Safety Violations:** {report.get('safety_violation_count', 0)}",
        f"- **Execution Failures:** {report.get('execution_failure_count', 0)}",
        "",
        "## Ordered Workflow",
        "",
        "| Order | Module | Version | Status | Paper Only | Public Entry Points |",
        "|---:|---|---|---|---|---|",
    ]
    for item in report.get("workflow", []):
        entries = ", ".join(item.get("public_entry_points") or []) or "None detected"
        lines.append(
            f"| {item.get('workflow_order')} | {item.get('module')} | {item.get('version') or 'N/A'} | "
            f"{item.get('status')} | {item.get('paper_trade_mode')} | {entries} |"
        )
    if report.get("execution_results"):
        lines.extend(["", "## Builder Execution Results", "", "| Module | Builder | Status | Result Type | Error |", "|---|---|---|---|---|"])
        for item in report["execution_results"]:
            lines.append(f"| {item.get('module')} | {item.get('builder') or 'N/A'} | {item.get('status')} | {item.get('result_type') or 'N/A'} | {item.get('error') or ''} |")
    lines.extend([
        "",
        "## Governance",
        "",
        "The integrated workflow is paper-only. It cannot communicate with a brokerage, place orders, create sector quotas, or change investment policy automatically.",
        "",
        "## Next Phase",
        "",
        str(report.get("next_phase", "Not supplied")),
        "",
    ])
    return "\n".join(lines)


def format_ai_cio_system_integration_html(report: Mapping[str, Any]) -> str:
    import html
    markdown = format_ai_cio_system_integration_markdown(report)
    return "<!doctype html><html><head><meta charset='utf-8'><title>AI CIO System Integration</title><style>body{font-family:Arial,sans-serif;max-width:1200px;margin:0 auto;padding:32px;background:#f5f7fb;color:#172033}pre{white-space:pre-wrap;background:white;padding:28px;border-radius:14px;box-shadow:0 4px 18px rgba(0,0,0,.08);line-height:1.5}</style></head><body><pre>" + html.escape(markdown) + "</pre></body></html>"


def write_ai_cio_system_integration(
    payload: Mapping[str, Any],
    root_path: str = ".",
    output_files: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    report = build_ai_cio_system_integration(**dict(payload))
    root = Path(root_path)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    (root / files["json"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_ai_cio_system_integration_markdown(report), encoding="utf-8")
    (root / files["html"]).write_text(format_ai_cio_system_integration_html(report), encoding="utf-8")
    return report


def build_and_write_ai_cio_system_integration(
    payload: Mapping[str, Any],
    root_path: str = ".",
    output_files: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    return write_ai_cio_system_integration(payload, root_path, output_files)


if __name__ == "__main__":
    result = write_ai_cio_system_integration({})
    print(f"AI CIO Integration Status: {result['overall_status']} ({result['readiness_percent']:.2f}%)")
