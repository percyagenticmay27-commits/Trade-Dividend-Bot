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
from src.dividend_bot.enterprise_strategy_comparison_engine import (
    build_enterprise_strategy_comparison,
)

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _kpi_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def build_enterprise_dashboard_intelligence(
    *,
    strategy_discovery: Mapping[str, Any],
    strategy_kpis: Sequence[Mapping[str, Any]] = (),
) -> tuple[dict[str, Any], list[str]]:
    """Build the canonical Phase 3 intelligence document once."""
    interpretation, interpretation_warnings = build_ai_cio_strategy_interpretation(
        strategy_discovery=strategy_discovery,
        strategy_kpis=strategy_kpis,
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

    # Named aliases make current UI consumers explicit while preserving one
    # canonical parent document for equality and deployment validation.
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
