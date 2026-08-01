from __future__ import annotations

import json
from pathlib import Path

from generate_enterprise_preview import generate_enterprise_preview


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _dashboard(intelligence: dict) -> dict:
    return {
        "enterprise_dashboard_intelligence": intelligence,
        "investor_summary": {
            "portfolio_value": 12000,
            "capital_appreciation": 500,
            "projected_annual_dividend_income": 600,
        },
        "portfolio_health": "HEALTHY",
        "strategy_kpis": [
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Income Strategy",
                "allocated_capital": 7000,
                "portfolio_value": 7400,
                "income": 600,
                "realized_gain": 100,
                "unrealized_gain": 300,
                "health_status": "HEALTHY",
                "runtime_status": "RUNNING",
                "evidence_status": "AVAILABLE",
                "watchlist_count": 12,
                "position_count": 5,
            },
            {
                "strategy_id": "SWING-001",
                "display_name": "Swing Strategy",
                "allocated_capital": 5000,
                "portfolio_value": 4600,
                "income": 0,
                "realized_gain": -200,
                "unrealized_gain": -100,
                "health_status": "WARNING",
                "runtime_status": "RUNNING",
                "evidence_status": "PARTIAL",
                "watchlist_count": 20,
                "position_count": 3,
            },
        ],
    }


def test_generates_standalone_preview_and_status(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    intelligence = {"registered_strategy_count": 2, "strategy_ids": ["DIVIDEND-001", "SWING-001"]}
    _write(results / "ai_cio_executive_dashboard.json", _dashboard(intelligence))
    _write(results / "enterprise_investor_dashboard.json", _dashboard(intelligence))

    status = generate_enterprise_preview(results_dir=results)

    html = (results / "enterprise-preview.html").read_text(encoding="utf-8")
    published = json.loads((results / "enterprise-preview-status.json").read_text(encoding="utf-8"))
    assert status["preview_ready"] is True
    assert status["layout"] == "SCAN_FIRST"
    assert status["strategy_ids"] == ["DIVIDEND-001", "SWING-001"]
    assert published == status
    assert "STAGING PREVIEW" in html
    assert "Executive Summary" in html
    assert "Investor Summary" in html
    assert "Profit / Loss" in html
    assert "Action Needed" in html
    assert "Where should I look?" in html
    assert "Strategy KPI workspace" in html
    assert "Technical evidence paths" in html
    assert "NOT THE LIVE ALLOCATION PAGE" in html


def test_strategy_with_highest_concern_is_visible_first(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    intelligence = {"registered_strategy_count": 2, "strategy_ids": ["DIVIDEND-001", "SWING-001"]}
    dashboard = _dashboard(intelligence)
    _write(results / "ai_cio_executive_dashboard.json", dashboard)
    _write(results / "enterprise_investor_dashboard.json", dashboard)

    generate_enterprise_preview(results_dir=results)
    html = (results / "enterprise-preview.html").read_text(encoding="utf-8")

    assert "Highest concern" in html
    assert "Swing Strategy" in html
    assert "negative reported P&amp;L" in html or "negative reported P&L" in html


def test_missing_required_dashboard_fails(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    _write(results / "ai_cio_executive_dashboard.json", {})
    try:
        generate_enterprise_preview(results_dir=results)
    except FileNotFoundError as exc:
        assert "enterprise_investor_dashboard.json" in str(exc)
    else:
        raise AssertionError("expected missing investor dashboard to fail")


def test_preview_safety_metadata_is_locked(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    _write(results / "ai_cio_executive_dashboard.json", {})
    _write(results / "enterprise_investor_dashboard.json", {})
    status = generate_enterprise_preview(results_dir=results)
    assert status["paper_trade_mode"] is True
    assert status["live_trading_enabled"] is False
    assert status["broker_execution_enabled"] is False
    assert status["capital_movement_enabled"] is False
    assert status["reporting_only"] is True
    assert status["read_only"] is True


def test_recommended_route_is_separate_preview(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    _write(results / "ai_cio_executive_dashboard.json", {})
    _write(results / "enterprise_investor_dashboard.json", {})
    status = generate_enterprise_preview(results_dir=results)
    assert status["recommended_route"] == "/enterprise-preview"
