"""Strategy ownership routing for Dividend paper positions.

This module does not place or simulate orders. It decides which Dividend timing
strategy owns a prospective or existing paper position so lifecycle exits cannot
silently switch methodologies.

Rules
-----
* Existing valid Strategy A/B ownership is sticky for the life of the open position.
* A new position may be owned by Strategy A when only Strategy A is BUY-active.
* A new position may be owned by Strategy B when only Strategy B is BUY-active.
* If neither strategy is BUY-active, ownership is unresolved and entry must wait.
* If both strategies are BUY-active, ownership is intentionally unresolved until
  an explicit precedence/selection policy exists. The router fails closed rather
  than arbitrarily choosing a strategy.
* Strategy A's fast Stoch RSI bearish cross is warning evidence only. It is
  preserved through owner routing while the slower Stochastic Oscillator decides
  whether the warning becomes an executable exit.
* Legacy paper positions that predate ownership may be explicitly tagged
  LEGACY_UNASSIGNED. They are never retroactively assigned Strategy A or B.
  Their ordinary technical exit requires independent SELL confirmation from both
  Strategy A and Strategy B. One-strategy-only deterioration is buffered as a
  warning, not executed as a sale.
"""
from __future__ import annotations

from typing import Any, Mapping

PAPER_TRADE_MODE = True
REPORTING_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

STRATEGY_A = "STRATEGY_A"
STRATEGY_B = "STRATEGY_B"
LEGACY_UNASSIGNED = "LEGACY_UNASSIGNED"
VALID_OWNERS = {STRATEGY_A, STRATEGY_B}


