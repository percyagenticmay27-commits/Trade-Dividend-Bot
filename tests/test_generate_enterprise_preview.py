from __future__ import annotations

import json
from pathlib import Path

from generate_enterprise_preview import generate_enterprise_preview


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_generates_standalone_preview_and_status(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    intelligence = {"registered_strategy_count": 2, "strategy_ids": ["DIVIDEND-001", "SWING-001"]}
    _write(results / "ai_cio_executive_dashboard.json", {"enterprise_dashboard_intelligence": intelligence, "strategy_kpis": []})
    _write(results / "enterprise_investor_dashboard.json", {"enterprise_dashboard_intelligence": intelligence, "strategy_kpis": []})

    status = generate_enterprise_preview(results_dir=results)

    html = (results / "enterprise-preview.html").read_text(encoding="utf-8")
    published = json.loads((results / "enterprise-preview-status.json").read_text(encoding="utf-8"))
    assert status["preview_ready"] is True
    assert status["strategy_ids"] == ["DIVIDEND-001", "SWING-001"]
    assert published == status
    assert "STAGING PREVIEW" in html
    assert "Executive Dashboard" in html
    assert "Investor Dashboard" in html
    assert "NOT THE LIVE ALLOCATION PAGE" in html


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
