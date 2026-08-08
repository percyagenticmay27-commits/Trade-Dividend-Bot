from __future__ import annotations

from src.dividend_bot.enterprise_portal_strategy_ui_v2 import render_strategy_workspace, strategy_ui_css


def _report() -> dict:
    return {
        "strategy_kpis": [
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Income Strategy",
                "allocated_capital": 5000.0,
                "evidence_status": "AVAILABLE",
                "runtime_status": "READY",
                "health_status": "HEALTHY",
                "capabilities": [],
                "published_artifacts": [],
                "holdings": [
                    {
                        "symbol": "AAA",
                        "name": "Alpha Income ETF",
                        "yearly_distribution_yield_percent": 20.0,
                        "annual_income": 60.0,
                        "income_analytics_source": "market_data_snapshot.json",
                    }
                ],
                "income": 4.0,
                "net_income_received": 4.0,
                "gross_distribution_income": 5.0,
                "income_adjustments": -1.0,
                "projected_annual_income": 60.0,
                "income_events": [
                    {"date": "2026-08-01", "symbol": "AAA", "event_type": "DIVIDEND_RECEIVED", "amount": 5.0, "source": "paper_trade_log.csv"},
                    {"date": "2026-08-02", "symbol": "AAA", "event_type": "DIVIDEND_REVERSAL", "amount": -1.0, "source": "paper_trade_log.csv"},
                ],
            }
        ]
    }


def test_workspace_income_tab_uses_professional_renderer() -> None:
    output = render_strategy_workspace(_report(), audience="investor")
    assert "data-workspace-tab-panel='income'" in output
    assert "class='income-pro'" in output
    assert "Net Income Received" in output
    assert "Gross Distributions" in output
    assert "Income Adjustments" in output
    assert "Projected Annual Income" in output
    assert "Income by Holding" in output
    assert "Distribution History" in output
    assert "Reported Strategy Income" not in output


def test_workspace_income_is_strategy_scoped() -> None:
    report = _report()
    report["strategy_kpis"].append(
        {
            "strategy_id": "SWING-001",
            "display_name": "Trade Swing Bot",
            "allocated_capital": 4500.0,
            "evidence_status": "AVAILABLE",
            "runtime_status": "READY",
            "health_status": "HEALTHY",
            "capabilities": [],
            "published_artifacts": [],
            "holdings": [],
            "income": None,
            "projected_annual_income": None,
            "income_events": [],
        }
    )
    output = render_strategy_workspace(report, audience="executive")
    assert output.count("class='income-pro'") == 2
    assert "Alpha Income ETF" in output
    assert "No strategy-owned income projection evidence is currently reported" in output


def test_strategy_css_includes_income_styles() -> None:
    css = strategy_ui_css()
    assert ".income-summary-grid" in css
    assert ".income-table" in css
    assert ".income-positive" in css
    assert ".income-negative" in css
