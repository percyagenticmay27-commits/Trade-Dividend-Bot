from __future__ import annotations

from copy import deepcopy

from src.dividend_bot.enterprise_dashboard_intelligence_publisher import (
    attach_enterprise_dashboard_intelligence,
    build_dashboard_intelligence_publication,
    build_enterprise_dashboard_intelligence,
)


def _discovery() -> dict:
    return {
        "summary": {
            "registered_strategy_count": 2,
            "enabled_strategy_count": 2,
            "paper_compatible_strategy_count": 2,
        },
        "strategies": [
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Strategy",
                "strategy_type": "DIVIDEND_ETF",
                "enabled": True,
                "paper_trade_mode": True,
                "paper_compatible": True,
                "reporting_only": True,
                "runtime_status": "RUNNING",
                "health_status": "HEALTHY",
                "readiness": "READY",
            },
            {
                "strategy_id": "SWING-001",
                "display_name": "Swing Strategy",
                "strategy_type": "SWING",
                "enabled": True,
                "paper_trade_mode": True,
                "paper_compatible": True,
                "reporting_only": True,
                "runtime_status": "RUNNING",
                "health_status": "HEALTHY",
                "readiness": "READY",
            },
        ],
    }


def _kpis() -> list[dict]:
    return [
        {
            "strategy_id": "DIVIDEND-001",
            "display_name": "Dividend Strategy",
            "evidence_status": "AVAILABLE",
            "allocated_capital": 6000,
            "portfolio_value": 6400,
            "income": 300,
            "realized_gain": 120,
            "unrealized_gain": 280,
            "watchlist_count": 4,
            "position_count": 5,
            "win_rate_percent": 70,
            "wins": 7,
            "losses": 3,
            "completed_observations": 10,
            "yield_percent": 5,
            "yield_basis": 6000,
            "capital_appreciation": 400,
        },
        {
            "strategy_id": "SWING-001",
            "display_name": "Swing Strategy",
            "evidence_status": "AVAILABLE",
            "allocated_capital": 4000,
            "portfolio_value": 4500,
            "income": 100,
            "realized_gain": 250,
            "unrealized_gain": 250,
            "watchlist_count": 8,
            "position_count": 3,
            "win_rate_percent": 60,
            "wins": 6,
            "losses": 4,
            "completed_observations": 10,
            "yield_percent": 1,
            "yield_basis": 4000,
            "capital_appreciation": 500,
        },
    ]


def test_builds_all_three_phase_3_documents_once() -> None:
    document, warnings = build_enterprise_dashboard_intelligence(
        strategy_discovery=_discovery(),
        strategy_kpis=_kpis(),
    )

    assert document["registered_strategy_count"] == 2
    assert document["strategy_ids"] == ["DIVIDEND-001", "SWING-001"]
    assert "ai_cio_strategy_interpretation" in document
    assert "enterprise_strategy_comparison" in document
    assert "enterprise_contributor_details" in document
    assert warnings == []


def test_attaches_identical_canonical_payload_to_both_dashboards() -> None:
    intelligence, _ = build_enterprise_dashboard_intelligence(
        strategy_discovery=_discovery(),
        strategy_kpis=_kpis(),
    )
    executive, investor = attach_enterprise_dashboard_intelligence(
        executive_dashboard={"name": "executive"},
        investor_dashboard={"name": "investor"},
        intelligence=intelligence,
    )

    assert executive["enterprise_dashboard_intelligence"] == intelligence
    assert investor["enterprise_dashboard_intelligence"] == intelligence
    assert (
        executive["enterprise_dashboard_intelligence"]
        == investor["enterprise_dashboard_intelligence"]
    )


def test_named_aliases_match_canonical_children() -> None:
    payloads, warnings = build_dashboard_intelligence_publication(
        strategy_discovery=_discovery(),
        strategy_kpis=_kpis(),
        executive_dashboard={},
        investor_dashboard={},
    )

    canonical = payloads["enterprise_dashboard_intelligence"]
    for dashboard_name in ("executive_dashboard", "investor_dashboard"):
        dashboard = payloads[dashboard_name]
        assert dashboard["ai_cio_strategy_interpretation"] == canonical[
            "ai_cio_strategy_interpretation"
        ]
        assert dashboard["enterprise_strategy_comparison"] == canonical[
            "enterprise_strategy_comparison"
        ]
        assert dashboard["enterprise_contributor_details"] == canonical[
            "enterprise_contributor_details"
        ]
    assert warnings == []


