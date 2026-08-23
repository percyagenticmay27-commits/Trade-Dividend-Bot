from __future__ import annotations

from src.dividend_bot.enterprise_portal_strategy_ui import (
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
                "lifecycle_status": "PRODUCTION",
                "runtime_status": "ONLINE",
                "health_status": "HEALTHY",
                "readiness": "READY",
                "allocated_capital": 5000,
                "portfolio_value": 5200,
                "capability_count": 2,
                "capabilities": ["portfolio", "income"],
                "published_artifact_count": 1,
                "published_artifacts": [
                    {
                        "artifact_id": "dividend-portfolio",
                        "artifact_type": "portfolio",
                        "format": "JSON",
                        "authoritative": True,
                        "required": False,
                    }
                ],
                "evidence_status": "AVAILABLE",
                "evidence_paths": ["results/dividend.json"],
            },
            {
                "strategy_id": "SWING-001",
                "display_name": "Trade Swing Bot",
                "strategy_type": "SWING",
                "lifecycle_status": "PRODUCTION",
                "runtime_status": "ONLINE",
                "health_status": "HEALTHY",
                "readiness": "READY",
                "allocated_capital": 4500,
                "capability_count": 3,
                "capabilities": ["portfolio", "watchlist", "opportunity_quality"],
                "published_artifact_count": 0,
                "published_artifacts": [],
                "evidence_status": "REGISTRY_ONLY",
                "evidence_paths": [],
            },
        ]
    }


def test_workspace_lists_every_registered_strategy_and_registry_details() -> None:
    output = render_strategy_workspace(_report(), audience="executive")

    assert "Dividend Income Strategy" in output
    assert "Trade Swing Bot" in output
    assert "2 capabilities · 1 artifacts" in output
    assert "3 capabilities · 0 artifacts" in output
    assert "Lifecycle:</strong> PRODUCTION" in output
    assert "dividend-portfolio" in output
    assert "authoritative, optional" in output
    assert "opportunity_quality" in output
    assert "REGISTRY_ONLY" in output


def test_workspace_escapes_registry_derived_text() -> None:
    report = _report()
    report["strategy_kpis"][0]["display_name"] = "<script>alert(1)</script>"
    report["strategy_kpis"][0]["capabilities"] = ["<b>portfolio</b>"]

    output = render_strategy_workspace(report, audience="investor")

    assert "<script>alert(1)</script>" not in output
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in output
    assert "<b>portfolio</b>" not in output
    assert "&lt;b&gt;portfolio&lt;/b&gt;" in output


def test_empty_workspace_does_not_fabricate_strategy_data() -> None:
    output = render_strategy_workspace({}, audience="executive")

    assert "No registry-driven strategy KPI evidence is available yet." in output
    assert "Dividend" not in output
    assert "Swing" not in output


def test_dividend_decision_journal_reaches_decisions_tab() -> None:
    report = _report()
    report["strategy_kpis"][0]["decision_journal_status"] = "AVAILABLE"
    report["strategy_kpis"][0]["decision_journal"] = {
        "strategy_id": "DIVIDEND-001",
        "strategy_name": "Dividend Income Strategy",
        "strategy_type": "DIVIDEND",
        "generated_at": "2026-08-11T12:00:00Z",
        "decisions": [{
            "strategy_id": "DIVIDEND-001",
            "decision_id": "AMDW-HOLD",
            "decision_timestamp": "2026-08-11T12:00:00Z",
            "decision_type": "HOLD",
            "status": "MONITOR",
            "ecosystem": {
                "ecosystem_name": "AMDW / AMDL",
                "income_leg": "AMDW",
                "leverage_leg": "AMDL",
            },
            "final_rationale": "The warning is buffered; no owner-specific sell is confirmed.",
            "committee_evidence": [],
            "images": [],
        }],
    }

    output = render_strategy_workspace(report, audience="executive")

    assert "Dividend Income Strategy Decision Journal" in output
    assert "AMDW / AMDL" in output
    assert "The warning is buffered" in output
    assert "Search stock, pair, reason, or decision" in output
    assert "applyJournalFilters" in output
    assert "Pair Lifecycle Overview" in output
    assert "<h3>AMDW / AMDL</h3>" in output
    assert "More evidence" in output
    assert "Open full history" in output
    assert "data-lifecycle-search" in output
    assert "data-lifecycle-filter" in output
    assert "data-lifecycle-prev" in output
    assert "applyLifecycleOverview" in output
    dividend_start = output.index("id='strategy-DIVIDEND-001'")
    swing_start = output.index("id='strategy-SWING-001'")
    dividend_workspace = output[dividend_start:swing_start]
    assert "Decision Journal status: NOT_REPORTED" not in dividend_workspace


