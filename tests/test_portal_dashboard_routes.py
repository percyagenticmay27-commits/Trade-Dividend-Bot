from __future__ import annotations

import io
import json
from pathlib import Path

from src.dividend_bot.paper_capital_allocation_server import create_wsgi_app, render_allocation_page


PLUGIN = {
    "strategy_id": "dividend",
    "display_name": "Dividend Income Strategy",
    "status": "READY",
    "health": "HEALTHY",
    "enabled": True,
    "paper_trade_mode": True,
    "strategy_plugin": True,
}


def _call(app, method: str, path: str, body: bytes = b"") -> tuple[str, str]:
    response: dict[str, str] = {}

    def start_response(status: str, headers) -> None:
        response["status"] = status

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
    }
    payload = b"".join(app(environ, start_response)).decode("utf-8")
    return response["status"], payload


def _app(tmp_path: Path, **overrides):
    registry = tmp_path / "registry.json"
    cash = tmp_path / "cash.json"
    registry.write_text(json.dumps({"strategy_plugins": [PLUGIN]}), encoding="utf-8")
    cash.write_text(json.dumps({"available_cash": 5000, "allocated_cash": 0}), encoding="utf-8")
    kwargs = {
        "registry_path": registry,
        "cash_path": cash,
        "request_log": tmp_path / "requests.jsonl",
        "transaction_log": tmp_path / "cash_transactions.jsonl",
        "approval_log": tmp_path / "approvals.jsonl",
        "allocation_transaction_log": tmp_path / "allocation_transactions.jsonl",
        "executive_dashboard_html": tmp_path / "executive.html",
        "executive_dashboard_json": tmp_path / "executive.json",
        "investor_dashboard_json": tmp_path / "investor.json",
    }
    kwargs.update(overrides)
    return create_wsgi_app(**kwargs), cash, kwargs


def test_navigation_uses_read_only_dashboard_routes() -> None:
    page = render_allocation_page(5000, [PLUGIN])
    assert 'href="/executive-dashboard"' in page
    assert 'href="/investor-dashboard"' in page
    assert "/executive_dashboard.html" not in page
    assert "/investor_dashboard.html" not in page


def test_existing_executive_html_is_served(tmp_path: Path) -> None:
    app, _, paths = _app(tmp_path)
    Path(paths["executive_dashboard_html"]).write_text("<!doctype html><title>Existing Executive</title>", encoding="utf-8")
    status, page = _call(app, "GET", "/executive-dashboard")
    assert status == "200 OK"
    assert "Existing Executive" in page


def test_executive_json_fallback_uses_authoritative_formatter(tmp_path: Path) -> None:
    app, _, paths = _app(tmp_path)
    Path(paths["executive_dashboard_json"]).write_text(
        json.dumps({"portfolio_summary": {"portfolio_value": 1234}, "ai_cio_verdict": {}, "capital_allocation_rankings": []}),
        encoding="utf-8",
    )
    status, page = _call(app, "GET", "/executive-dashboard")
    assert status == "200 OK"
    assert "AI CIO Executive Dashboard" in page
    assert "Portfolio Value" in page


def test_missing_executive_data_returns_styled_200(tmp_path: Path) -> None:
    app, _, _ = _app(tmp_path)
    status, page = _call(app, "GET", "/executive-dashboard")
    assert status == "200 OK"
    assert "Executive Dashboard Unavailable" in page
    assert "has not been generated yet" in page


def test_investor_json_is_rendered_and_escaped(tmp_path: Path) -> None:
    app, _, paths = _app(tmp_path)
    Path(paths["investor_dashboard_json"]).write_text(
        json.dumps({
            "generated_at_utc": "2026-07-31T12:00:00Z",
            "portfolio_health": "STABLE",
            "investor_summary": {"portfolio_value": 5000, "projected_annual_dividend_income": 250},
            "income_reliability": {"consistency_label": "STRONG"},
            "allocation": {"holdings": [{"symbol": "<script>alert(1)</script>", "market_value": 1000, "allocation_percent": 20, "sector": "Tech"}]},
            "upcoming_payments": [{"symbol": "ABC", "date": "2026-08-01"}],
            "risk_flags": [{"code": "WATCH", "message": "Review"}],
            "suggested_actions": [{"action": "Continue monitoring"}],
            "warnings": ["No warning"],
        }),
        encoding="utf-8",
    )
    status, page = _call(app, "GET", "/investor-dashboard")
    assert status == "200 OK"
    assert "Investor Dashboard" in page
    assert "Income Reliability" in page
    assert "Upcoming Payments" in page
    assert "Risk Flags" in page
    assert "Suggested Actions" in page
    assert "2026-07-31T12:00:00Z" in page
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_missing_investor_data_returns_styled_200(tmp_path: Path) -> None:
    app, _, _ = _app(tmp_path)
    status, page = _call(app, "GET", "/investor-dashboard")
    assert status == "200 OK"
    assert "Investor Dashboard Unavailable" in page
    assert "has not been generated yet" in page


def test_malformed_dashboard_json_does_not_crash_service(tmp_path: Path) -> None:
    app, _, paths = _app(tmp_path)
    Path(paths["investor_dashboard_json"]).write_text("{bad json", encoding="utf-8")
    status, page = _call(app, "GET", "/investor-dashboard")
    assert status == "200 OK"
    assert "artifact could not be read" in page


def test_dashboard_routes_are_get_only(tmp_path: Path) -> None:
    app, _, _ = _app(tmp_path)
    status, _ = _call(app, "POST", "/executive-dashboard")
    assert status == "404 Not Found"
    status, _ = _call(app, "POST", "/investor-dashboard")
    assert status == "404 Not Found"


def test_dashboard_reads_do_not_modify_cash_or_logs(tmp_path: Path) -> None:
    app, cash, paths = _app(tmp_path)
    before = cash.read_text(encoding="utf-8")
    _call(app, "GET", "/executive-dashboard")
    _call(app, "GET", "/investor-dashboard")
    assert cash.read_text(encoding="utf-8") == before
    assert not Path(paths["request_log"]).exists()
    assert not Path(paths["approval_log"]).exists()
    assert not Path(paths["allocation_transaction_log"]).exists()