def test_preserves_existing_dashboard_calculations() -> None:
    executive_source = {
        "portfolio_value": 1234.56,
        "enterprise_summary": {"enterprise_status": "HEALTHY"},
    }
    investor_source = {
        "income": 88.25,
        "holdings": [{"symbol": "TEST", "market_value": 500}],
    }
    executive_before = deepcopy(executive_source)
    investor_before = deepcopy(investor_source)

    payloads, _ = build_dashboard_intelligence_publication(
        strategy_discovery=_discovery(),
        strategy_kpis=_kpis(),
        executive_dashboard=executive_source,
        investor_dashboard=investor_source,
    )

    assert executive_source == executive_before
    assert investor_source == investor_before
    assert payloads["executive_dashboard"]["portfolio_value"] == 1234.56
    assert payloads["investor_dashboard"]["income"] == 88.25
    assert payloads["investor_dashboard"]["holdings"] == investor_before["holdings"]


def test_contributor_details_include_all_approved_more_detail_metrics() -> None:
    payloads, _ = build_dashboard_intelligence_publication(
        strategy_discovery=_discovery(),
        strategy_kpis=_kpis(),
        executive_dashboard={},
        investor_dashboard={},
    )
    details = payloads["enterprise_contributor_details"]

    assert set(details) == {
        "income",
        "performance",
        "realized_pnl",
        "unrealized_pnl",
        "win_rate",
        "yield",
        "capital_appreciation",
        "watchlist_count",
    }
    assert details["income"]["enterprise_value"] == 400.0
    assert details["capital_appreciation"]["enterprise_value"] == 900.0
    assert details["watchlist_count"]["enterprise_value"] == 12.0


def test_missing_kpi_evidence_remains_explicit_and_does_not_fail_publication() -> None:
    payloads, warnings = build_dashboard_intelligence_publication(
        strategy_discovery=_discovery(),
        strategy_kpis=_kpis()[:1],
        executive_dashboard={},
        investor_dashboard={},
    )

    income = payloads["enterprise_contributor_details"]["income"]
    assert income["complete"] is False
    assert income["missing_strategy_ids"] == ["SWING-001"]
    assert any("SWING-001" in warning for warning in warnings)


def test_empty_discovery_publishes_safe_empty_intelligence() -> None:
    payloads, warnings = build_dashboard_intelligence_publication(
        strategy_discovery={},
        strategy_kpis=[],
        executive_dashboard={"existing": True},
        investor_dashboard={"existing": True},
    )

    intelligence = payloads["enterprise_dashboard_intelligence"]
    assert intelligence["registered_strategy_count"] == 0
    assert intelligence["strategy_ids"] == []
    assert payloads["executive_dashboard"]["existing"] is True
    assert payloads["investor_dashboard"]["existing"] is True
    assert intelligence["paper_trade_mode"] is True
    assert intelligence["read_only"] is True
    assert warnings


def test_publication_safety_metadata_is_locked() -> None:
    payloads, _ = build_dashboard_intelligence_publication(
        strategy_discovery=_discovery(),
        strategy_kpis=_kpis(),
        executive_dashboard={},
        investor_dashboard={},
    )

    assert payloads["paper_trade_mode"] is True
    assert payloads["live_trading_enabled"] is False
    assert payloads["broker_execution_enabled"] is False
    assert payloads["capital_movement_enabled"] is False
    assert payloads["reporting_only"] is True
    assert payloads["read_only"] is True
    policy = payloads["enterprise_dashboard_intelligence"]["publication_policy"]
    assert policy["dashboard_calculations_changed"] is False
    assert policy["strategy_calculations_changed"] is False
    assert policy["recommendations_generated"] is False
    assert policy["allocation_changes_generated"] is False