def test_decision_journal_filter_controls_have_visible_portal_styles() -> None:
    css = strategy_ui_css()

    assert ".strategy-decision-panel .journal-filters button{" in css
    assert "font-weight:700" in css
    assert "opacity:1" in css
    assert ".strategy-decision-panel .journal-filters button:hover{" in css
    assert ".strategy-decision-panel .journal-filters button:focus-visible{" in css
    assert ".strategy-decision-panel .lifecycle-summary-list{" in css
    assert ".strategy-decision-panel .lifecycle-overview>header h3" in css
    assert ".strategy-decision-panel .lifecycle-overview>header p" in css
    assert "color:#fff!important" in css
    assert ".strategy-decision-panel [data-lifecycle-search]{" in css
    assert ".strategy-decision-panel .lifecycle-stage-badge{" in css
    assert "white-space:normal" in css
    assert "overflow-wrap:anywhere" in css
    assert ".strategy-decision-panel .lifecycle-more{" in css
    assert "width:fit-content" in css
    assert "max-width:100%" in css
    assert ".strategy-decision-panel .lifecycle-pagination{" in css
    assert ".strategy-decision-panel .decision-card header .decision-type{" in css
    assert ".strategy-decision-panel .decision-card header .status{" in css
    assert "color:#5b21b6!important" in css
    assert "color:#334155!important" in css


def test_swing_candidate_pipeline_reaches_strategy_workspace_watchlist_tab() -> None:
    report = _report()
    swing = report["strategy_kpis"][1]
    swing["watchlist_count"] = 3
    swing["watchlist"] = [
        {
            "underlying_symbol": "NBIS",
            "leveraged_symbol": "NEBX",
            "lifecycle_status": "WATCHLIST",
            "capacity_status": "ACTIVE",
            "watchlist_rank": 1,
            "composite_score": 91.2,
            "financial_health": "STRONG",
            "theme": "AI Infrastructure",
            "promotion_eligible": True,
            "source_count": 5,
            "win_rate": 62.5,
            "paper_return": 8.4,
        },
        {
            "underlying_symbol": "IREN",
            "leveraged_symbol": "IREL",
            "lifecycle_status": "DISCOVERY",
            "capacity_status": "ACTIVE",
            "watchlist_rank": 2,
        },
        {
            "underlying_symbol": "BE",
            "leveraged_symbol": None,
            "lifecycle_status": "REMOVED",
            "capacity_status": "REMOVED",
            "watchlist_rank": 3,
        },
    ]

    output = render_strategy_workspace(report, audience="executive")
    swing_start = output.index("id='strategy-SWING-001'")
    swing_workspace = output[swing_start:]

    assert "Candidate Pipeline" in swing_workspace
    assert "Total Candidate Records</span><strong>3" in swing_workspace
    assert "Active Watchlist</span><strong>1" in swing_workspace
    assert "Discovery</span><strong>1" in swing_workspace
    assert "Removed</span><strong>1" in swing_workspace
    assert "NBIS" in swing_workspace and "NEBX" in swing_workspace
    assert "IREN" in swing_workspace and "IREL" in swing_workspace
    assert ">BE<" in swing_workspace
    assert "No active strategy watchlist candidates." not in swing_workspace

