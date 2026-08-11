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
    verify_veto_token,
    veto_promotion_request,
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
