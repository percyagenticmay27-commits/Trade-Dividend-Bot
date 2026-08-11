"""Build the read-only Dividend strategy Decision Journal from observed evidence."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

STRATEGY_ID = "DIVIDEND-001"
PAPER_TRADE_MODE = True
REPORTING_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False


def _text_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _timestamp(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return "Not reported"


def _pair_identity(row: Mapping[str, Any]) -> dict[str, str]:
    pair = str(row.get("pair") or "Unknown pair")
    symbols = [part.strip().upper() for part in pair.split("/") if part.strip()]
    return {
        "ecosystem_name": pair,
        "income_leg": symbols[0] if symbols else str(row.get("symbol") or "Not reported"),
        "leverage_leg": symbols[1] if len(symbols) > 1 else "Not reported",
    }


def _rationale(prefix: str, reasons: Sequence[str], fallback: str) -> str:
    detail = "; ".join(str(reason).replace("_", " ").lower() for reason in reasons)
    return f"{prefix}: {detail}." if detail else fallback


def _holding_decision(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    reasons = _text_list(row.get("sell_reasons") or row.get("exit_warning_reasons"))
    sell = row.get("sell_trigger") is True
    warning = row.get("exit_warning_active") is True or row.get("exit_buffered") is True
    decision = "SELL" if sell else "HOLD"
    if sell:
        rationale = _rationale(
            "Owner-specific exit is confirmed",
            reasons,
            "The owning strategy reported a confirmed paper exit.",
        )
        status = "ACTION_REQUIRED"
    elif warning:
        rationale = _rationale(
            "The position remains held because the warning is buffered",
            reasons,
            "A warning exists, but the owning strategy has not authorized a paper exit.",
        )
        status = "MONITOR"
    else:
        rationale = str(
            row.get("exit_authority_reason")
            or "No owner-specific sell condition is currently confirmed, so the position remains held."
        ).replace("_", " ").capitalize()
        status = "RECORDED"
    evidence_status = "AVAILABLE" if row.get("exit_evidence_source") else "NOT_REPORTED"
    return {
        "decision_id": f"HOLDING-{index}-{row.get('pair') or row.get('symbol')}",
        "strategy_id": STRATEGY_ID,
        "decision_timestamp": _timestamp(
            row,
            "exit_evidence_generated_at_utc",
            "entry_date",
            "purchase_date",
        ),
        "decision_type": decision,
        "status": status,
        "ecosystem": _pair_identity(row),
        "final_rationale": rationale,
        "alternatives": ["Continue holding"] if sell else ["Sell only when the owning strategy confirms an exit"],
        "committee_evidence": [{
            "engine": str(row.get("strategy_owner") or "POSITION_OWNER"),
            "vote": decision,
            "evidence_status": evidence_status,
            "evidence_summary": rationale,
        }],
        "images": [],
    }


def _watchlist_decision(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    entry_status = str(row.get("entry_status") or "EVIDENCE_UNAVAILABLE").upper()
    ready = entry_status in {"BUY", "READY", "PROMOTED"}
    reasons = _text_list(row.get("entry_reasons"))
    requirements = _text_list(row.get("requirements_for_buy"))
    if ready:
        decision = "BUY"
        status = "ENTRY_READY"
        rationale = _rationale(
            "Current entry requirements are satisfied",
            reasons,
            "The published entry evidence reports this candidate as ready for a paper entry.",
        )
    else:
        decision = "WATCHLIST"
        status = "WAITING_FOR_ENTRY"
        rationale = _rationale(
            "Paper purchase is blocked by current entry requirements",
            requirements or reasons,
            "Current entry evidence is unavailable; no paper purchase is authorized.",
        )
    return {
        "decision_id": f"WATCHLIST-{index}-{row.get('symbol') or 'UNKNOWN'}",
        "strategy_id": STRATEGY_ID,
        "decision_timestamp": _timestamp(row, "entry_evidence_generated_at_utc"),
        "decision_type": decision,
        "status": status,
        "ecosystem": {
            "ecosystem_name": str(row.get("symbol") or "Unknown candidate"),
            "income_leg": str(row.get("symbol") or "Not reported"),
            "leverage_leg": "Candidate pair leg not reported",
        },
        "final_rationale": rationale,
        "alternatives": requirements,
        "committee_evidence": [{
            "engine": "ENTRY_SCORE",
            "score": row.get("entry_score"),
            "confidence": row.get("entry_confidence_level") or row.get("entry_confidence"),
            "vote": entry_status,
            "evidence_status": "AVAILABLE" if row.get("entry_evidence_source") else "NOT_REPORTED",
            "evidence_summary": rationale,
        }],
        "images": [],
    }


def _historical_decision(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    reasons = _text_list(row.get("exit_reasons") or row.get("sell_reasons"))
    raw_reason = row.get("exit_reason") or row.get("reason")
    if raw_reason not in (None, ""):
        reasons.append(str(raw_reason))
    rationale = _rationale(
        "The recorded paper position was closed or parked",
        reasons,
        "Historical evidence records an exit, but no detailed reason was reported.",
    )
    return {
        "decision_id": f"HISTORY-{index}-{row.get('pair') or row.get('symbol')}",
        "strategy_id": STRATEGY_ID,
        "decision_timestamp": _timestamp(row, "exit_date", "last_exit_date", "date"),
        "decision_type": "SELL",
        "status": "COMPLETED",
        "ecosystem": _pair_identity(row),
        "final_rationale": rationale,
        "alternatives": ["Continue holding"],
        "committee_evidence": [{
            "engine": str(row.get("exit_strategy") or row.get("strategy_owner") or "HISTORICAL_LEDGER"),
            "vote": "SELL",
            "evidence_status": "AVAILABLE" if reasons else "PARTIAL",
            "evidence_summary": rationale,
        }],
        "images": [],
    }


def build_dividend_decision_journal(
    *,
    holdings: Sequence[Mapping[str, Any]],
    watchlist: Sequence[Mapping[str, Any]],
    historical_positions: Sequence[Mapping[str, Any]],
    generated_at: Any = None,
) -> dict[str, Any]:
    """Return strategy-owned decisions; never mutate state or authorize execution."""
    decisions: list[dict[str, Any]] = []
    decisions.extend(_holding_decision(row, index) for index, row in enumerate(holdings))
    decisions.extend(_watchlist_decision(row, index) for index, row in enumerate(watchlist))
    decisions.extend(_historical_decision(row, index) for index, row in enumerate(historical_positions))
    return {
        "strategy_id": STRATEGY_ID,
        "strategy_name": "Dividend Income Strategy",
        "strategy_type": "DIVIDEND",
        "generated_at": str(generated_at or "Not reported"),
        "decisions": decisions,
        "decision_count": len(decisions),
        "paper_trade_mode": True,
        "reporting_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
    }
