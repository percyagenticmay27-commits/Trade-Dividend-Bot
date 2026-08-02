from __future__ import annotations

from src.dividend_bot.enterprise_portal_strategy_ui import (
    render_left_navigation,
    render_strategy_workspace,
    strategy_ui_css,
)


def _report() -> dict:
    return {
        "strategy_kpis": [
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Income Strategy",
                "allocated_capital": 5000,
                "decision_journal": None,
                "decision_journal_status": "NOT_REPORTED",
            },
            {
                "strategy_id": "SWING-001",
                "display_name": "Swing Trading Strategy",
                "allocated_capital": 4500,
                "decision_journal": None,
                "decision_journal_status": "NOT_REPORTED",
            },
        ]
    }


def test_active_page_link_uses_aria_current() -> None:
    value = render_left_navigation("Executive Dashboard")

    assert "class='side-link active'" in value
    assert "aria-current='page'" in value
    assert "aria-label='Enterprise navigation'" in value


def test_workspace_tabs_publish_accessible_roles_and_state() -> None:
    value = render_strategy_workspace(_report(), audience="executive")

    assert "role='tablist'" in value
    assert "role='tab'" in value
    assert "role='tabpanel'" in value
    assert "aria-selected='true'" in value
    assert "aria-selected='false'" in value


def test_tabs_connect_controls_to_panels() -> None:
    value = render_strategy_workspace(_report(), audience="executive")

    assert "aria-controls='panel-DIVIDEND-001-executive-summary'" in value
    assert "id='panel-DIVIDEND-001-executive-summary'" in value
    assert "aria-labelledby='tab-DIVIDEND-001-executive-summary'" in value


def test_strategy_cards_publish_pressed_state_and_controls() -> None:
    value = render_strategy_workspace(_report(), audience="executive")

    assert "aria-controls='strategy-DIVIDEND-001'" in value
    assert "aria-pressed='true'" in value
    assert "aria-controls='strategy-SWING-001'" in value
    assert "aria-pressed='false'" in value


def test_keyboard_navigation_supports_arrows_home_and_end() -> None:
    value = render_strategy_workspace(_report(), audience="executive")

    assert "event.key==='ArrowRight'" in value
    assert "event.key==='ArrowLeft'" in value
    assert "event.key==='Home'" in value
    assert "event.key==='End'" in value
    assert "tabs[next].focus()" in value


def test_selection_updates_accessibility_and_url_state() -> None:
    value = render_strategy_workspace(_report(), audience="executive")

    assert "setAttribute('aria-selected',active?'true':'false')" in value
    assert "setAttribute('aria-pressed',active?'true':'false')" in value
    assert "window.history.replaceState" in value
    assert "url.searchParams.set('strategy',strategy)" in value
    assert "url.searchParams.set('tab',tab)" in value


def test_dynamic_sidebar_strategies_receive_active_state_metadata() -> None:
    value = render_strategy_workspace(_report(), audience="executive")

    assert "a.dataset.strategyTarget=c.dataset.strategyTarget" in value
    assert "a.setAttribute('aria-controls','strategy-'+c.dataset.strategyTarget)" in value
    assert "side-strategy[data-strategy-target]" in value


def test_responsive_css_covers_tablet_and_mobile_navigation() -> None:
    value = strategy_ui_css()

    assert "@media(max-width:900px)" in value
    assert "@media(max-width:520px)" in value
    assert ".primary-navigation,.registered-strategy-links" in value
    assert "scroll-snap-type:x proximity" in value
    assert ":focus-visible" in value
