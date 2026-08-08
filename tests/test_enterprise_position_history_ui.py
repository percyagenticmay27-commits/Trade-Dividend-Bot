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
                    "last_exit_value": 28.0,
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
                    "last_exit_value": 35.89,
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


def test_position_history_renderer_shows_exit_evidence_and_value() -> None:
    output = render_position_history_panel(_row())
    assert "PAPER_PARK_IN_SGOV" in output
    assert "PAPER_SELL_TO_SGOV" in output
    assert "$28.00" in output
    assert "$35.89" in output
    assert "paper_trade_log.csv" in output


def test_position_history_renderer_does_not_mix_distribution_history() -> None:
    output = render_position_history_panel(_row())
    assert "Distribution History" not in output
    assert "dividend" in output.lower()


def test_position_history_renderer_has_explicit_empty_state() -> None:
    output = render_position_history_panel({"performance_detail": {"position_lifecycle": []}})
    assert "No strategy-owned position exits are currently reported." in output


def test_position_history_css_is_responsive_and_scrollable() -> None:
    css = position_history_ui_css()
    assert "overflow-x:auto" in css
    assert "@media" in css
    assert "position-history-table" in css
