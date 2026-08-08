from src.dividend_bot.enterprise_position_history_ui import (
    position_history_ui_css,
    render_position_history_panel,
)


def _row():
    return {
        "performance_detail": {
            "position_lifecycle": [
                {
                    "symbol": "AMDW",
                    "pair": "AMDW / AMDL",
                    "sleeve": "A",
                    "lifecycle_status": "OPEN",
                    "first_purchase_date": "2026-06-18",
                    "last_exit_date": None,
                    "last_exit_action": None,
                    "reentry_count": 0,
                    "evidence_source": "paper_trade_log.csv",
                },
                {
                    "symbol": "PLTW",
                    "pair": "PLTW / PLTU",
                    "sleeve": "A",
                    "lifecycle_status": "PARKED_IN_SGOV",
                    "first_purchase_date": "2026-06-18",
                    "last_exit_date": "2026-06-18",
                    "last_exit_action": "PAPER_PARK_IN_SGOV",
                    "entry_value": 26.0,
                    "last_exit_value": 28.0,
                    "realized_gain_loss": 2.0,
                    "reentry_count": 0,
                    "evidence_source": "paper_trade_log.csv",
                },
                {
                    "symbol": "AVGW",
                    "pair": "AVGW / AVGX",
                    "sleeve": "A",
                    "lifecycle_status": "PARKED_IN_SGOV",
                    "first_purchase_date": "2026-06-18",
                    "last_exit_date": "2026-06-26",
                    "last_exit_action": "PAPER_SELL_TO_SGOV",
                    "entry_value": 36.98,
                    "last_exit_value": 35.89,
                    "realized_gain_loss": -1.09,
                    "reentry_count": 0,
                    "evidence_source": "paper_trade_log.csv",
                },
                {
                    "symbol": "SGOV",
                    "lifecycle_status": "RESERVE",
                    "evidence_source": "paper_state.json",
                },
            ]
        }
    }


def test_position_history_renderer_keeps_current_and_reserve_out_of_sales_history() -> None:
    output = render_position_history_panel(_row())
    assert "Position / Sales History" in output
    assert "PLTW" in output
    assert "AVGW" in output
    assert "AMDW" not in output
    assert ">SGOV<" not in output


def test_position_history_renderer_shows_entry_exit_and_gain_loss() -> None:
    output = render_position_history_panel(_row())
    assert "Entry Value" in output
    assert "Exit Value" in output
    assert "Gain / Loss" in output
    assert "$26.00" in output
    assert "$28.00" in output
    assert "+$2.00" in output
    assert "$36.98" in output
    assert "$35.89" in output
    assert "-$1.09" in output
    assert "position-history-pnl positive" in output
    assert "position-history-pnl negative" in output


def test_position_history_renderer_shows_exit_evidence_and_summary() -> None:
    output = render_position_history_panel(_row())
    assert "PAPER_PARK_IN_SGOV" in output
    assert "PAPER_SELL_TO_SGOV" in output
    assert "paper_trade_log.csv" in output
    assert "Reported Realized P&amp;L" in output
    assert "+$0.91" in output


def test_position_history_renderer_does_not_mix_distribution_history() -> None:
    output = render_position_history_panel(_row())
    assert "Distribution History" not in output
    assert "dividend" in output.lower()


def test_position_history_renderer_does_not_fabricate_missing_pnl() -> None:
    output = render_position_history_panel(
        {
            "performance_detail": {
                "position_lifecycle": [
                    {
                        "symbol": "TEST",
                        "lifecycle_status": "CLOSED",
                        "entry_value": None,
                        "last_exit_value": None,
                        "realized_gain_loss": None,
                    }
                ]
            }
        }
    )
    assert "Not reported" in output
    assert "Reported Realized P&amp;L</span><strong class='position-history-pnl neutral'>Not reported" in output


def test_position_history_renderer_has_explicit_empty_state() -> None:
    output = render_position_history_panel({"performance_detail": {"position_lifecycle": []}})
    assert "No strategy-owned position exits are currently reported." in output


def test_position_history_css_is_professional_responsive_and_scrollable() -> None:
    css = position_history_ui_css()
    assert "overflow-x:auto" in css
    assert "position:sticky" in css
    assert "nth-child(even)" in css
    assert "position-history-pnl.positive" in css
    assert "position-history-pnl.negative" in css
    assert "@media" in css
