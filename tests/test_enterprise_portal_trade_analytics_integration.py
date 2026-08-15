from __future__ import annotations

from src.dividend_bot.enterprise_portal_strategy_ui_v2 import (
    render_strategy_workspace,
    strategy_ui_css,
)


def _report() -> dict:
    return {
        "strategy_kpis": [
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Income Strategy",
                "strategy_type": "DIVIDEND",
                "allocated_capital": 5000.0,
                "income": 125.0,
                "income_events": [{"symbol": "AMDW", "amount": 12.5}],
                "capabilities": ["income"],
                "published_artifacts": [],
                "evidence_status": "AVAILABLE",
            },
            {
                "strategy_id": "SWING-001",
                "display_name": "Trade Swing Bot",
                "strategy_type": "SWING",
                "allocated_capital": 4500.0,
                "paper_trade_mode": True,
                "capabilities": ["trade_analytics"],
                "published_artifacts": [{
                    "artifact_id": "swing_trade_analytics_report",
                    "artifact_type": "trade_analytics",
                    "path": "results/swing_trade_analytics_report.json",
                }],
                "evidence_status": "AVAILABLE",
                "position_count": 1,
                "portfolio_value": 4525.52,
                "holdings": [{
                    "symbol": "SOXL",
                    "position_status": "OPEN",
                    "shares": 8.04145854,
                    "current_price": 143.264297485352,
                    "market_value": 1152.05,
                    "active_strategy": "Strategy A",
                }],
                "trade_analytics_status": "AVAILABLE",
                "trade_analytics": {
                    "generated_at": "2026-08-15T01:00:00Z",
                    "max_drawdown_policy": "AUTHORITATIVE_POSITION_HISTORY_ONLY",
                    "max_drawdown_inference_allowed": False,
                    "open_positions": [{
                        "symbol": "SOXL",
                        "entry_date": "2026-08-04",
                        "entry_price": 139.899993896484,
                        "current_price": 143.264297485352,
                        "gain_loss_amount": 27.05,
                        "gain_loss_percent": 2.404444,
                        "max_drawdown_amount": 82.42,
                        "max_drawdown_percent": 7.308378,
                        "position_status": "OPEN",
                    }],
                    "closed_positions": [],
                },
            },
        ]
    }


def test_swing_income_tab_routes_to_trade_analytics() -> None:
    output = render_strategy_workspace(_report(), audience="executive")

    swing_start = output.index("id='strategy-SWING-001'")
    swing_workspace = output[swing_start:]
    assert "data-section-kind='trade-analytics'" in swing_workspace
    assert ">Trade Analytics</button>" in swing_workspace
    assert "Trade Analytics / Position Performance" in swing_workspace
    assert "SOXL" in swing_workspace
    assert "$82.42" in swing_workspace
    assert "AUTHORITATIVE_POSITION_HISTORY_ONLY" in swing_workspace
    assert "<h3>Income</h3>" not in swing_workspace


def test_swing_holdings_deep_link_uses_position_performance_not_dividend_income() -> None:
    output = render_strategy_workspace(_report(), audience="executive")

    swing_start = output.index("id='strategy-SWING-001'")
    swing_workspace = output[swing_start:]
    assert "holdings-overview-table" in swing_workspace
    assert "holdings-management-table" in swing_workspace
    assert "holdings-income-table" not in swing_workspace
    # One authoritative renderer is on Holdings and one is on the backward-
    # compatible former Income tab.
    assert swing_workspace.count("Trade Analytics / Position Performance") == 2
    assert swing_workspace.count("$82.42") == 2


def test_dividend_income_section_remains_unchanged() -> None:
    output = render_strategy_workspace(_report(), audience="executive")

    dividend_start = output.index("id='strategy-DIVIDEND-001'")
    swing_start = output.index("id='strategy-SWING-001'")
    dividend_workspace = output[dividend_start:swing_start]
    assert "id='tab-DIVIDEND-001-income'" in dividend_workspace
    assert ">Income</button>" in dividend_workspace
    assert "<h3>Income</h3>" in dividend_workspace
    assert "Trade Analytics / Position Performance" not in dividend_workspace
    assert "$5,000.00" in dividend_workspace


def test_strategy_workspace_preserves_allocations_and_safety_labels() -> None:
    output = render_strategy_workspace(_report(), audience="executive")

    assert "$5,000.00 allocated" in output
    assert "$4,500.00 allocated" in output
    assert "PAPER ONLY" in output
    assert "READ ONLY" in output
    assert "SWING-001" in output


def test_trade_analytics_styles_are_in_portal_css() -> None:
    css = strategy_ui_css()

    assert ".trade-analytics{" in css
    assert ".trade-gain{color:#087443" in css
    assert ".trade-loss{color:#b42318" in css
