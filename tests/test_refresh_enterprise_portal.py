from __future__ import annotations

from pathlib import Path

import refresh_enterprise_portal as launcher


def _dashboard_summary(tmp_path: Path) -> dict:
    results = tmp_path / "results"
    return {
        "strategy_discovery_summary": {
            "registered_strategy_count": 2,
            "strategy_ids": ["DIVIDEND-001", "SWING-001"],
        },
        "paths": {
            "executive_json": str(results / "ai_cio_executive_dashboard.json"),
            "investor_json": str(results / "enterprise_investor_dashboard.json"),
        },
        "warnings": ["base warning"],
        "errors": [],
    }


def _intelligence_summary(tmp_path: Path) -> dict:
    results = tmp_path / "results"
    return {
        "registered_strategy_count": 2,
        "strategy_ids": ["DIVIDEND-001", "SWING-001"],
        "paths": {
            "enterprise_dashboard_intelligence": str(
                results / "enterprise_dashboard_intelligence.json"
            ),
            "enterprise_strategy_comparison": str(
                results / "enterprise_strategy_comparison.json"
            ),
        },
        "warnings": ["intelligence warning"],
    }


def test_runs_base_refresh_before_intelligence_publication(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, object]] = []

    def fake_refresh(**kwargs):
        calls.append(("refresh", kwargs))
        return _dashboard_summary(tmp_path)

    def fake_publish(**kwargs):
        calls.append(("publish", kwargs))
        return _intelligence_summary(tmp_path)

    monkeypatch.setattr(launcher, "refresh_enterprise_dashboards", fake_refresh)
    monkeypatch.setattr(launcher, "publish_enterprise_dashboard_intelligence", fake_publish)

    summary = launcher.refresh_enterprise_portal(
        root_dir=tmp_path,
        results_dir="results",
        state_dir="state",
    )

    assert [name for name, _ in calls] == ["refresh", "publish"]
    assert calls[1][1]["results_dir"] == tmp_path / "results"
    assert summary["refresh_complete"] is True


def test_returns_one_combined_summary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        launcher,
        "refresh_enterprise_dashboards",
        lambda **kwargs: _dashboard_summary(tmp_path),
    )
    monkeypatch.setattr(
        launcher,
        "publish_enterprise_dashboard_intelligence",
        lambda **kwargs: _intelligence_summary(tmp_path),
    )

    summary = launcher.refresh_enterprise_portal(root_dir=tmp_path)

    assert summary["registered_strategy_count"] == 2
    assert summary["strategy_ids"] == ["DIVIDEND-001", "SWING-001"]
    assert summary["warnings"] == ["base warning", "intelligence warning"]
    assert "executive_json" in summary["paths"]
    assert "intelligence_enterprise_dashboard_intelligence" in summary["paths"]


def test_detects_strategy_identity_drift(monkeypatch, tmp_path: Path) -> None:
    dashboard = _dashboard_summary(tmp_path)
    intelligence = _intelligence_summary(tmp_path)
    intelligence["strategy_ids"] = ["DIVIDEND-001"]
    intelligence["registered_strategy_count"] = 1

    monkeypatch.setattr(
        launcher, "refresh_enterprise_dashboards", lambda **kwargs: dashboard
    )
    monkeypatch.setattr(
        launcher,
        "publish_enterprise_dashboard_intelligence",
        lambda **kwargs: intelligence,
    )

    summary = launcher.refresh_enterprise_portal(root_dir=tmp_path)

    assert summary["refresh_complete"] is False
    assert any("strategy IDs" in error for error in summary["errors"])


def test_preserves_dashboard_errors(monkeypatch, tmp_path: Path) -> None:
    dashboard = _dashboard_summary(tmp_path)
    dashboard["errors"] = ["required dashboard evidence missing"]

    monkeypatch.setattr(
        launcher, "refresh_enterprise_dashboards", lambda **kwargs: dashboard
    )
    monkeypatch.setattr(
        launcher,
        "publish_enterprise_dashboard_intelligence",
        lambda **kwargs: _intelligence_summary(tmp_path),
    )

    summary = launcher.refresh_enterprise_portal(root_dir=tmp_path)

    assert summary["refresh_complete"] is False
    assert summary["errors"] == ["required dashboard evidence missing"]


def test_absolute_results_directory_is_not_rebased(monkeypatch, tmp_path: Path) -> None:
    results = tmp_path / "absolute-results"
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        launcher,
        "refresh_enterprise_dashboards",
        lambda **kwargs: _dashboard_summary(tmp_path),
    )

    def fake_publish(**kwargs):
        captured.update(kwargs)
        return _intelligence_summary(tmp_path)

    monkeypatch.setattr(launcher, "publish_enterprise_dashboard_intelligence", fake_publish)

    launcher.refresh_enterprise_portal(
        root_dir=tmp_path / "root",
        results_dir=results,
    )

    assert captured["results_dir"] == results


def test_safety_metadata_is_locked(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        launcher,
        "refresh_enterprise_dashboards",
        lambda **kwargs: _dashboard_summary(tmp_path),
    )
    monkeypatch.setattr(
        launcher,
        "publish_enterprise_dashboard_intelligence",
        lambda **kwargs: _intelligence_summary(tmp_path),
    )

    summary = launcher.refresh_enterprise_portal(root_dir=tmp_path)

    assert summary["paper_trade_mode"] is True
    assert summary["live_trading_enabled"] is False
    assert summary["broker_execution_enabled"] is False
    assert summary["capital_movement_enabled"] is False
    assert summary["reporting_only"] is True
    assert summary["read_only"] is True