def test_swing_holdings_reach_strategy_workspace_without_reconciliation_warning() -> None:
    report = _report()
    swing = report["strategy_kpis"][1]
    swing.update({
        "allocated_capital": 4500.0,
        "portfolio_value": 4525.52,
        "cash_balance": 2700.0,
        "invested_capital": 1800.0,
        "positions_market_value": 1825.52,
        "position_count": 2,
        "unrealized_pnl": 25.52,
        "holdings": [
            {
                "symbol": "SOXL",
                "shares": 8.04145854,
                "entry_price": 139.899993896484,
                "current_price": 143.264297485352,
                "market_value": 1152.05,
                "unrealized_pnl": 27.05,
                "unrealized_pnl_percent": 2.404444,
                "active_strategy": "Strategy A",
            },
            {
                "symbol": "TQQQ",
                "shares": 9.021652,
                "entry_price": 74.819999694824,
                "current_price": 74.650001525879,
                "market_value": 673.47,
                "unrealized_pnl": -1.53,
                "unrealized_pnl_percent": -0.226667,
                "active_strategy": "Strategy A",
            },
        ],
    })

    output = render_strategy_workspace(report, audience="executive")
    swing_start = output.index("id='strategy-SWING-001'")
    swing_workspace = output[swing_start:]

    assert "SOXL" in swing_workspace and "TQQQ" in swing_workspace
    assert "Invested Capital" in swing_workspace
    assert "$1,800.00" in swing_workspace
    assert "$2,700.00" in swing_workspace
    assert "$1,825.52" in swing_workspace
    assert "$4,525.52" in swing_workspace
    assert "+$25.52" in swing_workspace
    assert "does not match reported portfolio value" not in swing_workspace



def test_dividend_workspace_uses_authoritative_strategy_nav_accounting() -> None:
    report = _report()
    dividend = report["strategy_kpis"][0]

    dividend.update({
        "allocated_capital": 5000.0,
        "portfolio_value": 4715.63,
        "strategy_nav": 4715.63,
        "strategy_nav_pnl": -284.37,
        "strategy_nav_return_pct": -5.6874,
        "nav_accounting_method": "CURRENT_STRATEGY_NAV_MINUS_ALLOCATED_CAPITAL",
        "realized_gain": -155.01,
        "unrealized_gain": None,
        "income": 58.47,
    })

    output = render_strategy_workspace(report, audience="executive")

    dividend_start = output.index("id='strategy-DIVIDEND-001'")
    swing_start = output.index("id='strategy-SWING-001'")
    dividend_workspace = output[dividend_start:swing_start]

    assert "Total P/L" in dividend_workspace
    assert "-$284.37" in dividend_workspace
    assert "Total Return" in dividend_workspace
    assert "-5.6874%" in dividend_workspace

    assert "Realized P/L" in dividend_workspace
    assert "-$155.01" in dividend_workspace

    assert "Unrealized P/L" in dividend_workspace
    assert "Not reported" in dividend_workspace

    assert "Realized Gain" not in dividend_workspace
    assert "Unrealized Gain" not in dividend_workspace


def test_dividend_receives_own_strategy_assignments_tab(monkeypatch):
    from src.dividend_bot import enterprise_portal_strategy_ui_v2 as ui

    monkeypatch.setattr(
        ui,
        "render_dividend_strategy_assignments",
        lambda root=".": (
            "<div id='dividend-assignment-test'>"
            "Dividend Strategy Assignments"
            "</div>"
        ),
    )

    report = _report()
    report["strategy_kpis"] = [
        row
        for row in report["strategy_kpis"]
        if row.get("strategy_id") == "DIVIDEND-001"
    ]

    output = ui.render_strategy_workspace(
        report,
        audience="executive",
    )

    assert "tab-DIVIDEND-001-strategy-assignments" in output
    assert "Dividend Strategy Assignments" in output
    assert "dividend-assignment-test" in output


def test_dividend_manual_strategy_tab_uses_dividend_transport_only():
    from src.dividend_bot import enterprise_portal_strategy_ui_v2 as ui

    report = _report()
    report["strategy_kpis"] = [
        row
        for row in report["strategy_kpis"]
        if row.get("strategy_id") == "DIVIDEND-001"
    ]

    output = ui.render_strategy_workspace(
        report,
        audience="executive",
    )

    # Dividend now intentionally owns its own Manual Strategy tab.
    assert "tab-DIVIDEND-001-manual-strategy" in output

    # It must submit only to the Dividend-owned intake route.
    assert "action='/strategy/dividend-manual-entry'" in output

    # Swing-owned write/promotion routes must not appear in Dividend's form.
    assert "action='/strategy/manual-entry'" not in output
    assert "action='/strategy/shadow-promote'" not in output

    # Safety/governance presentation remains explicit.
    assert "PAPER / SHADOW ONLY" in output
    assert "TEST_CANDIDATE" in output
    assert "Automatic Promotion:</strong> DISABLED" in output

