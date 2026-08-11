"""Pair-specific primary/shadow strategy evaluation and promotion lifecycle.

This module changes strategy governance only. It cannot move capital or place orders.
Strategy A is the default primary for every Dividend pair. Other strategies remain
shadow-only until a pair-specific request survives owner review.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False

STRATEGY_A = "STRATEGY_A"
PENDING = "PENDING_OWNER_REVIEW"
VETOED = "VETOED"
PROMOTED = "PROMOTED"
EVALUATION_DAYS = 90
VETO_DAYS = 7
MIN_OBSERVATIONS = 60
MIN_COMPLETED_TRADES = 1

DEFAULT_ASSIGNMENTS_PATH = Path("state/dividend_pair_strategy_assignments.json")
DEFAULT_REQUESTS_PATH = Path("state/dividend_strategy_promotion_requests.json")
DEFAULT_JOURNAL_PATH = Path("state/dividend_strategy_promotion_journal.jsonl")


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _date(value: Any) -> date:
    return date.fromisoformat(str(value)[:10])


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _append_journal(path: Path, event: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(event), sort_keys=True) + "\n")


def load_assignments(path: str | Path) -> dict[str, dict[str, Any]]:
    file = Path(path)
    if not file.is_file():
        return {}
    value = json.loads(file.read_text(encoding="utf-8"))
    rows = value.get("assignments", {}) if isinstance(value, Mapping) else {}
    if not isinstance(rows, Mapping):
        raise ValueError("pair strategy assignments must contain an assignments object")
    return {str(pair): dict(row) for pair, row in rows.items() if isinstance(row, Mapping)}


def ensure_pair_assignments(
    pairs: Sequence[str],
    *,
    path: str | Path = DEFAULT_ASSIGNMENTS_PATH,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    file = Path(path)
    assignments = load_assignments(file)
    timestamp = _iso(now or datetime.now(timezone.utc))
    changed = False
    for pair in pairs:
        if pair not in assignments:
            assignments[pair] = {
                "pair": pair,
                "primary_strategy": STRATEGY_A,
                "assignment_status": "ACTIVE",
                "assignment_source": "DEFAULT_PRODUCTION_BASELINE",
                "effective_at_utc": timestamp,
                "shadow_strategies": ["STRATEGY_B"],
                "paper_trade_mode": True,
            }
            changed = True
    if changed or not file.is_file():
        _write_json(
            file,
            {
                "schema_version": "1.0",
                "paper_trade_mode": True,
                "live_trading_enabled": False,
                "broker_execution_enabled": False,
                "assignments": assignments,
            },
        )
    return assignments


def load_requests(path: str | Path) -> list[dict[str, Any]]:
    file = Path(path)
    if not file.is_file():
        return []
    value = json.loads(file.read_text(encoding="utf-8"))
    rows = value.get("requests", []) if isinstance(value, Mapping) else value
    if not isinstance(rows, list):
        raise ValueError("promotion requests must contain a requests list")
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _save_requests(path: Path, requests: Sequence[Mapping[str, Any]]) -> None:
    _write_json(
        path,
        {
            "schema_version": "1.0",
            "paper_trade_mode": True,
            "live_trading_enabled": False,
            "broker_execution_enabled": False,
            "requests": [dict(row) for row in requests],
        },
    )


def _metric(row: Mapping[str, Any], key: str) -> float:
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"strategy performance is missing numeric {key}") from exc


def _int_metric(row: Mapping[str, Any], key: str) -> int:
    try:
        return int(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"strategy performance is missing integer {key}") from exc


def challenger_qualification(
    primary: Mapping[str, Any],
    challenger: Mapping[str, Any],
) -> dict[str, Any]:
    if str(primary.get("pair")) != str(challenger.get("pair")):
        raise ValueError("strategy comparison must be for the same pair")
    start = max(_date(primary.get("evaluation_start")), _date(challenger.get("evaluation_start")))
    end = min(_date(primary.get("evaluation_end")), _date(challenger.get("evaluation_end")))
    covered_days = (end - start).days + 1
    primary_return = _metric(primary, "total_return_percent")
    challenger_return = _metric(challenger, "total_return_percent")
    primary_drawdown = abs(_metric(primary, "max_drawdown_percent"))
    challenger_drawdown = abs(_metric(challenger, "max_drawdown_percent"))
    primary_observations = _int_metric(primary, "observation_count")
    challenger_observations = _int_metric(challenger, "observation_count")
    primary_trades = _int_metric(primary, "completed_trade_count")
    challenger_trades = _int_metric(challenger, "completed_trade_count")

    checks = {
        "evaluation_window_at_least_90_days": covered_days >= EVALUATION_DAYS,
        "both_have_sufficient_observations": min(primary_observations, challenger_observations) >= MIN_OBSERVATIONS,
        "both_have_completed_trade_evidence": min(primary_trades, challenger_trades) >= MIN_COMPLETED_TRADES,
        "challenger_total_return_higher": challenger_return > primary_return,
        "challenger_drawdown_no_worse": challenger_drawdown <= primary_drawdown,
    }
    return {
        "qualified": all(checks.values()),
        "checks": checks,
        "pair": str(primary.get("pair")),
        "current_primary_strategy": str(primary.get("strategy_id") or STRATEGY_A),
        "proposed_primary_strategy": str(challenger.get("strategy_id") or ""),
        "evaluation_start": start.isoformat(),
        "evaluation_end": end.isoformat(),
        "evaluation_days": covered_days,
        "primary_total_return_percent": primary_return,
        "challenger_total_return_percent": challenger_return,
        "primary_max_drawdown_percent": primary_drawdown,
        "challenger_max_drawdown_percent": challenger_drawdown,
        "primary_observation_count": primary_observations,
        "challenger_observation_count": challenger_observations,
        "primary_completed_trade_count": primary_trades,
        "challenger_completed_trade_count": challenger_trades,
    }


def create_promotion_requests(
    performance_rows: Sequence[Mapping[str, Any]],
    *,
    assignments_path: str | Path = DEFAULT_ASSIGNMENTS_PATH,
    requests_path: str | Path = DEFAULT_REQUESTS_PATH,
    journal_path: str | Path = DEFAULT_JOURNAL_PATH,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    effective_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    assignments = load_assignments(assignments_path)
    requests = load_requests(requests_path)
    active_pairs = {
        str(row.get("pair"))
        for row in requests
        if str(row.get("status") or "").upper() == PENDING
    }
    by_pair: dict[str, list[Mapping[str, Any]]] = {}
    for row in performance_rows:
        if isinstance(row, Mapping):
            by_pair.setdefault(str(row.get("pair") or ""), []).append(row)

    for pair, rows in by_pair.items():
        assignment = assignments.get(pair)
        if not assignment or pair in active_pairs:
            continue
        primary_id = str(assignment.get("primary_strategy") or STRATEGY_A)
        primary = next((row for row in rows if str(row.get("strategy_id")) == primary_id), None)
        if primary is None:
            continue
        qualified: list[dict[str, Any]] = []
        for challenger in rows:
            challenger_id = str(challenger.get("strategy_id") or "")
            if not challenger_id or challenger_id == primary_id:
                continue
            result = challenger_qualification(primary, challenger)
            if result["qualified"]:
                qualified.append(result)
        if not qualified:
            continue
        winner = max(qualified, key=lambda row: float(row["challenger_total_return_percent"]))
        request_id = f"PROMOTE-{pair.replace(' / ', '-')}-{uuid4().hex[:12].upper()}"
        deadline = effective_now + timedelta(days=VETO_DAYS)
        request = {
            "request_id": request_id,
            "pair": pair,
            "current_primary_strategy": primary_id,
            "proposed_primary_strategy": winner["proposed_primary_strategy"],
            "status": PENDING,
            "requested_at_utc": _iso(effective_now),
            "veto_deadline": _iso(deadline),
            "evaluation_days": EVALUATION_DAYS,
            "qualification": winner,
            "evidence_summary": (
                f"{winner['proposed_primary_strategy']} returned "
                f"{winner['challenger_total_return_percent']:.2f}% versus "
                f"{primary_id} at {winner['primary_total_return_percent']:.2f}%, "
                "with no worse maximum drawdown and sufficient evidence."
            ),
            "paper_trade_mode": True,
        }
        requests.append(request)
        _append_journal(
            Path(journal_path),
            {
                "event_type": "STRATEGY_PROMOTION_REQUESTED",
                **request,
                "live_trading_enabled": False,
                "broker_execution_enabled": False,
                "capital_movement_enabled": False,
            },
        )
    _save_requests(Path(requests_path), requests)
    return requests


def activate_unvetoed_promotions(
    *,
    assignments_path: str | Path = DEFAULT_ASSIGNMENTS_PATH,
    requests_path: str | Path = DEFAULT_REQUESTS_PATH,
    journal_path: str | Path = DEFAULT_JOURNAL_PATH,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    effective_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    assignment_file = Path(assignments_path)
    request_file = Path(requests_path)
    assignments = load_assignments(assignment_file)
    requests = load_requests(request_file)
    activated: list[dict[str, Any]] = []
    for request in requests:
        if str(request.get("status") or "").upper() != PENDING:
            continue
        deadline = datetime.fromisoformat(str(request.get("veto_deadline")).replace("Z", "+00:00"))
        if effective_now <= deadline:
            continue
        pair = str(request.get("pair") or "")
        assignment = assignments.get(pair)
        if not assignment:
            continue
        if str(assignment.get("primary_strategy")) != str(request.get("current_primary_strategy")):
            request["status"] = "STALE_ASSIGNMENT_CHANGED"
            continue
        previous = str(assignment.get("primary_strategy"))
        promoted = str(request.get("proposed_primary_strategy"))
        assignment.update(
            {
                "primary_strategy": promoted,
                "previous_primary_strategy": previous,
                "assignment_status": "ACTIVE",
                "assignment_source": "PROMOTED_AFTER_OWNER_REVIEW",
                "promotion_request_id": request.get("request_id"),
                "effective_at_utc": _iso(effective_now),
            }
        )
        shadows = [str(value) for value in assignment.get("shadow_strategies", [])]
        assignment["shadow_strategies"] = list(dict.fromkeys([value for value in shadows + [previous] if value != promoted]))
        request["status"] = PROMOTED
        request["promoted_at_utc"] = _iso(effective_now)
        event = {
            "event_type": "STRATEGY_PROMOTION_ACTIVATED",
            "request_id": request.get("request_id"),
            "pair": pair,
            "previous_primary_strategy": previous,
            "new_primary_strategy": promoted,
            "recorded_at_utc": _iso(effective_now),
            "reason": "NO_OWNER_VETO_DURING_SEVEN_DAY_REVIEW",
            "paper_trade_mode": True,
            "live_trading_enabled": False,
            "broker_execution_enabled": False,
            "capital_movement_enabled": False,
        }
        _append_journal(Path(journal_path), event)
        activated.append(event)
    _write_json(
        assignment_file,
        {
            "schema_version": "1.0",
            "paper_trade_mode": True,
            "live_trading_enabled": False,
            "broker_execution_enabled": False,
            "assignments": assignments,
        },
    )
    _save_requests(request_file, requests)
    return activated


def run_strategy_promotion_cycle(
    performance_rows: Sequence[Mapping[str, Any]],
    *,
    pairs: Sequence[str],
    assignments_path: str | Path = DEFAULT_ASSIGNMENTS_PATH,
    requests_path: str | Path = DEFAULT_REQUESTS_PATH,
    journal_path: str | Path = DEFAULT_JOURNAL_PATH,
    now: datetime | None = None,
) -> dict[str, Any]:
    assignments = ensure_pair_assignments(pairs, path=assignments_path, now=now)
    requests = create_promotion_requests(
        performance_rows,
        assignments_path=assignments_path,
        requests_path=requests_path,
        journal_path=journal_path,
        now=now,
    )
    activated = activate_unvetoed_promotions(
        assignments_path=assignments_path,
        requests_path=requests_path,
        journal_path=journal_path,
        now=now,
    )
    return {
        "assignments": load_assignments(assignments_path),
        "requests": requests,
        "activated": activated,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
    }
