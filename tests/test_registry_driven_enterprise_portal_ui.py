from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.enterprise_portal_strategy_ui import render_left_navigation, render_strategy_workspace
from src.dividend_bot.enterprise_strategy_kpi_adapter import build_strategy_kpis
from src.dividend_bot.portal_dashboard_routes import render_executive_dashboard_body, render_investor_dashboard_body


def _registry(tmp_path: Path) -> dict:
    swing_report = tmp_path / "swing_report.json"
    swing_report.write_text(json.dumps({
        "portfolio_value": 4750,
        "watchlist_count": 31,
        "open_positions": 7,
        "opportunity_quality_score": 84,
        "win_rate_percent": 62.5,
    }), encoding="utf-8")
    return {
        "strategy_plugins": [
            {
                "strategy_id": "DIVIDEND",
                "display_name": "Dividend Income Strategy",
                "status": "READY",
                "health": "HEALTHY",
                "paper_trade_mode": True,
            },
            {
                "strategy_id": "SWING-001",
                "display_name": "Trade Swing Bot",
                "status": "AVAILABLE",
                "health": "HEALTHY",
                "paper_trade_mode": True,
                "dashboard_artifacts": [{"report_path": str(swing_report)}],
            },
        ]
    }


def test_registry_iteration_builds_one_kpi_row_per_plugin(tmp_path: Path) -> None:
    rows, warnings = build_strategy_kpis(
        registry=_registry(tmp_path),
        strategy_allocations={"DIVIDEND": 5000, "SWING-001": 4500},
        root_dir=tmp_path,
    )
    assert [row["strategy_id"] for row in rows] == ["DIVIDEND", "SWING-001"]
    assert rows[0]["allocated_capital"] == 5000
    assert rows[1]["allocated_capital"] == 4500
    assert rows[1]["portfolio_value"] == 4750
    assert rows[1]["watchlist_count"] == 31
    assert rows[1]["position_count"] == 7
    assert rows[1]["opportunity_quality"] == 84
    assert rows[1]["win_rate_percent"] == 62.5
    assert warnings == []


def test_plugin_without_declared_artifacts_remains_visible(tmp_path: Path) -> None:
    rows, _ = build_strategy_kpis(registry=_registry(tmp_path), root_dir=tmp_path)
    dividend = next(row for row in rows if row["strategy_id"] == "DIVIDEND")
    assert dividend["evidence_status"] == "REGISTRY_ONLY"
    assert dividend["display_name"] == "Dividend Income Strategy"


def test_missing_external_evidence_warns_without_removing_plugin(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry["strategy_plugins"][1]["dashboard_artifacts"] = [{"path": str(tmp_path / "missing.json")}]
    rows, warnings = build_strategy_kpis(registry=registry, root_dir=tmp_path)
    assert len(rows) == 2
    assert any("declared evidence is missing" in warning for warning in warnings)


def test_left_navigation_contains_portal_routes_and_strategy_container() -> None:
    value = render_left_navigation("Executive Dashboard")
    assert "/cash" in value
    assert "/allocation" in value
    assert "/executive-dashboard" in value
    assert "/investor-dashboard" in value
    assert "registered-strategy-links" in value


def test_strategy_workspace_uses_one_view_analysis_and_more_link() -> None:
    report = {"strategy_kpis": [{
        "strategy_id": "SWING-001",
        "display_name": "Trade Swing Bot",
        "allocated_capital": 4500,
        "health_status": "HEALTHY",
        "evidence_status": "AVAILABLE",
        "watchlist_count": 31,
    }]}
    value = render_strategy_workspace(report, audience="executive")
    assert "...more" in value
    assert "One View Analysis" in value
    assert "AI CIO Commentary" in value
    assert "Trade Swing Bot" in value
    assert "Watchlist" in value


def test_executive_dashboard_labels_top_cards_as_enterprise_totals() -> None:
    value = render_executive_dashboard_body({
        "dashboard_scope": "ENTERPRISE_ALL_REGISTERED_STRATEGIES",
        "portfolio_summary": {"portfolio_value": 10000, "available_cash": 500, "allocated_cash": 9500},
        "enterprise_summary": {"registered_strategy_count": 2, "enterprise_status": "HEALTHY"},
        "strategy_kpis": [],
    })
    assert "Enterprise Portfolio Value" in value
    assert "Enterprise Available Cash" in value
    assert "Enterprise Allocated Capital" in value
    assert "Enterprise total" in value
    assert "enterprise-sidebar" in value


def test_investor_dashboard_distinguishes_enterprise_and_strategy_scope() -> None:
    value = render_investor_dashboard_body({
        "dashboard_scope": "ENTERPRISE_ALL_REGISTERED_STRATEGIES",
        "investor_summary": {"portfolio_value": 10000, "cash_or_reserve_value": 500},
        "strategy_kpis": [{
            "strategy_id": "DIVIDEND",
            "display_name": "Dividend Income Strategy",
            "allocated_capital": 5000,
            "health_status": "HEALTHY",
            "evidence_status": "REGISTRY_ONLY",
        }],
    })
    assert "Enterprise Portfolio Value" in value
    assert "Investor Strategy KPIs" in value
    assert "Dividend Income Strategy" in value
    assert "only this registered strategy's evidence" in value


def test_json_derived_text_is_escaped() -> None:
    value = render_strategy_workspace({"strategy_kpis": [{
        "strategy_id": "X",
        "display_name": "<script>alert(1)</script>",
        "allocated_capital": 1,
    }]}, audience="investor")
    assert "<script>alert(1)</script>" not in value
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in value
