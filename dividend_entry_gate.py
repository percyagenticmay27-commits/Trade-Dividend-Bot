"""Fail-closed paper entry gate for the Dividend strategy.

Eligible-universe membership is not permission to invest. A new paper position
may leave SGOV only when strategy-owned watchlist/promotion evidence and
symbol-specific entry evidence agree. Legacy technical BUY evidence remains a
fallback for old Entry Score payloads; Strategy A/B evidence is authoritative
when the new strategy-entry fields are present.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from src.dividend_bot.dividend_strategy_ownership import resolve_strategy_ownership

MODULE_NAME = "dividend_entry_gate"
MODULE_VERSION = "1.2.0"
STRATEGY_ID = "DIVIDEND-001"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
APPROVED_ENTRY_STATUSES = {"GOOD_ENTRY", "STRONG_ENTRY"}
APPROVED_WATCHLIST_STATUSES = {"READY", "PROMOTED"}


@dataclass(frozen=True)
class EntryGateDecision:
    strategy_id: str
    symbol: str
    pair: str
    sleeve: str
    signal_symbol: str
    technical_signal: str
    watchlist_status: str | None
    opportunity_score: float | None
    market_data_stale: bool | None
    currently_held: bool
    entry_status: str | None
    entry_score: float | None
    final_decision: str
    approved: bool
    reasons: tuple[str, ...]
    technical_snapshot: Mapping[str, Any]
    entry_requirements: tuple[str, ...] = ()
    entry_reasons: tuple[str, ...] = ()
    strategy_entry_approved: bool | None = None
    strategy_owner: str | None = None
    strategy_ownership_reason: str | None = None
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False
    order_placement_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reasons"] = list(self.reasons)
        payload["entry_requirements"] = list(self.entry_requirements)
        payload["entry_reasons"] = list(self.entry_reasons)
        payload["technical_snapshot"] = dict(self.technical_snapshot)
        return payload


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _watchlist_row(watchlist_report: Mapping[str, Any] | None, symbol: str) -> Mapping[str, Any] | None:
    rows = watchlist_report.get("watchlist") if isinstance(watchlist_report, Mapping) else None
    if not isinstance(rows, list):
        return None
    target = symbol.upper()
    for row in rows:
        if isinstance(row, Mapping) and str(row.get("symbol") or "").strip().upper() == target:
            return row
    return None


def _entry_row(entry_score_report: Mapping[str, Any] | None, symbol: str) -> Mapping[str, Any] | None:
    """Prefer symbol-specific evidence while preserving the v1.0 global fallback."""
    if not isinstance(entry_score_report, Mapping):
        return None
    rows = entry_score_report.get("entries")
    if isinstance(rows, list):
        target = symbol.upper()
        for row in rows:
            if isinstance(row, Mapping) and str(row.get("symbol") or "").strip().upper() == target:
                return row
        if entry_score_report.get("symbol_specific"):
            return None
    return entry_score_report


def evaluate_entry_gate(
    *, symbol: str, pair: str, sleeve: str, signal_symbol: str,
    technical_snapshot: Mapping[str, Any], watchlist_report: Mapping[str, Any] | None,
    entry_score_report: Mapping[str, Any] | None, currently_held: bool = False,
    pair_primary_strategy: str = "STRATEGY_A",
) -> dict[str, Any]:
    """Return a fail-closed paper entry decision with explicit WAIT reasons."""
    symbol = str(symbol or "").strip().upper()
    legacy_technical_signal = str(
        technical_snapshot.get("signal") or technical_snapshot.get("Signal") or "UNKNOWN"
    ).upper()
    watch = _watchlist_row(watchlist_report, symbol)
    watch_status = str(watch.get("status") or watch.get("watchlist_status") or "").upper() if watch else None
    stale = watch.get("market_data_stale") if watch else None
    if stale not in (True, False):
        stale = None
    opportunity_score = _number(watch.get("opportunity_score")) if watch else None

    entry = _entry_row(entry_score_report, symbol)
    entry_status = None
    entry_score = None
    entry_reasons: list[str] = []
    entry_requirements: list[str] = []
    strategy_entry_approved: bool | None = None
    strategy_owner: str | None = None
    strategy_ownership_reason: str | None = None

    if isinstance(entry, Mapping):
        raw_status = entry.get("entry_status")
        entry_status = str(raw_status).upper() if raw_status not in (None, "") else None
        entry_score = _number(entry.get("entry_score"))
        if isinstance(entry.get("reasons"), list):
            entry_reasons = [str(item) for item in entry["reasons"] if str(item).strip()]
        if isinstance(entry.get("requirements_for_buy"), list):
            entry_requirements = [str(item) for item in entry["requirements_for_buy"] if str(item).strip()]
        if entry.get("strategy_entry_approved") in (True, False):
            strategy_entry_approved = bool(entry.get("strategy_entry_approved"))
        ownership = entry.get("strategy_ownership")
        if isinstance(ownership, Mapping):
            raw_owner = ownership.get("strategy_owner")
            strategy_owner = str(raw_owner).upper() if raw_owner not in (None, "") else None
            raw_reason = ownership.get("reason")
            strategy_ownership_reason = str(raw_reason) if raw_reason not in (None, "") else None

        strategy_signals = entry.get("strategy_signals")
        if isinstance(strategy_signals, Mapping):
            assigned = resolve_strategy_ownership(
                strategy_signals,
                pair_primary_strategy=pair_primary_strategy,
            )
            strategy_entry_approved = bool(assigned.get("entry_allowed_by_ownership"))
            strategy_owner = assigned.get("strategy_owner")
            strategy_ownership_reason = str(assigned.get("reason") or "")
    # New Strategy A/B evidence owns the technical BUY authority. Legacy signal
    # remains authoritative only for older payloads that do not publish the new
    # explicit strategy_entry_approved field.
    if strategy_entry_approved is True:
        technical_signal = "BUY"
    elif strategy_entry_approved is False:
        technical_signal = "HOLD"
    else:
        technical_signal = legacy_technical_signal

    reasons: list[str] = []
    if currently_held:
        reasons.append("ALREADY_HELD")
    if technical_signal != "BUY":
        reasons.append(f"TECHNICAL_SIGNAL_{technical_signal}")
    if watch is None:
        reasons.append("NOT_ON_STRATEGY_WATCHLIST")
    else:
        if watch_status not in APPROVED_WATCHLIST_STATUSES:
            reasons.append(f"WATCHLIST_NOT_PROMOTED_{watch_status or 'UNKNOWN'}")
        if stale is not False:
            reasons.append("MARKET_FRESHNESS_NOT_CONFIRMED")
        if bool(watch.get("currently_held")):
            reasons.append("WATCHLIST_MARKED_CURRENTLY_HELD")

    if entry is None:
        reasons.append("ENTRY_STATUS_NOT_APPROVED_MISSING")
    elif strategy_entry_approved is not None:
        if strategy_entry_approved is not True:
            reason = strategy_ownership_reason or "STRATEGY_ENTRY_NOT_APPROVED"
            tagged = f"STRATEGY_OWNERSHIP_{reason}"
            if tagged not in reasons:
                reasons.append(tagged)
    elif entry_status not in APPROVED_ENTRY_STATUSES:
        reasons.append(f"ENTRY_STATUS_NOT_APPROVED_{entry_status or 'MISSING'}")

    # Entry status remains an audit consistency check for new payloads. A
    # strategy-owned approved entry should publish GOOD/STRONG; inconsistent
    # evidence fails closed rather than being silently accepted.
    if strategy_entry_approved is True and entry_status not in APPROVED_ENTRY_STATUSES:
        reasons.append(f"ENTRY_STATUS_INCONSISTENT_{entry_status or 'MISSING'}")

    for reason in entry_reasons:
        if reason not in {"ENTRY_TECHNICAL_CONFIRMATION_COMPLETE", "STRATEGY_ENTRY_TRIGGER_ACTIVE"}:
            tagged = f"ENTRY_EVIDENCE_{reason}"
            if tagged not in reasons:
                reasons.append(tagged)

    approved = not reasons
    return EntryGateDecision(
        strategy_id=STRATEGY_ID,
        symbol=symbol,
        pair=str(pair),
        sleeve=str(sleeve),
        signal_symbol=str(signal_symbol).upper(),
        technical_signal=technical_signal,
        watchlist_status=watch_status,
        opportunity_score=opportunity_score,
        market_data_stale=stale,
        currently_held=bool(currently_held),
        entry_status=entry_status,
        entry_score=entry_score,
        final_decision="BUY_APPROVED" if approved else "WAIT_IN_SGOV",
        approved=approved,
        reasons=tuple(reasons),
        technical_snapshot={
            **dict(technical_snapshot),
            "pair_primary_strategy": pair_primary_strategy,
            "legacy_signal": legacy_technical_signal,
            "entry_authority": "STRATEGY_A_B" if strategy_entry_approved is not None else "LEGACY_TECHNICAL_SIGNAL",
        },
        entry_requirements=tuple(entry_requirements),
        entry_reasons=tuple(entry_reasons),
        strategy_entry_approved=strategy_entry_approved,
        strategy_owner=strategy_owner,
        strategy_ownership_reason=strategy_ownership_reason,
    ).to_dict()


def evaluate_pair_entry_gate(
    *, pair: str, config: Mapping[str, Any], technical_snapshot: Mapping[str, Any],
    watchlist_report: Mapping[str, Any] | None, entry_score_report: Mapping[str, Any] | None,
    pair_primary_strategy: str = "STRATEGY_A",
) -> dict[str, Any]:
    """Require both sleeves of a pair-managed position to be independently ready."""
    decisions = []
    for side in ("A", "B"):
        key = side.lower()
        decisions.append(evaluate_entry_gate(
            symbol=str(config[key]),
            pair=pair,
            sleeve=side,
            signal_symbol=str(config.get(f"{key}_signal") or config[key]),
            technical_snapshot=technical_snapshot,
            watchlist_report=watchlist_report,
            entry_score_report=entry_score_report,
            currently_held=False,
            pair_primary_strategy=pair_primary_strategy,
        ))
    approved = all(item["approved"] for item in decisions)
    reasons = sorted({reason for item in decisions for reason in item["reasons"]})
    requirements = sorted({reason for item in decisions for reason in item.get("entry_requirements", [])})
    owners = sorted({item.get("strategy_owner") for item in decisions if item.get("strategy_owner")})
    return {
        "strategy_id": STRATEGY_ID,
        "pair": pair,
        "architecture": str(config.get("architecture") or ""),
        "approved": approved,
        "final_decision": "BUY_APPROVED" if approved else "WAIT_IN_SGOV",
        "reasons": reasons,
        "requirements_for_buy": requirements,
        "strategy_owners": owners,
        "sleeves": decisions,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "order_placement_enabled": False,
    }
