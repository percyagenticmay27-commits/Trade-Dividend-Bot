"""
bot_capabilities.py

Read-only platform-facing capability profile for the deployed Dividend Bot.

This module does not modify trading logic, does not connect to any broker,
does not place orders, and is permanently constrained to PAPER ONLY metadata
reporting.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


MODULE_NAME = "bot_capabilities"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"


_REQUIRED_KEYS = {
    "bot_name",
    "bot_type",
    "bot_version",
    "schema_version",
    "generated_at_utc",
    "paper_trade_mode",
    "live_trading_enabled",
    "broker_execution_enabled",
    "capabilities",
    "supported_reports",
    "supported_outputs",
    "operational_scripts",
    "platform_integration_files",
    "safety_guarantees",
    "limitations",
}


_CAPABILITIES = [
    "paper_trading",
    "dividend_etf_management",
    "portfolio_snapshot_generation",
    "daily_paper_reporting",
    "weekly_portfolio_review",
    "strategy_health_reporting",
    "live_readiness_reporting",
    "email_report_delivery",
    "backup_support",
    "log_rotation_support",
    "health_check_support",
]


_SUPPORTED_REPORTS = [
    "daily_paper_report.md",
    "daily_change_summary.md",
    "strategy_health_report.md",
    "live_readiness_report.md",
    "weekly_portfolio_review.md",
    "performance_summary.md",
    "walk_forward_summary.md",
]


_SUPPORTED_OUTPUTS = [
    "paper_state.json",
    "snapshot_manifest.json",
    "paper_trade_log.csv",
    "portfolio_snapshot.csv",
    "paper_signal_history.csv",
    "strategy_health.csv",
    "pair_health.csv",
    "live_readiness.csv",
    "email_delivery_log.csv",
    "performance_report.csv",
]


_OPERATIONAL_SCRIPTS = [
    "health_check_dividend_bot.sh",
    "backup_dividend_bot.sh",
    "rotate_dividend_logs.sh",
    "deploy_dividend_update.sh",
]


_PLATFORM_INTEGRATION_FILES = [
    "bot_capabilities.py",
    "bot_capabilities.json",
]


_SAFETY_GUARANTEES = [
    "paper_trade_mode is always True",
    "live_trading_enabled is always False",
    "broker_execution_enabled is always False",
    "no broker execution is performed",
    "no Robinhood execution is performed",
    "no real order placement is performed",
    "module is read-only except for writing bot_capabilities.json",
    "module uses Python standard library only",
]


_LIMITATIONS = [
    "does not execute trades",
    "does not connect to Robinhood",
    "does not connect to broker APIs",
    "does not modify trading strategy logic",
    "does not modify run_daily_paper_cycle.py",
    "does not modify send_daily_reports.py",
    "does not verify live market prices",
    "does not verify email delivery status",
    "does not perform runtime diagnostics beyond static capability reporting",
]


def _utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_bot_capabilities() -> Dict[str, Any]:
    """
    Build the read-only Dividend Bot capability profile.

    Returns:
        A JSON-serializable dictionary describing supported capabilities,
        outputs, operational scripts, safety guarantees, and limitations.
    """
    payload: Dict[str, Any] = {
        "bot_name": "Agentic Robin Dividend Bot",
        "bot_type": "paper_only_dividend_etf_management_bot",
        "bot_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "generated_by": GENERATED_BY,
        "module_name": MODULE_NAME,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capabilities": list(_CAPABILITIES),
        "supported_reports": list(_SUPPORTED_REPORTS),
        "supported_outputs": list(_SUPPORTED_OUTPUTS),
        "operational_scripts": list(_OPERATIONAL_SCRIPTS),
        "platform_integration_files": list(_PLATFORM_INTEGRATION_FILES),
        "safety_guarantees": list(_SAFETY_GUARANTEES),
        "limitations": list(_LIMITATIONS),
    }
    validate_bot_capabilities(payload)
    return payload


def validate_bot_capabilities(payload: Dict[str, Any]) -> bool:
    """
    Validate a Dividend Bot capability profile.

    Safety validation is intentionally strict. Any payload that suggests live
    trading, broker execution, Robinhood execution, or real order placement is
    rejected.

    Args:
        payload: Capability profile dictionary to validate.

    Returns:
        True when the payload is valid.

    Raises:
        TypeError: If payload is not a dictionary.
        ValueError: If required fields are missing or safety rules are violated.
    """
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dictionary")

    missing_keys = sorted(_REQUIRED_KEYS.difference(payload.keys()))
    if missing_keys:
        raise ValueError(f"missing required capability keys: {missing_keys}")

    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")

    if payload.get("paper_trade_mode") is not True:
        raise ValueError("paper_trade_mode must be True")

    if payload.get("live_trading_enabled") is not False:
        raise ValueError("live_trading_enabled must be False")

    if payload.get("broker_execution_enabled") is not False:
        raise ValueError("broker_execution_enabled must be False")

    list_fields = [
        "capabilities",
        "supported_reports",
        "supported_outputs",
        "operational_scripts",
        "platform_integration_files",
        "safety_guarantees",
        "limitations",
    ]
    for field_name in list_fields:
        if not isinstance(payload.get(field_name), list):
            raise ValueError(f"{field_name} must be a list")

    forbidden_capabilities = {
        "live_trading",
        "real_trading",
        "broker_execution",
        "robinhood_execution",
        "real_order_placement",
        "place_real_orders",
    }
    capabilities = {str(item).strip().lower() for item in payload["capabilities"]}
    violations = sorted(capabilities.intersection(forbidden_capabilities))
    if violations:
        raise ValueError(f"forbidden live-trading capabilities detected: {violations}")

    safety_text = " ".join(str(item).lower() for item in payload["safety_guarantees"])
    required_safety_phrases = [
        "paper_trade_mode is always true",
        "live_trading_enabled is always false",
        "broker_execution_enabled is always false",
        "no broker execution",
        "no robinhood execution",
        "no real order placement",
    ]
    for phrase in required_safety_phrases:
        if phrase not in safety_text:
            raise ValueError(f"missing safety guarantee: {phrase}")

    return True


def write_bot_capabilities(path: str = "bot_capabilities.json") -> Dict[str, Any]:
    """
    Write the capability profile to JSON.

    This is the module's only file-writing operation. It writes static platform
    metadata only and does not alter trading state, reports, workflows, broker
    settings, or order logic.

    Args:
        path: Destination JSON path. Defaults to bot_capabilities.json.

    Returns:
        The validated payload that was written.
    """
    payload = build_bot_capabilities()
    output_path = Path(path)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_bot_capabilities(path: str = "bot_capabilities.json") -> Dict[str, Any]:
    """
    Read and validate a capability profile JSON file.

    Args:
        path: Source JSON path. Defaults to bot_capabilities.json.

    Returns:
        The validated capability profile payload.
    """
    input_path = Path(path)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    validate_bot_capabilities(payload)
    return payload


def format_bot_capabilities_summary(payload: Dict[str, Any]) -> str:
    """
    Format a concise human-readable capability summary.

    Args:
        payload: Capability profile dictionary.

    Returns:
        A Markdown-compatible text summary.
    """
    validate_bot_capabilities(payload)

    capabilities = payload.get("capabilities", [])
    reports = payload.get("supported_reports", [])
    outputs = payload.get("supported_outputs", [])
    scripts = payload.get("operational_scripts", [])

    lines: List[str] = [
        f"# {payload['bot_name']} Capabilities",
        "",
        f"- Bot type: {payload['bot_type']}",
        f"- Bot version: {payload['bot_version']}",
        f"- Schema version: {payload['schema_version']}",
        f"- Generated at UTC: {payload['generated_at_utc']}",
        f"- Paper trade mode: {payload['paper_trade_mode']}",
        f"- Live trading enabled: {payload['live_trading_enabled']}",
        f"- Broker execution enabled: {payload['broker_execution_enabled']}",
        "",
        "## Capabilities",
    ]
    lines.extend(f"- {item}" for item in capabilities)
    lines.extend(["", "## Supported Reports"])
    lines.extend(f"- {item}" for item in reports)
    lines.extend(["", "## Supported Outputs"])
    lines.extend(f"- {item}" for item in outputs)
    lines.extend(["", "## Operational Scripts"])
    lines.extend(f"- {item}" for item in scripts)
    lines.extend(["", "## Safety Guarantees"])
    lines.extend(f"- {item}" for item in payload.get("safety_guarantees", []))
    lines.extend(["", "## Limitations"])
    lines.extend(f"- {item}" for item in payload.get("limitations", []))

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    write_bot_capabilities()
