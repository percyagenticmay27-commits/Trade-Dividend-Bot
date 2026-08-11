from src.dividend_bot.enterprise_portal_strategy_ui_v2 import (
    render_strategy_workspace,
    strategy_ui_css,
)


def _report():
    return {
        "strategy_kpis": [
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Income Strategy",
                "allocated_capital": 5000.0,
                "realized_gain": 12.5,
                "unrealized_gain": -203.06,
                "health_status": "HEALTHY",
                "evidence_status": "AVAILABLE",
                "runtime_status": "READY",
                "performance_detail": {
                    "position_lifecycle": [
                        {
                            "symbol": "PLTW",
                            "pair": "PLTW / PLTU",
                            "sleeve": "A",
                            "lifecycle_status": "PARKED_IN_SGOV",
                            "first_purchase_date": "2026-06-18",
                            "last_exit_date": "2026-06-18",
                            "last_exit_action": "PAPER_PARK_IN_SGOV",
                            "last_exit_value": 28.0,
                            "reentry_count": 0,
                            "evidence_source": "paper_trade_log.csv",
                        }
                    ]
                },
            }
        ]
    }


def test_performance_workspace_includes_position_sales_history() -> None:
    output = render_strategy_workspace(_report(), audience="executive")
    assert "panel-DIVIDEND-001-performance" in output
    assert "Position / Sales History" in output
    assert "PLTW" in output
    assert "PAPER_PARK_IN_SGOV" in output


def test_performance_workspace_keeps_existing_performance_metrics() -> None:
    output = render_strategy_workspace(_report(), audience="executive")
    assert "<h3>Performance</h3>" in output
    assert "Realized Gain" in output
    assert "Position / Sales History" in output


def test_strategy_css_includes_position_history_styles() -> None:
    css = strategy_ui_css()
    assert ".position-history-pro" in css
    assert ".position-history-table" in css


def test_performance_gain_and_loss_metrics_are_semantically_colored() -> None:
    output = render_strategy_workspace(_report(), audience="executive")
    assert "metric-positive'>+$12.50" in output
    assert "metric-negative'>-$203.06" in output
