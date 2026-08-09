"""Fail-closed paper entry gate for the Dividend strategy.

Eligible-universe membership is not permission to invest. A new paper position
may leave SGOV only when strategy-owned watchlist/promotion evidence, technical
BUY evidence, and symbol-specific entry-quality evidence all agree. The module
is deterministic and read-only; it does not place orders or move real capital.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

MODULE_NAME = "dividend_entry_gate"
MODULE_VERSION = "1.1.0"
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
    if isinstance(value, bool): return None
    try: return float(value)
    except (TypeError, ValueError): return None


def _watchlist_row(watchlist_report: Mapping[str, Any] | None, symbol: str) -> Mapping[str, Any] | None:
    rows = watchlist_report.get("watchlist") if isinstance(watchlist_report, Mapping) else None
    if not isinstance(rows, list): return None
    target = symbol.upper()
    for row in rows:
        if isinstance(row, Mapping) and str(row.get("symbol") or "").strip().upper() == target:
            return row
    return None


def _entry_row(entry_score_report: Mapping[str, Any] | None, symbol: str) -> Mapping[str, Any] | None:
    """Prefer symbol-specific evidence while preserving the v1.0 global fallback."""
    if not isinstance(entry_score_report, Mapping): return None
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
) -> dict[str, Any]:
    """Return a fail-closed paper entry decision with explicit WAIT reasons."""
    symbol = str(symbol or "").strip().upper()
    technical_signal = str(technical_snapshot.get("signal") or technical_snapshot.get("Signal") or "UNKNOWN").upper()
    watch = _watchlist_row(watchlist_report, symbol)
    watch_status = str(watch.get("status") or watch.get("watchlist_status") or "").upper() if watch else None
    stale = watch.get("market_data_stale") if watch else None
    if stale not in (True, False): stale = None
    opportunity_score = _number(watch.get("opportunity_score")) if watch else None

    entry = _entry_row(entry_score_report, symbol)
    entry_status = None
    entry_score = None
    entry_reasons: list[str] = []
    entry_requirements: list[str] = []
    if isinstance(entry, Mapping):
        raw_status = entry.get("entry_status")
        entry_status = str(raw_status).upper() if raw_status not in (None, "") else None
        entry_score = _number(entry.get("entry_score"))
        if isinstance(entry.get("reasons"), list): entry_reasons = [str(item) for item in entry["reasons"] if str(item).strip()]
        if isinstance(entry.get("requirements_for_buy"), list): entry_requirements = [str(item) for item in entry["requirements_for_buy"] if str(item).strip()]

    reasons: list[str] = []
    if currently_held: reasons.append("ALREADY_HELD")
    if technical_signal != "BUY": reasons.append(f"TECHNICAL_SIGNAL_{technical_signal}")
    if watch is None:
        reasons.append("NOT_ON_STRATEGY_WATCHLIST")
    else:
        if watch_status not in APPROVED_WATCHLIST_STATUSES: reasons.append(f"WATCHLIST_NOT_PROMOTED_{watch_status or 'UNKNOWN'}")
        if stale is not False: reasons.append("MARKET_FRESHNESS_NOT_CONFIRMED")
        if bool(watch.get("currently_held")): reasons.append("WATCHLIST_MARKED_CURRENTLY_HELD")
    if entry is None:
        reasons.append("ENTRY_STATUS_NOT_APPROVED_MISSING")
    elif entry_status not in APPROVED_ENTRY_STATUSES:
        reasons.append(f"ENTRY_STATUS_NOT_APPROVED_{entry_status or 'MISSING'}")
    for reason in entry_reasons:
        if reason != "ENTRY_TECHNICAL_CONFIRMATION_COMPLETE":
            tagged = f"ENTRY_EVIDENCE_{reason}"
            if tagged not in reasons: reasons.append(tagged)

    approved = not reasons
    return EntryGateDecision(
        strategy_id=STRATEGY_ID, symbol=symbol, pair=str(pair), sleeve=str(sleeve),
        signal_symbol=str(signal_symbol).upper(), technical_signal=technical_signal,
        watchlist_status=watch_status, opportunity_score=opportunity_score,
        market_data_stale=stale, currently_held=bool(currently_held),
        entry_status=entry_status, entry_score=entry_score,
        final_decision="BUY_APPROVED" if approved else "WAIT_IN_SGOV", approved=approved,
        reasons=tuple(reasons), technical_snapshot=technical_snapshot,
        entry_requirements=tuple(entry_requirements), entry_reasons=tuple(entry_reasons),
    ).to_dict()


def evaluate_pair_entry_gate(
    *, pair: str, config: Mapping[str, Any], technical_snapshot: Mapping[str, Any],
    watchlist_report: Mapping[str, Any] | None, entry_score_report: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Require both sleeves of a pair-managed position to be independently ready."""
    decisions = []
    for side in ("A", "B"):
        key = side.lower()
        decisions.append(evaluate_entry_gate(
            symbol=str(config[key]), pair=pair, sleeve=side,
            signal_symbol=str(config.get(f"{key}_signal") or config[key]),
            technical_snapshot=technical_snapshot, watchlist_report=watchlist_report,
            entry_score_report=entry_score_report, currently_held=False,
        ))
    approved = all(item["approved"] for item in decisions)
    reasons = sorted({reason for item in decisions for reason in item["reasons"]})
    requirements = sorted({reason for item in decisions for reason in item.get("entry_requirements", [])})
    return {
        "strategy_id": STRATEGY_ID, "pair": pair, "architecture": str(config.get("architecture") or ""),
        "approved": approved, "final_decision": "BUY_APPROVED" if approved else "WAIT_IN_SGOV",
        "reasons": reasons, "requirements_for_buy": requirements, "sleeves": decisions,
        "paper_trade_mode": True, "live_trading_enabled": False,
        "broker_execution_enabled": False, "order_placement_enabled": False,
    }
