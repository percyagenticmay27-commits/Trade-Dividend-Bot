from __future__ import annotations

from src.dividend_bot.enterprise_trade_analytics_ui import (
    render_trade_analytics_panel,
    trade_analytics_ui_css,
)


def _swing_row() -> dict:
    return {
        "strategy_id": "SWING-001",
        "allocated_capital": 4500.0,
        "paper_trade_mode": True,
        "trade_analytics_status": "AVAILABLE",
        "trade_analytics": {
            "strategy_id": "SWING-001",
            "generated_at": "2026-08-15T01:00:00Z",
            "max_drawdown_policy": "AUTHORITATIVE_POSITION_HISTORY_ONLY",
            "max_drawdown_inference_allowed": False,
            "open_position_count": 2,
            "closed_position_count": 0,
            "open_positions": [
                {
                    "symbol": "SOXL",
                    "entry_date": "2026-08-04",
                    "entry_price": 139.899993896484,
                    "current_price": 143.264297485352,
                    "shares": 8.04145854,
                    "cost_basis": 1125.0,
                    "current_or_exit_value": 1152.05,
                    "gain_loss_amount": 27.05,
                    "gain_loss_percent": 2.404444,
                    "max_drawdown_amount": 82.42,
                    "max_drawdown_percent": 7.308378,
                    "days_held": 11,
                    "active_strategy": "Strategy A",
                    "position_status": "OPEN",
                },
                {
                    "symbol": "TQQQ",
                    "entry_date": "2026-08-04",
                    "entry_price": 74.819999694824,
                    "current_price": 74.650001525879,
                    "shares": 9.021652,
                    "cost_basis": 675.0,
                    "current_or_exit_value": 673.47,
                    "gain_loss_amount": -1.53,
                    "gain_loss_percent": -0.226667,
                    "max_drawdown_amount": 25.17,
                    "max_drawdown_percent": 3.728951,
                    "days_held": 11,
                    "active_strategy": "Strategy A",
                    "position_status": "OPEN",
                },
            ],
            "closed_positions": [],
        },
    }


def test_renders_authoritative_open_swing_position_performance() -> None:
    output = render_trade_analytics_panel(_swing_row())

    assert "Trade Analytics / Position Performance" in output
    assert "AUTHORITATIVE_POSITION_HISTORY_ONLY" in output
    assert "Inference Allowed" in output
    assert ">No<" in output
    assert "SOXL" in output
    assert "TQQQ" in output
    assert "2026-08-04" in output
    assert "$143.26" in output
    assert "$74.65" in output
    assert "+$27.05" in output
    assert "-$1.53" in output
    assert "$82.42" in output
    assert "7.31%" in output
    assert "$25.17" in output
    assert "3.73%" in output
    assert "Strategy A" in output
    assert "trade-gain" in output
    assert "trade-loss" in output


def test_open_positions_do_not_render_exit_columns_or_fabricated_closures() -> None:
    output = render_trade_analytics_panel(_swing_row())

    assert "No authentic closed positions are reported" in output
    assert "Exit/Sale Price" not in output
    assert "Final Proceeds" not in output
    assert "Exit Reason" not in output


def test_closed_columns_appear_only_with_authentic_closed_evidence() -> None:
    row = _swing_row()
    row["trade_analytics"]["closed_positions"] = [{
        "symbol": "FAS",
        "entry_date": "2026-07-01",
        "exit_date": "2026-07-10",
        "entry_price": 100.0,
        "exit_price": 110.0,
        "shares": 2.0,
        "cost_basis": 200.0,
        "current_or_exit_value": 220.0,
        "gain_loss_amount": 20.0,
        "gain_loss_percent": 10.0,
        "max_drawdown_amount": 8.0,
        "max_drawdown_percent": 4.0,
        "days_held": 9,
        "active_strategy": "Strategy A",
        "exit_reason": "Confirmed exit",
        "position_status": "CLOSED",
    }]

    output = render_trade_analytics_panel(row)

    assert "Exit/Sale Price" in output
    assert "Final Proceeds" in output
    assert "Exit Reason" in output
    assert "Confirmed exit" in output
    assert "$220.00" in output


def test_missing_optional_evidence_is_unavailable_and_not_inferred() -> None:
    row = _swing_row()
    row["trade_analytics"]["open_positions"][0]["max_drawdown_amount"] = None
    row["trade_analytics"]["open_positions"][0]["max_drawdown_percent"] = None
    output = render_trade_analytics_panel(row)

    assert "Unavailable" in output
    assert "no host-side drawdown calculation" in output


def test_renderer_escapes_strategy_owned_text_and_preserves_paper_safety() -> None:
    row = _swing_row()
    row["trade_analytics"]["open_positions"][0]["symbol"] = "<script>alert(1)</script>"
    output = render_trade_analytics_panel(row)

    assert "<script>alert(1)</script>" not in output
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in output
    assert "PAPER ONLY" in output
    assert "READ ONLY" in output


def test_non_swing_strategy_does_not_receive_swing_analytics() -> None:
    output = render_trade_analytics_panel({
        "strategy_id": "DIVIDEND-001",
        "trade_analytics": _swing_row()["trade_analytics"],
    })

    assert "Not applicable to this strategy" in output
    assert "SOXL" not in output


def test_trade_analytics_css_defines_gain_and_loss_colors() -> None:
    css = trade_analytics_ui_css()

    assert ".trade-gain{color:#087443" in css
    assert ".trade-loss{color:#b42318" in css
