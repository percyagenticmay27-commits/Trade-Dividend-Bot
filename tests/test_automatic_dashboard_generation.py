"""Focused tests for automatic Enterprise dashboard publication."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "start_dividend_bot.sh"


def _launcher_text() -> str:
    return LAUNCHER.read_text(encoding="utf-8")


def test_daily_launcher_runs_dashboard_refresh() -> None:
    text = _launcher_text()
    assert "python3 refresh_enterprise_dashboards.py" in text


def test_daily_launcher_refreshes_dividend_performance() -> None:
    text = _launcher_text()
    assert "python3 refresh_dividend_paper_trade_performance.py" in text


def test_daily_cycle_and_realized_performance_run_before_dashboard_refresh() -> None:
    text = _launcher_text()
    daily = text.index("python3 run_daily_paper_cycle.py")
    realized = text.index("python3 refresh_dividend_paper_trade_performance.py")
    dashboards = text.index("python3 refresh_enterprise_dashboards.py")
    assert daily < realized < dashboards


def test_launcher_remains_fail_fast() -> None:
    text = _launcher_text()
    assert "set -eu" in text


def test_launcher_preserves_paper_environment_default() -> None:
    text = _launcher_text()
    assert 'DIVIDEND_BOT_ENV="${DIVIDEND_BOT_ENV:-paper}"' in text


def test_dashboard_refresh_does_not_replace_daily_cycle() -> None:
    text = _launcher_text()
    assert text.count("python3 run_daily_paper_cycle.py") == 1
    assert text.count("python3 refresh_dividend_paper_trade_performance.py") == 1
    assert text.count("python3 refresh_enterprise_dashboards.py") == 1
