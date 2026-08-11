"""Read-only pair strategy history and owner alert evidence."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping, Sequence

PAPER_TRADE_MODE = True
REPORTING_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False

STALE_AFTER_DAYS = 3
NEARING_DAYS = 75
NEARING_OBSERVATIONS = 50


def _date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)


def _number(row: Mapping[str, Any], key: str) -> float:
    try:
        return float(row.get(key, 0))
    except (TypeError, ValueError):
        return 0.0


def _entry_strategy(pair_state: Mapping[str, Any]) -> str:
    direct = str(pair_state.get("strategy_owner") or "").strip().upper()
    if direct:
        return direct
    owners = {
        str(pair_state.get(key) or "").strip().upper()
        for key in ("a_strategy_owner", "b_strategy_owner")
        if str(pair_state.get(key) or "").strip()
    }
    if len(owners) == 1:
        return next(iter(owners))
    if len(owners) > 1:
        return "MIXED_ENTRY_STRATEGIES"
    return "NOT_ASSIGNED_OR_PARKED"


def _position_status(pair_state: Mapping[str, Any]) -> str:
    a_parked = bool(pair_state.get("a_in_sgov"))
    b_parked = bool(pair_state.get("b_in_sgov"))
    if a_parked and b_parked:
        return "PARKED_IN_SGOV"
    if a_parked or b_parked:
        return "MIXED_ETF_AND_SGOV"
    return "OPEN_ETF_POSITION"


def build_strategy_history_alerts(
    *,
    assignments: Mapping[str, Mapping[str, Any]],
    performance_report: Mapping[str, Any],
    requests: Sequence[Mapping[str, Any]],
    journal_events: Sequence[Mapping[str, Any]],
    paper_state: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build transparent owner-facing alerts without changing lifecycle state."""
    effective_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    performance_rows = performance_report.get("performance")
    performance_rows = performance_rows if isinstance(performance_rows, list) else []
    by_pair: dict[str, list[Mapping[str, Any]]] = {}
    for row in performance_rows:
        if isinstance(row, Mapping):
            by_pair.setdefault(str(row.get("pair") or ""), []).append(row)

    alerts: list[dict[str, Any]] = []
    report_date = _date(performance_report.get("as_of_date"))
    if report_date is None:
        alerts.append({
            "severity": "WARNING",
            "alert_type": "MISSING_STRATEGY_EVIDENCE",
            "pair": "ALL",
            "message": "Shadow strategy evidence has no reported as-of date.",
            "owner_action": "Run the daily paper cycle and review evidence generation.",
        })
    elif (effective_now.date() - report_date).days > STALE_AFTER_DAYS:
        alerts.append({
            "severity": "WARNING",
            "alert_type": "STALE_STRATEGY_EVIDENCE",
            "pair": "ALL",
            "message": f"Shadow strategy evidence is dated {report_date.isoformat()}.",
            "owner_action": "Run the daily paper cycle before relying on promotion evidence.",
        })

    request_by_pair: dict[str, list[Mapping[str, Any]]] = {}
    for request in requests:
        if isinstance(request, Mapping):
            request_by_pair.setdefault(str(request.get("pair") or ""), []).append(request)
            if str(request.get("status") or "").upper() == "PENDING_OWNER_REVIEW":
                deadline = _timestamp(request.get("veto_deadline"))
                remaining = (
                    (deadline - effective_now).total_seconds() / 86400
                    if deadline is not None else None
                )
                urgent = remaining is not None and remaining <= 2
                alerts.append({
                    "severity": "CRITICAL" if urgent else "ACTION",
                    "alert_type": "VETO_DEADLINE_APPROACHING" if urgent else "OWNER_REVIEW_REQUIRED",
                    "pair": str(request.get("pair") or "Unknown pair"),
                    "message": (
                        f"Review {request.get('proposed_primary_strategy')} promotion; "
                        f"veto deadline {request.get('veto_deadline') or 'not reported'}."
                    ),
                    "owner_action": "Open the pending decision and veto it if the current primary should remain.",
                })

    paper_pairs = paper_state.get("pairs")
    paper_pairs = paper_pairs if isinstance(paper_pairs, Mapping) else {}
    histories: list[dict[str, Any]] = []
    for pair, assignment in sorted(assignments.items()):
        rows = by_pair.get(pair, [])
        primary_id = str(assignment.get("primary_strategy") or "STRATEGY_A")
        primary = next(
            (row for row in rows if str(row.get("strategy_id")) == primary_id),
            None,
        )
        candidates = [
            row for row in rows if str(row.get("strategy_id") or "") != primary_id
        ]
        if primary is None or not candidates:
            alerts.append({
                "severity": "WARNING",
                "alert_type": "MISSING_PAIR_COMPARISON",
                "pair": pair,
                "message": "Primary and candidate comparison evidence is incomplete.",
                "owner_action": "Review the next daily evidence refresh.",
            })
        elif not any(
            str(row.get("status") or "").upper() == "PENDING_OWNER_REVIEW"
            for row in request_by_pair.get(pair, [])
        ):
            for candidate in candidates:
                start = max(
                    _date(primary.get("evaluation_start")) or effective_now.date(),
                    _date(candidate.get("evaluation_start")) or effective_now.date(),
                )
                end = min(
                    _date(primary.get("evaluation_end")) or effective_now.date(),
                    _date(candidate.get("evaluation_end")) or effective_now.date(),
                )
                days = max((end - start).days + 1, 0)
                observations = int(min(
                    _number(primary, "observation_count"),
                    _number(candidate, "observation_count"),
                ))
                trades = int(min(
                    _number(primary, "completed_trade_count"),
                    _number(candidate, "completed_trade_count"),
                ))
                if days >= NEARING_DAYS and observations >= NEARING_OBSERVATIONS and trades >= 1:
                    alerts.append({
                        "severity": "INFO",
                        "alert_type": "CANDIDATE_NEARING_QUALIFICATION",
                        "pair": pair,
                        "message": (
                            f"{candidate.get('strategy_id')} has {days}/90 days and "
                            f"{observations}/60 observations."
                        ),
                        "owner_action": "Continue monitoring; no owner decision is required yet.",
                    })

        pair_state = paper_pairs.get(pair)
        pair_state = pair_state if isinstance(pair_state, Mapping) else {}
        events = [
            dict(event)
            for event in journal_events
            if isinstance(event, Mapping) and str(event.get("pair") or "") == pair
        ]
        histories.append({
            "pair": pair,
            "original_entry_strategy": _entry_strategy(pair_state),
            "current_management_strategy": primary_id,
            "previous_primary_strategy": assignment.get("previous_primary_strategy") or "NONE",
            "position_status": _position_status(pair_state),
            "assignment_source": assignment.get("assignment_source") or "DEFAULT_PRODUCTION_BASELINE",
            "assigned_since": assignment.get("effective_at_utc") or "Not reported",
            "promotion_request_id": assignment.get("promotion_request_id") or "NONE",
            "events": events,
        })

    recent_cutoff = effective_now.timestamp() - 7 * 86400
    for event in journal_events:
        if not isinstance(event, Mapping):
            continue
        event_type = str(event.get("event_type") or "")
        recorded = _timestamp(event.get("recorded_at_utc") or event.get("promoted_at_utc"))
        if recorded is None or recorded.timestamp() < recent_cutoff:
            continue
        if event_type == "STRATEGY_PROMOTION_ACTIVATED":
            alerts.append({
                "severity": "INFO",
                "alert_type": "PROMOTION_ACTIVATED",
                "pair": str(event.get("pair") or "Unknown pair"),
                "message": f"{event.get('new_primary_strategy')} became the current primary.",
                "owner_action": "Review the pair history; no immediate action is required.",
            })

    severity_order = {"CRITICAL": 0, "ACTION": 1, "WARNING": 2, "INFO": 3}
    alerts.sort(key=lambda row: (severity_order.get(str(row["severity"]), 9), str(row["pair"])))
    return {
        "alerts": alerts,
        "histories": histories,
        "paper_trade_mode": True,
        "reporting_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
    }
