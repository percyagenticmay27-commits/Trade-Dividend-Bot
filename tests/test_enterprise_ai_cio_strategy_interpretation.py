from copy import deepcopy

from src.dividend_bot.enterprise_ai_cio_strategy_interpretation import (
    build_ai_cio_strategy_interpretation,
)


def _discovery() -> dict[str, object]:
    return {
        "strategies": [
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Income Strategy",
                "strategy_type": "DIVIDEND_ETF",
                "runtime_status": "ONLINE",
                "health_status": "HEALTHY",
                "readiness": "READY",
                "enabled": True,
                "paper_trade_mode": True,
                "paper_compatible": True,
                "reporting_only": True,
            },
            {
                "strategy_id": "SWING-001",
                "display_name": "Trade Swing Bot",
                "strategy_type": "SWING",
                "runtime_status": "ONLINE",
                "health_status": "HEALTHY",
                "readiness": "READY",
                "enabled": True,
                "paper_trade_mode": True,
                "paper_compatible": True,
                "reporting_only": True,
            },
        ]
    }


def _kpis() -> list[dict[str, object]]:
    return [
        {
            "strategy_id": "DIVIDEND-001",
            "portfolio_value": 5200,
            "allocated_capital": 5000,
            "realized_gain": 100,
            "unrealized_gain": 100,
            "income": 240,
            "watchlist_count": 8,
            "position_count": 5,
            "opportunity_quality": 72,
            "win_rate_percent": 62,
            "evidence_status": "AVAILABLE",
        },
        {
            "strategy_id": "SWING-001",
            "portfolio_value": 4700,
            "allocated_capital": 4500,
            "realized_gain": 150,
            "unrealized_gain": 50,
            "income": 0,
            "watchlist_count": 14,
            "position_count": 3,
            "opportunity_quality": 84,
            "win_rate_percent": 68,
            "evidence_status": "AVAILABLE",
        },
    ]


def test_interprets_all_registered_strategies_in_registry_order() -> None:
    report, warnings = build_ai_cio_strategy_interpretation(
        strategy_discovery=_discovery(), strategy_kpis=_kpis()
    )

    assert warnings == []
    assert report["strategy_ids"] == ["DIVIDEND-001", "SWING-001"]
    assert [row["strategy_id"] for row in report["strategies"]] == [
        "DIVIDEND-001",
        "SWING-001",
    ]


def test_builds_enterprise_totals_with_completeness_metadata() -> None:
    report, _ = build_ai_cio_strategy_interpretation(
        strategy_discovery=_discovery(), strategy_kpis=_kpis()
    )

    portfolio = report["enterprise_totals"]["portfolio_value"]
    assert portfolio == {
        "value": 9900.0,
        "reported_strategy_count": 2,
        "registered_strategy_count": 2,
        "complete": True,
    }
    assert report["enterprise_totals"]["watchlist_count"]["value"] == 22
    assert report["enterprise_totals"]["position_count"]["value"] == 8


def test_missing_kpi_evidence_remains_explicit_not_invented_zero() -> None:
    report, warnings = build_ai_cio_strategy_interpretation(
        strategy_discovery=_discovery(), strategy_kpis=_kpis()[:1]
    )

    swing = report["strategies"][1]
    assert swing["portfolio_value"] is None
    assert swing["evidence_status"] == "REGISTRY_ONLY"
    assert report["enterprise_totals"]["portfolio_value"]["value"] == 5200.0
    assert report["enterprise_totals"]["portfolio_value"]["complete"] is False
    assert "SWING-001: strategy KPI evidence is unavailable." in warnings


def test_builds_evidence_only_leader_comparisons() -> None:
    report, _ = build_ai_cio_strategy_interpretation(
        strategy_discovery=_discovery(), strategy_kpis=_kpis()
    )

    leaders = report["strategy_comparisons"]["leaders"]
    assert leaders["portfolio_value"]["strategy_id"] == "DIVIDEND-001"
    assert leaders["opportunity_quality"]["strategy_id"] == "SWING-001"
    assert leaders["win_rate_percent"]["comparison_basis"] == "REPORTED_EVIDENCE_ONLY"


def test_summarizes_health_readiness_and_commentary() -> None:
    report, _ = build_ai_cio_strategy_interpretation(
        strategy_discovery=_discovery(), strategy_kpis=_kpis()
    )

    assert report["health_summary"] == {"HEALTHY": 2}
    assert report["readiness_summary"] == {"READY": 2}
    assert "Dividend Income Strategy" in report["commentary"][0]
    assert "Trade Swing Bot" in report["commentary"][0]


def test_ignores_unregistered_and_duplicate_kpi_rows_with_warnings() -> None:
    rows = _kpis()
    rows.append(dict(rows[0]))
    rows.append({"strategy_id": "OPTIONS-001", "portfolio_value": 1000})

    report, warnings = build_ai_cio_strategy_interpretation(
        strategy_discovery=_discovery(), strategy_kpis=rows
    )

    assert report["registered_strategy_count"] == 2
    assert "Duplicate strategy KPI row ignored: DIVIDEND-001" in warnings
    assert "Unregistered strategy KPI row ignored: OPTIONS-001" in warnings


def test_empty_or_malformed_discovery_returns_safe_empty_interpretation() -> None:
    report, warnings = build_ai_cio_strategy_interpretation(
        strategy_discovery={"strategies": "bad"}, strategy_kpis=[]
    )

    assert warnings == []
    assert report["registered_strategy_count"] == 0
    assert report["strategies"] == []
    assert report["commentary"] == [
        "No registered strategy evidence is available for AI CIO interpretation."
    ]
    assert report["paper_trade_mode"] is True
    assert report["broker_execution_enabled"] is False
    assert report["capital_movement_enabled"] is False


def test_does_not_mutate_discovery_or_kpi_inputs() -> None:
    discovery = _discovery()
    kpis = _kpis()
    discovery_before = deepcopy(discovery)
    kpis_before = deepcopy(kpis)

    report, _ = build_ai_cio_strategy_interpretation(
        strategy_discovery=discovery, strategy_kpis=kpis
    )

    assert discovery == discovery_before
    assert kpis == kpis_before
    assert report["read_only"] is True
    assert report["reporting_only"] is True
    assert report["live_trading_enabled"] is False