def _normalized_owner(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    return text if text in VALID_OWNERS else None


def _raw_owner(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    return text or None


def resolve_strategy_ownership(
    strategy_signals: Mapping[str, Any] | None,
    *,
    existing_owner: str | None = None,
    pair_primary_strategy: str | None = STRATEGY_A,
) -> dict[str, Any]:
    """Resolve entry authority from the approved pair-specific primary strategy.

    Strategy A is the default production primary. Other strategies are shadow
    evidence only unless a pair-specific promotion assignment names one as
    primary. Existing ownership is retained as entry-history evidence; it cannot
    overrule a subsequently approved management-strategy assignment.
    """
    primary = _normalized_owner(pair_primary_strategy) or STRATEGY_A
    historical_owner = _normalized_owner(existing_owner)
    signals = strategy_signals if isinstance(strategy_signals, Mapping) else {}
    strategy_a = signals.get("strategy_a") if isinstance(signals.get("strategy_a"), Mapping) else {}
    strategy_b = signals.get("strategy_b") if isinstance(signals.get("strategy_b"), Mapping) else {}
    active = {
        STRATEGY_A: bool(strategy_a.get("buy_trigger")),
        STRATEGY_B: bool(strategy_b.get("buy_eligible")),
    }
    primary_active = active.get(primary, False)
    shadow_active = sorted(name for name, triggered in active.items() if name != primary and triggered)

    if historical_owner and historical_owner != primary:
        source = "PAIR_PRIMARY_PROMOTION_OVERRIDES_HISTORICAL_ENTRY_OWNER"
    elif historical_owner:
        source = "EXISTING_ENTRY_OWNER_MATCHES_PAIR_PRIMARY"
    else:
        source = "PAIR_PRIMARY_ASSIGNMENT"

    return {
        "resolved": primary_active,
        "strategy_owner": primary if primary_active else None,
        "management_strategy": primary,
        "historical_entry_strategy": historical_owner,
        "eligible_strategies": [primary] if primary_active else [],
        "shadow_active_strategies": shadow_active,
        "reason": (
            "PAIR_PRIMARY_ENTRY_SIGNAL_ACTIVE"
            if primary_active
            else "PAIR_PRIMARY_ENTRY_SIGNAL_NOT_ACTIVE"
        ),
        "entry_allowed_by_ownership": primary_active,
        "ownership_source": source,
    }


def _strategy_a_exit_detail(signals: Mapping[str, Any]) -> dict[str, Any]:
    detail = signals.get("strategy_a") if isinstance(signals.get("strategy_a"), Mapping) else {}
    triggered = bool(detail.get("sell_trigger"))
    warning_active = bool(detail.get("exit_warning_active"))
    buffered = bool(detail.get("exit_buffered"))
    warning_reasons = list(detail.get("exit_warning_reasons") or [])
    return {
        "triggered": triggered,
        "sell_reasons": list(detail.get("sell_reasons") or []),
        "warning_active": warning_active,
        "buffered": buffered,
        "warning_reasons": warning_reasons,
    }


def _strategy_b_exit_detail(signals: Mapping[str, Any]) -> dict[str, Any]:
    detail = signals.get("strategy_b") if isinstance(signals.get("strategy_b"), Mapping) else {}
    triggered = bool(detail.get("sell_trigger"))
    reason = detail.get("sell_reason")
    return {
        "triggered": triggered,
        "sell_reasons": [reason] if reason else [],
    }


def legacy_unassigned_exit_signal(
    strategy_signals: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Conservatively manage a pre-ownership open position.

    The position is intentionally not assigned Strategy A or Strategy B. A normal
    technical sale is allowed only when *both* current strategies independently
    confirm SELL. One strategy deteriorating by itself becomes a buffered warning.
    This provides a deterministic bridge for legacy positions without rewriting
    historical ownership.
    """
    signals = strategy_signals if isinstance(strategy_signals, Mapping) else {}
    a = _strategy_a_exit_detail(signals)
    b = _strategy_b_exit_detail(signals)

    a_sell = bool(a["triggered"])
    b_sell = bool(b["triggered"])
    consensus_sell = a_sell and b_sell

    sell_reasons = []
    if consensus_sell:
        sell_reasons = list(dict.fromkeys(a["sell_reasons"] + b["sell_reasons"]))

    warning_reasons: list[str] = []
    if a["warning_active"]:
        warning_reasons.extend(a["warning_reasons"])
    if a_sell and not b_sell:
        warning_reasons.extend(a["sell_reasons"])
    if b_sell and not a_sell:
        warning_reasons.extend(b["sell_reasons"])
    warning_reasons = list(dict.fromkeys(str(item) for item in warning_reasons if item))
    warning_active = bool(warning_reasons) and not consensus_sell

    return {
        "strategy_owner": LEGACY_UNASSIGNED,
        "sell_trigger": consensus_sell,
        "sell_reasons": sell_reasons,
        "exit_warning_active": warning_active,
        "exit_buffered": warning_active,
        "exit_warning_reasons": warning_reasons,
        "exit_state": "SELL_CONFIRMED" if consensus_sell else ("WARNING_BUFFERED" if warning_active else "HOLD"),
        "reason": (
            "LEGACY_UNASSIGNED_A_B_EXIT_CONSENSUS"
            if consensus_sell
            else "LEGACY_UNASSIGNED_WAIT_FOR_A_B_EXIT_CONSENSUS"
        ),
        "legacy_management_policy": "REQUIRE_STRATEGY_A_AND_B_SELL_CONSENSUS",
        "strategy_a_sell_trigger": a_sell,
        "strategy_b_sell_trigger": b_sell,
    }


def owned_exit_signal(
    strategy_signals: Mapping[str, Any] | None,
    strategy_owner: str | None,
) -> dict[str, Any]:
    """Return only the exit authority belonging to the position's owner.

    Strategy A warning/buffer evidence is intentionally preserved even when the
    final sell trigger is false so downstream paper state and AI CIO reporting can
    distinguish a fast momentum warning from a confirmed exit.

    LEGACY_UNASSIGNED is an explicit compatibility state for positions opened
    before ownership existed. It invokes the conservative A+B consensus policy.
    An actually missing/unknown owner still fails closed.
    """
    raw_owner = _raw_owner(strategy_owner)
    signals = strategy_signals if isinstance(strategy_signals, Mapping) else {}

    if raw_owner == LEGACY_UNASSIGNED:
        return legacy_unassigned_exit_signal(signals)

    owner = _normalized_owner(strategy_owner)
    if owner == STRATEGY_A:
        detail = _strategy_a_exit_detail(signals)
        triggered = bool(detail["triggered"])
        warning_active = bool(detail["warning_active"])
        return {
            "strategy_owner": owner,
            "sell_trigger": triggered,
            "sell_reasons": detail["sell_reasons"],
            "exit_warning_active": warning_active,
            "exit_buffered": bool(detail["buffered"]),
            "exit_warning_reasons": detail["warning_reasons"],
            "exit_state": "SELL_CONFIRMED" if triggered else ("WARNING_BUFFERED" if warning_active else "HOLD"),
            "reason": "STRATEGY_A_EXIT_AUTHORITY",
        }

    if owner == STRATEGY_B:
        detail = _strategy_b_exit_detail(signals)
        triggered = bool(detail["triggered"])
        return {
            "strategy_owner": owner,
            "sell_trigger": triggered,
            "sell_reasons": detail["sell_reasons"],
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
