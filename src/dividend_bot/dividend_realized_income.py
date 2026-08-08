"""Normalize realized Dividend strategy income from paper-only transaction evidence.

This module is reporting-only. It reads transaction rows that are already owned by the
Dividend strategy and produces an auditable income ledger plus gross, adjustment, and
net totals. It never changes portfolio state, cash, allocations, or broker execution.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

PAPER_TRADE_MODE = True
REPORTING_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

_RECEIPT_ACTIONS = {
    "PAPER_DIVIDEND_RECEIVED",
    "PAPER_DISTRIBUTION_RECEIVED",
}
_ADJUSTMENT_ACTIONS = {
    "PAPER_DIVIDEND_ADJUSTMENT",
    "PAPER_DISTRIBUTION_ADJUSTMENT",
    "PAPER_DIVIDEND_REVERSAL",
    "PAPER_DISTRIBUTION_REVERSAL",
}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalized_amount(row: Mapping[str, Any], action: str) -> float | None:
    amount = _number(
        row.get("Paper_Value")
        if row.get("Paper_Value") not in (None, "")
        else row.get("Amount")
    )
    if amount is None:
        return None
    # Reversal actions are negative economic income even if a legacy row stored the
    # absolute correction amount as a positive number.
    if "REVERSAL" in action and amount > 0:
        amount = -amount
    return round(amount, 2)


def build_realized_income_evidence(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return an auditable realized-income summary from paper transaction rows."""
    events: list[dict[str, Any]] = []
    gross_distributions = 0.0
    income_adjustments = 0.0

    for row in rows:
        action = str(row.get("Action") or row.get("action") or "").strip().upper()
        if action not in _RECEIPT_ACTIONS and action not in _ADJUSTMENT_ACTIONS:
            continue
        amount = _normalized_amount(row, action)
        if amount is None:
            continue

        is_receipt = action in _RECEIPT_ACTIONS and amount >= 0
        event_type = "DISTRIBUTION_RECEIVED" if is_receipt else "INCOME_ADJUSTMENT"
        if "REVERSAL" in action:
            event_type = "DISTRIBUTION_REVERSAL"

        if is_receipt:
            gross_distributions += amount
        else:
            income_adjustments += amount

        events.append({
            "date": row.get("Date") or row.get("date"),
            "symbol": row.get("Ticker") or row.get("ticker") or row.get("Pair") or "DIVIDEND",
            "pair": row.get("Pair") or row.get("pair"),
            "action": action,
            "event_type": event_type,
            "amount": amount,
            "source": "paper_trade_log.csv",
        })

    net_income = round(gross_distributions + income_adjustments, 2)
    return {
        "gross_distribution_income": round(gross_distributions, 2),
        "income_adjustments": round(income_adjustments, 2),
        "net_income_received": net_income,
        "realized_income_event_count": len(events),
        "positive_income_event_count": sum(1 for item in events if (item.get("amount") or 0) > 0),
        "negative_income_event_count": sum(1 for item in events if (item.get("amount") or 0) < 0),
        "income_events": events[-100:],
        "income_accounting_method": "PAPER_TRANSACTION_LEDGER_NET_OF_ADJUSTMENTS",
        "income_evidence_source": "paper_trade_log.csv",
        "paper_trade_mode": True,
        "reporting_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
    }
