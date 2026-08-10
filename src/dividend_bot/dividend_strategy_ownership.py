"""Strategy ownership routing for Dividend paper positions.

This module does not place or simulate orders. It decides which Dividend timing
strategy owns a prospective or existing paper position so lifecycle exits cannot
silently switch methodologies.

Rules
-----
* Existing valid ownership is sticky for the life of the open position.
* A new position may be owned by Strategy A when only Strategy A is BUY-active.
* A new position may be owned by Strategy B when only Strategy B is BUY-active.
* If neither strategy is BUY-active, ownership is unresolved and entry must wait.
* If both strategies are BUY-active, ownership is intentionally unresolved until
  an explicit precedence/selection policy exists. The router fails closed rather
  than arbitrarily choosing a strategy.
* Strategy A's fast Stoch RSI bearish cross is warning evidence only. It is
  preserved through owner routing while the slower Stochastic Oscillator decides
  whether the warning becomes an executable exit.
"""
from __future__ import annotations

from typing import Any, Mapping

PAPER_TRADE_MODE = True
REPORTING_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

STRATEGY_A = "STRATEGY_A"
STRATEGY_B = "STRATEGY_B"
VALID_OWNERS = {STRATEGY_A, STRATEGY_B}


def _normalized_owner(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    return text if text in VALID_OWNERS else None


def resolve_strategy_ownership(
    strategy_signals: Mapping[str, Any] | None,
    *,
    existing_owner: str | None = None,
) -> dict[str, Any]:
    """Resolve sticky strategy ownership without inventing precedence.

    ``existing_owner`` is authoritative for an already-open position. For a new
    position, the current Strategy A/B BUY states determine eligibility.
    """
    owner = _normalized_owner(existing_owner)
    if owner:
        return {
            "resolved": True,
            "strategy_owner": owner,
            "eligible_strategies": [owner],
            "reason": "EXISTING_POSITION_STRATEGY_OWNERSHIP_PRESERVED",
            "entry_allowed_by_ownership": True,
            "ownership_source": "existing_position",
        }

    signals = strategy_signals if isinstance(strategy_signals, Mapping) else {}
    strategy_a = signals.get("strategy_a") if isinstance(signals.get("strategy_a"), Mapping) else {}
    strategy_b = signals.get("strategy_b") if isinstance(signals.get("strategy_b"), Mapping) else {}

    a_buy = bool(strategy_a.get("buy_trigger"))
    b_buy = bool(strategy_b.get("buy_eligible"))
    eligible = [
        name for name, active in ((STRATEGY_A, a_buy), (STRATEGY_B, b_buy)) if active
    ]

    if len(eligible) == 1:
        return {
            "resolved": True,
            "strategy_owner": eligible[0],
            "eligible_strategies": eligible,
            "reason": "SINGLE_ACTIVE_ENTRY_STRATEGY",
            "entry_allowed_by_ownership": True,
            "ownership_source": "current_entry_signals",
        }

    if not eligible:
        return {
            "resolved": False,
            "strategy_owner": None,
            "eligible_strategies": [],
            "reason": "NO_ACTIVE_ENTRY_STRATEGY",
            "entry_allowed_by_ownership": False,
            "ownership_source": "current_entry_signals",
        }

    return {
        "resolved": False,
        "strategy_owner": None,
        "eligible_strategies": eligible,
        "reason": "MULTIPLE_ACTIVE_ENTRY_STRATEGIES_REQUIRE_SELECTION_POLICY",
        "entry_allowed_by_ownership": False,
        "ownership_source": "current_entry_signals",
    }


def owned_exit_signal(
    strategy_signals: Mapping[str, Any] | None,
    strategy_owner: str | None,
) -> dict[str, Any]:
    """Return only the exit authority belonging to the position's owner.

    Strategy A warning/buffer evidence is intentionally preserved even when the
    final sell trigger is false so downstream paper state and AI CIO reporting can
    distinguish a fast momentum warning from a confirmed exit.
    """
    owner = _normalized_owner(strategy_owner)
    signals = strategy_signals if isinstance(strategy_signals, Mapping) else {}

    if owner == STRATEGY_A:
        detail = signals.get("strategy_a") if isinstance(signals.get("strategy_a"), Mapping) else {}
        triggered = bool(detail.get("sell_trigger"))
        warning_active = bool(detail.get("exit_warning_active"))
        buffered = bool(detail.get("exit_buffered"))
        warning_reasons = list(detail.get("exit_warning_reasons") or [])
        return {
            "strategy_owner": owner,
            "sell_trigger": triggered,
            "sell_reasons": list(detail.get("sell_reasons") or []),
            "exit_warning_active": warning_active,
            "exit_buffered": buffered,
            "exit_warning_reasons": warning_reasons,
            "exit_state": "SELL_CONFIRMED" if triggered else ("WARNING_BUFFERED" if warning_active else "HOLD"),
            "reason": "STRATEGY_A_EXIT_AUTHORITY",
        }

    if owner == STRATEGY_B:
        detail = signals.get("strategy_b") if isinstance(signals.get("strategy_b"), Mapping) else {}
        triggered = bool(detail.get("sell_trigger"))
        reason = detail.get("sell_reason")
        return {
            "strategy_owner": owner,
            "sell_trigger": triggered,
            "sell_reasons": [reason] if reason else [],
            "exit_warning_active": False,
            "exit_buffered": False,
            "exit_warning_reasons": [],
            "exit_state": "SELL_CONFIRMED" if triggered else "HOLD",
            "reason": "STRATEGY_B_EXIT_AUTHORITY",
        }

    return {
        "strategy_owner": None,
        "sell_trigger": False,
        "sell_reasons": [],
        "exit_warning_active": False,
        "exit_buffered": False,
        "exit_warning_reasons": [],
        "exit_state": "UNKNOWN",
        "reason": "STRATEGY_OWNERSHIP_UNKNOWN_FAIL_CLOSED",
    }
