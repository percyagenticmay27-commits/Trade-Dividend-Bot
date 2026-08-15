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


def test_executive_fallback_has_no_visible_stylesheet_before_portal_frame(tmp_path: Path) -> None:
    app, _, paths = _app(tmp_path)
    Path(paths["executive_dashboard_json"]).write_text(
        json.dumps({"portfolio_summary": {}, "ai_cio_verdict": {}, "capital_allocation_rankings": []}),
        encoding="utf-8",
    )
    status, page = _call(app, "GET", "/executive-dashboard")
    assert status == "200 OK"
    selector_index = page.index(".position-history-pro{")
    opening_style = page.rfind("<style", 0, selector_index)
    prior_closing_style = page.rfind("</style>", 0, selector_index)
    closing_style = page.index("</style>", selector_index)
    portal_frame = page.index("<div class='portal-frame'>")
    assert opening_style > prior_closing_style
    assert selector_index < closing_style < portal_frame


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


def test_strategy_review_route_loads_owner_alerts_and_pair_history(tmp_path: Path) -> None:
    assignments = tmp_path / "assignments.json"
    performance = tmp_path / "performance.json"
    requests = tmp_path / "promotion_requests.json"
    journal = tmp_path / "promotion_journal.jsonl"
    paper_state = tmp_path / "paper_state.json"
    assignments.write_text(json.dumps({
        "assignments": {
            "AMDW / AMDL": {
                "primary_strategy": "STRATEGY_B",
                "previous_primary_strategy": "STRATEGY_A",
                "assignment_source": "PROMOTED_AFTER_OWNER_REVIEW",
                "effective_at_utc": "2026-08-11T18:08:00Z",
                "promotion_request_id": "PROMOTE-AMDW-001",
            }
        }
    }), encoding="utf-8")
    performance.write_text(json.dumps({
        "as_of_date": "2026-08-11",
        "performance": [],
    }), encoding="utf-8")
    requests.write_text(json.dumps({"requests": []}), encoding="utf-8")
    journal.write_text(json.dumps({
        "event_type": "STRATEGY_PROMOTION_ACTIVATED",
        "pair": "AMDW / AMDL",
        "previous_primary_strategy": "STRATEGY_A",
        "new_primary_strategy": "STRATEGY_B",
        "recorded_at_utc": "2026-08-11T18:08:00Z",
    }) + "\n", encoding="utf-8")
    paper_state.write_text(json.dumps({
        "pairs": {
            "AMDW / AMDL": {
                "strategy_owner": "STRATEGY_A",
                "a_in_sgov": False,
                "b_in_sgov": False,
            }
        }
    }), encoding="utf-8")
    app, cash, paths = _app(
        tmp_path,
        strategy_assignments_path=assignments,
        strategy_performance_path=performance,
        promotion_requests_path=requests,
        promotion_journal_path=journal,
        paper_state_path=paper_state,
    )
    before = cash.read_text(encoding="utf-8")

    status, page = _call(app, "GET", "/strategy-review")

    assert status == "200 OK"
    assert "Owner Alerts and Next Steps" in page
    assert "Pair Strategy History" in page
    assert "Original Entry Strategy" in page
    assert "Current Management Strategy" in page
    assert "STRATEGY_A" in page
    assert "STRATEGY_B" in page
    assert "Promotion Activated" in page
    assert cash.read_text(encoding="utf-8") == before
    assert not Path(paths["request_log"]).exists()


def test_executive_route_renders_swing_trade_analytics_workspace(tmp_path: Path) -> None:
    app, _, paths = _app(tmp_path)
    Path(paths["executive_dashboard_json"]).write_text(json.dumps({
        "portfolio_summary": {"portfolio_value": 9500.0},
        "ai_cio_verdict": {},
        "capital_allocation_rankings": [],
        "strategy_kpis": [{
            "strategy_id": "SWING-001",
            "display_name": "Trade Swing Bot",
            "strategy_type": "SWING",
            "allocated_capital": 4500.0,
            "paper_trade_mode": True,
            "capabilities": ["trade_analytics"],
            "published_artifacts": [],
            "evidence_status": "AVAILABLE",
            "trade_analytics": {
                "max_drawdown_policy": "AUTHORITATIVE_POSITION_HISTORY_ONLY",
                "max_drawdown_inference_allowed": False,
                "open_positions": [{
                    "symbol": "SOXL",
                    "entry_date": "2026-08-04",
                    "entry_price": 139.899993896484,
                    "current_price": 143.264297485352,
                    "gain_loss_amount": 27.05,
                    "gain_loss_percent": 2.404444,
                    "max_drawdown_amount": 82.42,
                    "max_drawdown_percent": 7.308378,
                    "position_status": "OPEN",
                }],
                "closed_positions": [],
            },
        }],
    }), encoding="utf-8")

    status, page = _call(
        app,
        "GET",
        "/executive-dashboard",
    )

    assert status == "200 OK"
    assert "Trade Analytics / Position Performance" in page
    assert ">Trade Analytics</button>" in page
    assert "SOXL" in page
    assert "$82.42" in page
    assert "PAPER ONLY" in page


def test_executive_route_renders_authoritative_swing_alerts_workspace(tmp_path: Path) -> None:
    app, _, paths = _app(tmp_path)
    Path(paths["executive_dashboard_json"]).write_text(json.dumps({
        "portfolio_summary": {"portfolio_value": 9500.0},
        "ai_cio_verdict": {},
        "capital_allocation_rankings": [],
        "strategy_kpis": [{
            "strategy_id": "SWING-001",
            "display_name": "Trade Swing Bot",
            "strategy_type": "SWING",
            "allocated_capital": 4500.0,
            "paper_trade_mode": True,
            "advisory_only": True,
            "capabilities": ["alerts"],
            "published_artifacts": [],
            "evidence_status": "AVAILABLE",
            "risk_flags": ["Exit review attention required"],
            "alerts_status": "AVAILABLE",
            "alerts": [],
            "alerts_report": {
                "strategy_id": "SWING-001",
                "paper_trade_mode": True,
                "advisory_only": True,
                "alert_authority_policy": "CURRENT_AUTHORITATIVE_EVIDENCE_ONLY",
                "actionable_alert_count": 0,
                "alerts": [],
                "evidence_warnings": [
                    "KPI disclosure: Win rate is unavailable until authentic closed trades exist.",
                    "Legacy dashboard excluded because its timestamp is unavailable.",
                ],
                "evaluation_status": "COMPLETE_WITH_EVIDENCE_WARNINGS",
            },
        }],
    }), encoding="utf-8")

    status, page = _call(app, "GET", "/executive-dashboard")

    assert status == "200 OK"
    assert "CURRENT_AUTHORITATIVE_EVIDENCE_ONLY" in page
    assert "Current authoritative Swing evidence was evaluated and no actionable alerts were found." in page
    assert "Evidence Disclosures" in page
    assert "Win rate is unavailable" in page
    assert "Legacy dashboard excluded" in page
    assert "Exit review attention required" not in page
    assert "$4,500.00 allocated" in page
    assert "PAPER ONLY" in page
    assert "ADVISORY ONLY" in page
