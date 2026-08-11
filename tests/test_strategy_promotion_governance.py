from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.parse import urlencode

import pytest

from src.dividend_bot.paper_capital_allocation_server import create_wsgi_app
from src.dividend_bot.strategy_promotion_governance import (
    issue_veto_token,
    load_promotion_requests,
    load_promotion_journal,
    verify_veto_token,
    veto_promotion_request,
    render_strategy_review_page,
)


def _requests(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "requests": [
                    {
                        "request_id": "PROMOTE-AMDW-001",
                        "pair": "AMDW / AMDL",
                        "current_primary_strategy": "STRATEGY_A",
                        "proposed_primary_strategy": "STRATEGY_B",
                        "evaluation_days": 90,
                        "veto_deadline": "2099-08-18T17:00:00Z",
                        "status": "PENDING_OWNER_REVIEW",
                        "evidence_summary": "Strategy B produced higher return without worse drawdown.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _call(app, method: str, path: str, values=None, remote_user: str = "owner") -> tuple[str, str]:
    body = urlencode(values or {}).encode()
    response = {}

    def start_response(status, headers):
        response["status"] = status

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(body)),
        "CONTENT_TYPE": "application/x-www-form-urlencoded",
        "REMOTE_USER": remote_user,
        "wsgi.input": io.BytesIO(body),
    }
    payload = b"".join(app(environ, start_response)).decode()
    return response["status"], payload


def test_veto_token_is_signed_scoped_and_short_lived() -> None:
    token = issue_veto_token("PROMOTE-AMDW-001", "secret", issued_at=1000)
    verify_veto_token("PROMOTE-AMDW-001", token, "secret", now=1100)
    with pytest.raises(PermissionError):
        verify_veto_token("OTHER", token, "secret", now=1100)
    with pytest.raises(PermissionError):
        verify_veto_token("PROMOTE-AMDW-001", token, "secret", now=3000)


def test_veto_is_pair_specific_one_time_and_append_only(tmp_path: Path) -> None:
    requests = tmp_path / "requests.json"
    journal = tmp_path / "journal.jsonl"
    _requests(requests)
    event = veto_promotion_request(
        request_id="PROMOTE-AMDW-001",
        pair="AMDW / AMDL",
        owner_id="portal-owner",
        requests_path=requests,
        journal_path=journal,
    )
    assert event["event_type"] == "STRATEGY_PROMOTION_VETOED"
    assert event["paper_trade_mode"] is True
    assert event["broker_execution_enabled"] is False
    assert load_promotion_requests(requests)[0]["status"] == "VETOED"
    recorded = json.loads(journal.read_text(encoding="utf-8").splitlines()[0])
    assert recorded["owner_id"] == "portal-owner"
    with pytest.raises(ValueError, match="already vetoed"):
        veto_promotion_request(
            request_id="PROMOTE-AMDW-001",
            pair="AMDW / AMDL",
            owner_id="portal-owner",
            requests_path=requests,
            journal_path=journal,
        )


def test_cross_pair_veto_fails_closed_without_writing(tmp_path: Path) -> None:
    requests = tmp_path / "requests.json"
    journal = tmp_path / "journal.jsonl"
    _requests(requests)
    with pytest.raises(PermissionError):
        veto_promotion_request(
            request_id="PROMOTE-AMDW-001",
            pair="AVGW / AVGX",
            owner_id="portal-owner",
            requests_path=requests,
            journal_path=journal,
        )
    assert load_promotion_requests(requests)[0]["status"] == "PENDING_OWNER_REVIEW"
    assert not journal.exists()


def test_strategy_review_route_renders_and_vetoes_with_authenticated_owner(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    cash = tmp_path / "cash.json"
    requests = tmp_path / "promotion_requests.json"
    journal = tmp_path / "promotion_journal.jsonl"
    registry.write_text(json.dumps({"strategy_plugins": []}), encoding="utf-8")
    cash.write_text(json.dumps({"available_cash": 0, "allocated_cash": 0}), encoding="utf-8")
    _requests(requests)
    app = create_wsgi_app(
        registry_path=registry,
        cash_path=cash,
        promotion_requests_path=requests,
        promotion_journal_path=journal,
        owner_review_csrf_secret="review-secret",
    )

    status, page = _call(app, "GET", "/strategy-review")
    assert status == "200 OK"
    assert "Strategy Review" in page
    assert "AMDW / AMDL" in page
    assert "Veto Promotion" in page
    token = page.split("name='csrf_token' value='", 1)[1].split("'", 1)[0]

    status, result = _call(
        app,
        "POST",
        "/strategy-review/veto",
        {
            "request_id": "PROMOTE-AMDW-001",
            "pair": "AMDW / AMDL",
            "csrf_token": token,
            "owner_confirmed": "yes",
        },
        remote_user="percy-owner",
    )
    assert status == "200 OK"
    assert "Strategy Promotion Vetoed" in result
    assert load_promotion_requests(requests)[0]["status"] == "VETOED"
    assert json.loads(journal.read_text(encoding="utf-8"))["owner_id"] == "percy-owner"
    assert json.loads(cash.read_text(encoding="utf-8"))["allocated_cash"] == 0


def test_strategy_review_button_locks_when_secret_is_missing(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    cash = tmp_path / "cash.json"
    requests = tmp_path / "promotion_requests.json"
    registry.write_text(json.dumps({"strategy_plugins": []}), encoding="utf-8")
    cash.write_text(json.dumps({"available_cash": 0}), encoding="utf-8")
    _requests(requests)
    app = create_wsgi_app(
        registry_path=registry,
        cash_path=cash,
        promotion_requests_path=requests,
        owner_review_csrf_secret="",
    )
    status, page = _call(app, "GET", "/strategy-review")
    assert status == "200 OK"
    assert "controls are locked" in page
    assert "Veto Promotion" not in page



def test_strategy_review_displays_current_pair_assignments() -> None:
    page = render_strategy_review_page(
        [],
        csrf_secret="secret",
        assignments={
            "AMDW / AMDL": {
                "primary_strategy": "STRATEGY_A",
                "shadow_strategies": ["STRATEGY_B"],
                "assignment_source": "DEFAULT_PRODUCTION_BASELINE",
                "effective_at_utc": "2026-08-11T12:00:00Z",
            }
        },
    )
    assert "Current Pair Strategy Assignments" in page
    assert "AMDW / AMDL" in page
    assert "STRATEGY_A" in page
    assert "STRATEGY_B" in page
    assert "Default Production Baseline" in page


def _shadow_performance_rows() -> list[dict]:
    common = {
        "pair": "AMDW / AMDL",
        "evaluation_start": "2026-08-11",
        "evaluation_end": "2026-08-11",
        "virtual_capital_basis": 750.0,
        "max_drawdown_percent": 0.0,
        "observation_count": 1,
        "completed_trade_count": 0,
    }
    return [
        {**common, "strategy_id": "STRATEGY_A", "total_return_percent": 0.0},
        {**common, "strategy_id": "STRATEGY_B", "total_return_percent": 0.0},
    ]


def test_strategy_review_explains_pair_comparison_and_qualification_progress() -> None:
    page = render_strategy_review_page(
        [],
        csrf_secret="secret",
        assignments={
            "AMDW / AMDL": {
                "primary_strategy": "STRATEGY_A",
                "shadow_strategies": ["STRATEGY_B"],
            }
        },
        performance_rows=_shadow_performance_rows(),
    )
    assert "Strategy Performance and Qualification" in page
    assert "STRATEGY_A" in page
    assert "STRATEGY_B" in page
    assert "$750.00" in page
    assert "COLLECTING EVIDENCE" in page
    assert "1/90 evaluation days" in page
    assert "1/60 observations" in page
    assert "0/1 completed trades" in page
    assert "Virtual values never enter portfolio totals or the paper ledger" in page


def test_strategy_review_route_loads_shadow_performance_and_pending_status(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "registry.json"
    cash = tmp_path / "cash.json"
    requests = tmp_path / "promotion_requests.json"
    assignments = tmp_path / "assignments.json"
    performance = tmp_path / "performance.json"
    registry.write_text(json.dumps({"strategy_plugins": []}), encoding="utf-8")
    cash.write_text(json.dumps({"available_cash": 0}), encoding="utf-8")
    _requests(requests)
    assignments.write_text(
        json.dumps({
            "assignments": {
                "AMDW / AMDL": {
                    "primary_strategy": "STRATEGY_A",
                    "shadow_strategies": ["STRATEGY_B"],
                }
            }
        }),
        encoding="utf-8",
    )
    performance.write_text(
        json.dumps({"performance": _shadow_performance_rows()}),
        encoding="utf-8",
    )
    app = create_wsgi_app(
        registry_path=registry,
        cash_path=cash,
        promotion_requests_path=requests,
        strategy_assignments_path=assignments,
        strategy_performance_path=performance,
        owner_review_csrf_secret="review-secret",
    )

    status, page = _call(app, "GET", "/strategy-review")

    assert status == "200 OK"
    assert "$750.00" in page
    assert "PENDING REVIEW" in page
    assert "Qualified; owner may veto through 2099-08-18T17:00:00Z." in page
    assert "Veto Promotion" in page


def test_pair_card_groups_and_ranks_multiple_test_strategies() -> None:
    rows = _shadow_performance_rows()
    rows.append({
        **rows[0],
        "strategy_id": "STRATEGY_C",
        "display_name": "Strategy C",
        "strategy_role": "TEST_CANDIDATE",
        "total_return_percent": 2.0,
    })
    page = render_strategy_review_page(
        [],
        csrf_secret="secret",
        assignments={
            "AMDW / AMDL": {
                "primary_strategy": "STRATEGY_A",
                "shadow_strategies": ["STRATEGY_B", "STRATEGY_C"],
                "assignment_source": "DEFAULT_PRODUCTION_BASELINE",
                "effective_at_utc": "2026-08-11T18:08:00Z",
            }
        },
        performance_rows=rows,
    )
    assert page.count("class='pair-strategy-card'") == 1
    assert "class='pair-strategy-card' open" in page
    assert "View 2 candidates and evidence" in page
    assert "Assigned since: 2026-08-11T18:08:00Z" in page
    assert "Assigned Since" in page
    assert "Assignment Reason" in page
    assert "Default Production Baseline" in page
    assert "<th>Pair</th><th>Primary</th><th>Test Candidate</th>" in page
    assert "STRATEGY_B" in page
    assert "STRATEGY_C" in page
    assert "Leading by return" in page
    assert page.index("STRATEGY_C") < page.index("STRATEGY_B")


def test_strategy_review_renders_owner_alerts_and_pair_history(tmp_path: Path) -> None:
    journal = tmp_path / "journal.jsonl"
    journal.write_text(
        json.dumps({
            "event_type": "STRATEGY_PROMOTION_ACTIVATED",
            "pair": "AMDW / AMDL",
            "previous_primary_strategy": "STRATEGY_A",
            "new_primary_strategy": "STRATEGY_B",
            "recorded_at_utc": "2026-08-11T18:08:00Z",
            "reason": "NO_OWNER_VETO_DURING_SEVEN_DAY_REVIEW",
        }) + "\n",
        encoding="utf-8",
    )
    events = load_promotion_journal(journal)
    assert events[0]["event_type"] == "STRATEGY_PROMOTION_ACTIVATED"

    page = render_strategy_review_page(
        [],
        csrf_secret="secret",
        assignments={
            "AMDW / AMDL": {
                "primary_strategy": "STRATEGY_B",
                "previous_primary_strategy": "STRATEGY_A",
                "assignment_source": "PROMOTED_AFTER_OWNER_REVIEW",
                "effective_at_utc": "2026-08-11T18:08:00Z",
            }
        },
        performance_rows=[],
        governance_model={
            "alerts": [{
                "severity": "ACTION",
                "alert_type": "OWNER_REVIEW_REQUIRED",
                "pair": "AMDW / AMDL",
                "message": "Strategy B promotion requires review.",
                "owner_action": "Review and veto if necessary.",
            }],
            "histories": [{
                "pair": "AMDW / AMDL",
                "original_entry_strategy": "STRATEGY_A",
                "current_management_strategy": "STRATEGY_B",
                "previous_primary_strategy": "STRATEGY_A",
                "position_status": "OPEN_ETF_POSITION",
                "assignment_source": "PROMOTED_AFTER_OWNER_REVIEW",
                "assigned_since": "2026-08-11T18:08:00Z",
                "promotion_request_id": "PROMOTE-AMDW-001",
                "events": events,
            }],
        },
    )
    assert "Owner Alerts and Next Steps" in page
    assert "Owner Review Required" in page
    assert "Owner next step: Review and veto if necessary." in page
    assert "Pair Strategy History" in page
    assert "Original Entry Strategy" in page
    assert "Current Management Strategy" in page
    assert "STRATEGY_PROMOTION_ACTIVATED".replace("_", " ").title() in page
