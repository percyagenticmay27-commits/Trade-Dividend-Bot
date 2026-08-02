from __future__ import annotations

from src.dividend_bot.enterprise_portal_strategy_ui import render_strategy_workspace
from src.dividend_bot.strategy_decision_journal_renderer import (
    render_strategy_decision_journal,
    render_strategy_decision_journal_document,
)


def _row(strategy_id: str) -> dict:
    return {
        "strategy_id": strategy_id,
        "display_name": f"{strategy_id} Strategy",
        "allocated_capital": 1000,
        "decision_journal": None,
        "decision_journal_status": "NOT_REPORTED",
    }


def _journal(strategy_id: str) -> dict:
    return {
        "strategy_id": strategy_id,
        "strategy_name": f"{strategy_id} Strategy",
        "strategy_kind": "SWING",
        "decisions": [],
    }


def test_workspace_links_to_executive_and_investor_dashboards() -> None:
    value = render_strategy_workspace(
        {"strategy_kpis": [_row("SWING-001")]},
        audience="executive",
    )

    assert "/executive-dashboard?strategy=SWING-001#strategy-SWING-001" in value
    assert "/investor-dashboard?strategy=SWING-001#strategy-SWING-001" in value


def test_workspace_links_directly_to_decisions_tab() -> None:
    value = render_strategy_workspace(
        {"strategy_kpis": [_row("DIVIDEND-001")]},
        audience="executive",
    )

    assert (
        "?strategy=DIVIDEND-001&amp;tab=decisions"
        "#strategy-DIVIDEND-001"
    ) in value


def test_strategy_workspace_has_stable_link_target() -> None:
    value = render_strategy_workspace(
        {"strategy_kpis": [_row("DIVIDEND-001")]},
        audience="investor",
    )

    assert "id='strategy-DIVIDEND-001'" in value
    assert "data-strategy-panel='DIVIDEND-001'" in value


def test_url_state_restores_requested_strategy_and_tab() -> None:
    value = render_strategy_workspace(
        {
            "strategy_kpis": [
                _row("DIVIDEND-001"),
                _row("SWING-001"),
            ]
        },
        audience="executive",
    )

    assert "new URLSearchParams(window.location.search)" in value
    assert "params.get('strategy')" in value
    assert "params.get('tab')||'executive-summary'" in value
    assert "selectTab(requestedStrategy,requestedTab)" in value


def test_each_strategy_receives_only_its_own_cross_links() -> None:
    value = render_strategy_workspace(
        {
            "strategy_kpis": [
                _row("DIVIDEND-001"),
                _row("SWING-001"),
            ]
        },
        audience="executive",
    )

    assert value.count("?strategy=DIVIDEND-001") == 4
    assert value.count("?strategy=SWING-001") == 4


def test_journal_links_back_to_strategy_scoped_portal_views() -> None:
    value = render_strategy_decision_journal(_journal("SWING-001"))

    assert "/executive-dashboard?strategy=SWING-001#strategy-SWING-001" in value
    assert "/investor-dashboard?strategy=SWING-001#strategy-SWING-001" in value
    assert (
        "/executive-dashboard?strategy=SWING-001&amp;tab=decisions"
        "#strategy-SWING-001"
    ) in value


def test_journal_marks_decision_link_as_current_page() -> None:
    value = render_strategy_decision_journal(_journal("DIVIDEND-001"))

    assert 'aria-current="page"' in value
    assert "Decision Journal</a>" in value


def test_standalone_journal_contains_cross_link_styles_without_script() -> None:
    value = render_strategy_decision_journal_document(_journal("SWING-001"))

    assert ".journal-cross-links" in value
    assert "<script>" not in value
