"""Pair-specific strategy promotion review and owner veto governance."""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False

PENDING = "PENDING_OWNER_REVIEW"
VETOED = "VETOED"
PROMOTED = "PROMOTED"
DEFAULT_PROMOTION_REQUESTS_PATH = Path("state/dividend_strategy_promotion_requests.json")
DEFAULT_PROMOTION_JOURNAL_PATH = Path("state/dividend_strategy_promotion_journal.jsonl")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_timestamp(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("promotion veto deadline is required")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_promotion_requests(path: str | Path) -> list[dict[str, Any]]:
    file = Path(path)
    if not file.is_file():
        return []
    value = json.loads(file.read_text(encoding="utf-8"))
    rows = value.get("requests", []) if isinstance(value, Mapping) else value
    if not isinstance(rows, list):
        raise ValueError("strategy promotion request artifact must contain a list")
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _write_requests(path: Path, requests: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "requests": [dict(row) for row in requests],
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def issue_veto_token(request_id: str, secret: str, *, issued_at: int | None = None) -> str:
    if not secret:
        raise RuntimeError("owner review anti-forgery secret is not configured")
    timestamp = int(time.time() if issued_at is None else issued_at)
    message = f"{request_id}|{timestamp}"
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return f"{timestamp}.{signature}"


def verify_veto_token(
    request_id: str,
    token: str,
    secret: str,
    *,
    now: int | None = None,
    max_age_seconds: int = 1800,
) -> None:
    if not secret:
        raise PermissionError("owner review anti-forgery secret is not configured")
    try:
        raw_timestamp, supplied = token.split(".", 1)
        issued_at = int(raw_timestamp)
    except (AttributeError, TypeError, ValueError) as exc:
        raise PermissionError("invalid owner review token") from exc
    current = int(time.time() if now is None else now)
    if issued_at > current + 60 or current - issued_at > max_age_seconds:
        raise PermissionError("owner review token has expired")
    message = f"{request_id}|{issued_at}"
    expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        raise PermissionError("invalid owner review token")


def veto_promotion_request(
    *,
    request_id: str,
    pair: str,
    owner_id: str,
    requests_path: str | Path,
    journal_path: str | Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    request_file = Path(requests_path)
    requests = load_promotion_requests(request_file)
    match = next((row for row in requests if str(row.get("request_id")) == request_id), None)
    if match is None:
        raise ValueError("strategy promotion request was not found")
    if str(match.get("pair") or "") != pair:
        raise PermissionError("promotion request does not belong to the submitted pair")
    status = str(match.get("status") or PENDING).upper()
    if status == VETOED:
        raise ValueError("strategy promotion request was already vetoed")
    if status != PENDING:
        raise ValueError("only pending strategy promotions may be vetoed")
    effective_now = (now or _utc_now()).astimezone(timezone.utc)
    if effective_now > _parse_timestamp(match.get("veto_deadline")):
        raise ValueError("owner veto window has expired")

    event = {
        "event_type": "STRATEGY_PROMOTION_VETOED",
        "request_id": request_id,
        "pair": pair,
        "current_primary_strategy": match.get("current_primary_strategy") or "STRATEGY_A",
        "proposed_primary_strategy": match.get("proposed_primary_strategy"),
        "owner_id": owner_id,
        "recorded_at_utc": _iso(effective_now),
        "reason": "OWNER_VETO_DURING_REVIEW_WINDOW",
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
    }
    match["status"] = VETOED
    match["vetoed_at_utc"] = event["recorded_at_utc"]
    match["vetoed_by"] = owner_id
    _write_requests(request_file, requests)
    journal_file = Path(journal_path)
    journal_file.parent.mkdir(parents=True, exist_ok=True)
    with journal_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return event


def render_strategy_review_page(
    requests: Sequence[Mapping[str, Any]],
    *,
    csrf_secret: str,
    assignments: Mapping[str, Mapping[str, Any]] | None = None,
) -> str:
    cards: list[str] = []
    for request in requests:
        if str(request.get("status") or PENDING).upper() != PENDING:
            continue
        request_id = str(request.get("request_id") or "").strip()
        pair = str(request.get("pair") or "Unknown pair")
        current = str(request.get("current_primary_strategy") or "STRATEGY_A")
        proposed = str(request.get("proposed_primary_strategy") or "Not reported")
        deadline = str(request.get("veto_deadline") or "Not reported")
        period = request.get("evaluation_days", 90)
        evidence = str(request.get("evidence_summary") or "Performance comparison evidence was not reported.")
        token = issue_veto_token(request_id, csrf_secret) if csrf_secret and request_id else ""
        action = (
            "<form method='post' action='/strategy-review/veto'>"
            f"<input type='hidden' name='request_id' value='{html.escape(request_id, quote=True)}'>"
            f"<input type='hidden' name='pair' value='{html.escape(pair, quote=True)}'>"
            f"<input type='hidden' name='csrf_token' value='{html.escape(token, quote=True)}'>"
            "<label><input style='width:auto' type='checkbox' name='owner_confirmed' value='yes' required> "
            "I am the owner and veto this pair-specific strategy promotion.</label>"
            "<p><button class='veto-button' type='submit'>Veto Promotion</button></p></form>"
            if token
            else "<p class='warning'>Veto controls are locked because the anti-forgery secret is not configured.</p>"
        )
        cards.append(
            "<article class='promotion-review-card'>"
            f"<header><h3>{html.escape(pair)}</h3><span>{PENDING.replace('_', ' ').title()}</span></header>"
            "<dl>"
            f"<div><dt>Current primary</dt><dd>{html.escape(current)}</dd></div>"
            f"<div><dt>Proposed primary</dt><dd>{html.escape(proposed)}</dd></div>"
            f"<div><dt>Evaluation period</dt><dd>{html.escape(str(period))} days</dd></div>"
            f"<div><dt>Veto deadline</dt><dd>{html.escape(deadline)}</dd></div>"
            "</dl>"
            f"<p><strong>Why promotion was requested:</strong> {html.escape(evidence)}</p>"
            f"{action}</article>"
        )
    body = "".join(cards) or (
        "<p class='empty-state'>No pair-specific strategy promotions are awaiting owner review.</p>"
    )
    assignment_rows = []
    for pair, assignment in sorted((assignments or {}).items()):
        primary = str(assignment.get("primary_strategy") or "STRATEGY_A")
        shadows = ", ".join(str(value) for value in assignment.get("shadow_strategies", [])) or "None"
        source = str(assignment.get("assignment_source") or "DEFAULT_PRODUCTION_BASELINE")
        effective = str(assignment.get("effective_at_utc") or "Not reported")
        assignment_rows.append(
            "<tr>"
            f"<td><strong>{html.escape(str(pair))}</strong></td>"
            f"<td>{html.escape(primary)}</td>"
            f"<td>{html.escape(shadows)}</td>"
            f"<td>{html.escape(source.replace('_', ' ').title())}</td>"
            f"<td>{html.escape(effective)}</td></tr>"
        )
    assignments_body = (
        "<div class='assignment-table-wrap'><table><thead><tr>"
        "<th>Pair</th><th>Current Primary</th><th>Shadow/Test Strategies</th>"
        "<th>Assignment Reason</th><th>Effective</th></tr></thead><tbody>"
        + "".join(assignment_rows)
        + "</tbody></table></div>"
        if assignment_rows
        else "<p class='empty-state'>Pair assignments have not been initialized by the daily promotion cycle.</p>"
    )
    return (
        "<section class='panel strategy-review'><h2>Strategy Review</h2>"
        "<p>Review proposed pair-specific changes before a test strategy becomes primary. "
        "No response allows promotion after the seven-day review window; a veto keeps the current primary.</p>"
        "<h3>Pending Owner Decisions</h3>"
        f"{body}<h3>Current Pair Strategy Assignments</h3>{assignments_body}</section>"
    )
