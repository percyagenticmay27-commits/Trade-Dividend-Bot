"""Publish read-only Phase 3 intelligence to Enterprise dashboards.

This module builds the AI CIO interpretation, strategy comparison, and
enterprise contributor documents once, then attaches the same canonical
intelligence payload to the Executive and Investor dashboards. It does not
change dashboard calculations, strategy calculations, allocations, governance,
capital, orders, or broker behavior.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.dividend_bot.enterprise_ai_cio_strategy_interpretation import (
    build_ai_cio_strategy_interpretation,
)
from src.dividend_bot.enterprise_contributor_engine import (
    build_all_enterprise_contributor_details,
)
from src.dividend_bot.enterprise_kpi_contract import (
    normalize_strategy_kpi_contract,
)
from src.dividend_bot.enterprise_strategy_comparison_engine import (
    build_enterprise_strategy_comparison,
)

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True

_CONTRIBUTOR_EVIDENCE_FIELDS = (
    "performance_percent",
    "return_percent",
    "total_return_percent",
    "realized_pnl",
    "unrealized_pnl",
    "wins",
    "losses",
    "completed_observations",
    "yield_percent",
    "current_yield_percent",
    "yield_basis",
    "invested_value",
    "capital_appreciation",
    "capital_appreciation_value",
    "lifecycle_status",
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _kpi_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [
        normalize_strategy_kpi_contract(item)
        for item in value
        if isinstance(item, Mapping)
    ]


def _preserve_contributor_evidence(
    interpretation: Mapping[str, Any],
    strategy_kpis: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Copy reported contributor fields and KPI status envelopes downstream."""
    enriched = dict(interpretation)
    raw_strategies = interpretation.get("strategies")
    strategies = (
        [dict(item) for item in raw_strategies if isinstance(item, Mapping)]
        if isinstance(raw_strategies, list)
        else []
    )
    kpi_index = {
        str(item.get("strategy_id") or "").strip(): item
        for item in strategy_kpis
        if isinstance(item, Mapping) and str(item.get("strategy_id") or "").strip()
    }
    for strategy in strategies:
        strategy_id = str(strategy.get("strategy_id") or "").strip()
        source = kpi_index.get(strategy_id)
        if source is None:
            continue
        for field in _CONTRIBUTOR_EVIDENCE_FIELDS:
            if field in source:
                strategy[field] = source[field]
        metrics = source.get("metrics")
        if isinstance(metrics, Mapping):
            strategy["metrics"] = {
                str(key): dict(value)
                for key, value in metrics.items()
                if isinstance(value, Mapping)
            }
        strategy["enterprise_kpi_contract_version"] = str(
            source.get("enterprise_kpi_contract_version") or "1.0"
        )
    enriched["strategies"] = strategies
    return enriched


def build_enterprise_dashboard_intelligence(
    *,
    strategy_discovery: Mapping[str, Any],
    strategy_kpis: Sequence[Mapping[str, Any]] = (),
) -> tuple[dict[str, Any], list[str]]:
    """Build the canonical Phase 3 intelligence document once."""
    normalized_kpis = _kpi_rows(strategy_kpis)
    interpretation, interpretation_warnings = build_ai_cio_strategy_interpretation(
        strategy_discovery=strategy_discovery,
        strategy_kpis=normalized_kpis,
    )
    interpretation = _preserve_contributor_evidence(
        interpretation,
        normalized_kpis,
    )
    comparison, comparison_warnings = build_enterprise_strategy_comparison(
        interpretation=interpretation,
    )
    contributors, contributor_warnings = build_all_enterprise_contributor_details(
        interpretation=interpretation,
    )

    warnings = sorted(
        set(
            interpretation_warnings
            + comparison_warnings
            + contributor_warnings
        )
    )
    document = {
        "schema_version": "1.0",
        "enterprise_kpi_contract_version": "1.0",
        "source": "ENTERPRISE_DASHBOARD_INTELLIGENCE_PUBLISHER",
        "scope": "ALL_REGISTERED_STRATEGIES",
        "ai_cio_strategy_interpretation": interpretation,
        "enterprise_strategy_comparison": comparison,
        "enterprise_contributor_details": contributors,
        "strategy_ids": list(interpretation.get("strategy_ids", [])),
        "registered_strategy_count": int(
            interpretation.get("registered_strategy_count", 0) or 0
        ),
        "publication_policy": {
            "single_canonical_build": True,
            "identical_dashboard_payloads": True,
            "dashboard_calculations_changed": False,
            "strategy_calculations_changed": False,
            "recommendations_generated": False,
            "allocation_changes_generated": False,
            "missing_evidence_invented": False,
            "not_applicable_is_zero": False,
        },
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "read_only": True,
    }
    return document, warnings


def attach_enterprise_dashboard_intelligence(
    *,
    executive_dashboard: Mapping[str, Any],
    investor_dashboard: Mapping[str, Any],
    intelligence: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Attach the identical canonical intelligence document to both dashboards."""
    executive = _mapping(executive_dashboard)
    investor = _mapping(investor_dashboard)
    canonical = _mapping(intelligence)

    executive["enterprise_dashboard_intelligence"] = canonical
    investor["enterprise_dashboard_intelligence"] = canonical

    for dashboard in (executive, investor):
        dashboard["ai_cio_strategy_interpretation"] = canonical.get(
            "ai_cio_strategy_interpretation", {}
        )
        dashboard["enterprise_strategy_comparison"] = canonical.get(
            "enterprise_strategy_comparison", {}
        )
        dashboard["enterprise_contributor_details"] = canonical.get(
            "enterprise_contributor_details", {}
        )

    return executive, investor


def build_dashboard_intelligence_publication(
    *,
    strategy_discovery: Mapping[str, Any],
    strategy_kpis: Sequence[Mapping[str, Any]] = (),
    executive_dashboard: Mapping[str, Any],
    investor_dashboard: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Build intelligence once and return all publication-ready payloads."""
    normalized_kpis = _kpi_rows(strategy_kpis)
    intelligence, warnings = build_enterprise_dashboard_intelligence(
        strategy_discovery=strategy_discovery,
        strategy_kpis=normalized_kpis,
    )
    executive, investor = attach_enterprise_dashboard_intelligence(
        executive_dashboard=executive_dashboard,
        investor_dashboard=investor_dashboard,
        intelligence=intelligence,
    )

    return {
        "executive_dashboard": executive,
        "investor_dashboard": investor,
        "enterprise_dashboard_intelligence": intelligence,
        "ai_cio_strategy_interpretation": intelligence[
            "ai_cio_strategy_interpretation"
        ],
        "enterprise_strategy_comparison": intelligence[
            "enterprise_strategy_comparison"
        ],
        "enterprise_contributor_details": intelligence[
            "enterprise_contributor_details"
        ],
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "read_only": True,
    }, warnings
