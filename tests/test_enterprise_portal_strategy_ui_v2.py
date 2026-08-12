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
    assert ".strategy-decision-panel [data-lifecycle-search]{" in css
    assert ".strategy-decision-panel .lifecycle-stage-badge{" in css
    assert "white-space:normal" in css
    assert "overflow-wrap:anywhere" in css
    assert ".strategy-decision-panel .lifecycle-more{" in css
    assert "width:auto" in css
    assert "height:auto" in css
    assert ".strategy-decision-panel .lifecycle-pagination{" in css
