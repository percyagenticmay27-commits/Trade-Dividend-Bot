"""Combine existing AI CIO dashboard evidence with Registry v2 plugin evidence.

Read-only and paper-only. This adapter does not alter dashboard calculations,
registry state, cash, allocations, governance records, strategy files, or broker
state. It never imports external strategy production code.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.dividend_bot.enterprise_dashboard_evidence_adapter import (
    build_dashboard_evidence,
)
from src.dividend_bot.registry_declared_evidence import (
    load_registry_declared_evidence,
)

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True


def _read_mapping(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.is_file():
        return {}, f"missing registry evidence: {path}"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, f"invalid registry evidence {path}: {exc}"
    if not isinstance(value, dict):
        return {}, f"invalid registry evidence {path}: root must be an object"
    return value, None


def _strategy_summary(strategies: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "strategy_count": len(strategies),
        "available_count": sum(
            item.get("evidence_status") == "AVAILABLE" for item in strategies
        ),
        "partial_count": sum(
            item.get("evidence_status") == "PARTIAL" for item in strategies
        ),
        "registry_only_count": sum(
            item.get("evidence_status") == "REGISTRY_ONLY" for item in strategies
        ),
        "required_evidence_missing_count": sum(
            item.get("evidence_status") == "REQUIRED_EVIDENCE_MISSING"
            for item in strategies
        ),
        "declared_artifact_count": sum(
            int(item.get("declared_artifact_count", 0) or 0)
            for item in strategies
        ),
        "available_artifact_count": sum(
            int(item.get("available_artifact_count", 0) or 0)
            for item in strategies
        ),
    }


def build_registry_dashboard_evidence_v2(
    *,
    root_dir: str | Path = ".",
    results_dir: str | Path = "results",
    state_dir: str | Path = "state",
) -> dict[str, Any]:
    """Build dashboard evidence with registry declarations as the plugin source.

    Existing host evidence remains available for backward compatibility and for
    enterprise-level state such as the paper cash account. Registry-declared
    artifacts are loaded independently per strategy and never replaced by
    fabricated values when unavailable.
    """
    root = Path(root_dir)
    results = Path(results_dir)
    state = Path(state_dir)
    if not results.is_absolute():
        results = root / results
    if not state.is_absolute():
        state = root / state

    host_evidence = build_dashboard_evidence(
        root_dir=root,
        results_dir=results,
        state_dir=state,
    )
    registry_path = results / "enterprise_dividend_service_registry.json"
    registry, registry_warning = _read_mapping(registry_path)

    if registry:
        strategies, registry_warnings = load_registry_declared_evidence(
            registry,
            root_dir=root,
        )
        plugin_evidence_source = "REGISTRY_V2_DECLARED_ARTIFACTS"
    else:
        strategies = []
        registry_warnings = []
        plugin_evidence_source = "NONE"

    warnings = list(host_evidence.get("warnings", []))
    warnings.extend(registry_warnings)
    if registry_warning:
        warnings.append(registry_warning)

    required_failures = [
        item["strategy_id"]
        for item in strategies
        if item.get("required_artifact_failure")
    ]

    return {
        **host_evidence,
        "dashboard_evidence_contract_version": "2.0",
        "dashboard_scope": "ENTERPRISE_ALL_REGISTERED_STRATEGIES",
        "plugin_evidence_source": plugin_evidence_source,
        "registry_path": str(registry_path),
        "registry_declared_strategy_evidence": strategies,
        "registry_declared_evidence_summary": _strategy_summary(strategies),
        "required_plugin_evidence_failures": required_failures,
        "plugin_evidence_available": any(
            item.get("available_artifact_count", 0) for item in strategies
        ),
        "evidence_policy": {
            "registry_declared_artifacts_preferred": True,
            "host_state_fallback_retained": True,
            "fallback_is_authoritative_plugin_evidence": False,
            "missing_optional_artifacts_fabricated": False,
            "external_plugin_code_imported": False,
            "read_only": True,
            "paper_trade_mode": True,
        },
        "warnings": sorted(set(str(item) for item in warnings if item)),
    }
