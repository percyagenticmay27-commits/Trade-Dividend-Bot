from __future__ import annotations

from src.dividend_bot.enterprise_portal_strategy_ui import render_strategy_workspace


TAB_IDS = (
    "executive-summary",
    "portfolio",
    "watchlist",
    "holdings",
    "income",
    "performance",
    "alerts",
    "decisions",
)


def _row(strategy_id: str) -> dict:
    return {
        "strategy_id": strategy_id,
        "display_name": f"{strategy_id} Strategy",
        "allocated_capital": 5000,
        "portfolio_value": 5250,
        "realized_gain": 100,
        "unrealized_gain": 150,
        "income": 250,
        "position_count": 4,
        "watchlist_count": 12,
        "opportunity_quality": 88,
        "win_rate_percent": 62.5,
        "health_status": "HEALTHY",
        "evidence_status": "AVAILABLE",
        "watchlist": [{"symbol": "AMD", "score": 91}],
        "holdings": [{"symbol": "NVDA", "market_value": 1000}],
        "income_events": [{"symbol": "NVDY", "amount": 75}],
        "alerts": [{"alert_type": "EARNINGS_REVIEW", "severity": "WARNING"}],
        "decision_journal": None,
        "decision_journal_status": "NOT_REPORTED",
    }


def test_workspace_publishes_all_eight_approved_tabs() -> None:
    value = render_strategy_workspace(
        {"strategy_kpis": [_row("DIVIDEND-001")]},
        audience="executive",
    )

    for tab_id in TAB_IDS:
        assert f"data-workspace-tab-target='{tab_id}'" in value
        assert f"data-workspace-tab-panel='{tab_id}'" in value


def test_executive_summary_is_default_active_tab() -> None:
    value = render_strategy_workspace(
        {"strategy_kpis": [_row("DIVIDEND-001")]},
        audience="executive",
    )

    assert (
        "class='workspace-tab active' "
        "data-workspace-strategy='DIVIDEND-001' "
        "data-workspace-tab-target='executive-summary'"
    ) in value
    assert (
        "data-workspace-strategy-panel='DIVIDEND-001' "
        "data-workspace-tab-panel='executive-summary'"
    ) in value


def test_non_default_panels_are_initially_hidden() -> None:
    value = render_strategy_workspace(
        {"strategy_kpis": [_row("SWING-001")]},
        audience="executive",
    )

    assert (
        "<section class='workspace-tab-panel' hidden "
        "data-workspace-strategy-panel='SWING-001' "
        "data-workspace-tab-panel='decisions'"
    ) in value


def test_strategy_tabs_are_scoped_by_strategy_id() -> None:
    value = render_strategy_workspace(
        {
            "strategy_kpis": [
                _row("DIVIDEND-001"),
                _row("SWING-001"),
            ]
        },
        audience="executive",
    )

    for strategy_id in ("DIVIDEND-001", "SWING-001"):
        assert value.count(f"data-workspace-strategy='{strategy_id}'") == 8
        assert value.count(f"data-workspace-strategy-panel='{strategy_id}'") == 8


def test_domain_specific_rows_render_only_in_selected_tab_content() -> None:
    value = render_strategy_workspace(
        {"strategy_kpis": [_row("SWING-001")]},
        audience="executive",
    )

    assert "AMD: Score: 91" in value
    assert "NVDA: Market Value: 1000" in value
    assert "NVDY: Amount: 75" in value
    assert "EARNINGS_REVIEW: Alert Type: EARNINGS_REVIEW, Severity: WARNING" in value


def test_missing_domain_detail_uses_explicit_empty_states() -> None:
    row = _row("SWING-001")
    row.pop("watchlist")
    row.pop("holdings")
    row.pop("income_events")
    row.pop("alerts")

    value = render_strategy_workspace(
        {"strategy_kpis": [row]},
        audience="executive",
    )

    assert "No strategy-owned watchlist detail is currently reported." in value
    assert "No strategy-owned holdings detail is currently reported." in value
    assert "No strategy-owned income events are currently reported." in value
    assert "No strategy-owned alerts are currently reported." in value
