"""Build DIVIDEND-001 realized paper-trade performance from the operational log.

This module is reporting-only. It reconstructs closed paper round trips from the
existing paper_trade_log.csv and publishes an explicit service-level win rate for
Enterprise KPI consumption. No orders, broker calls, allocations, or policy
changes are performed.
"""
from __future__ import annotations

import csv
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

MODULE_NAME = "dividend_paper_trade_performance"
MODULE_VERSION = "1.1.0"
SCHEMA_VERSION = "1.0"
STRATEGY_ID = "DIVIDEND-001"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
AUTOMATIC_ACTIVATION_ALLOWED = False
REPORTING_ONLY = True

DEFAULT_LOG_PATH = Path("paper_trade_log.csv")
DEFAULT_OUTPUT_PATH = Path("results/dividend_paper_trade_performance.json")
ENTRY_ACTIONS = {"PAPER_BUY_OPEN", "PAPER_BUY_FROM_SGOV"}
EXIT_ACTIONS = {"PAPER_SELL_TO_SGOV"}
DIVIDEND_ACTION = "PAPER_DIVIDEND_RECEIVED"


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _positive_number(value: Any) -> float | None:
    number = _number(value, 0.0)
    return number if number > 0 else None


def _load_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _entry_cost_for_exit(trade: Mapping[str, Any], exit_shares: float | None) -> tuple[float, str]:
    """Return the economic cost basis for the shares that were actually sold.

    Enterprise allocation normalization scales paper-state share quantities without
    rewriting historical trade rows. When the exit row therefore contains more
    shares than the original entry row, use the entry's per-share cost to scale the
    cost basis to the sold quantity. If share evidence is unavailable, preserve the
    legacy recorded-entry-value behavior rather than fabricating a scale factor.
    """
    recorded_entry_value = float(trade.get("recorded_entry_value") or 0.0)
    entry_shares = _positive_number(trade.get("entry_shares"))
    if entry_shares is None or exit_shares is None:
        return recorded_entry_value, "RECORDED_ENTRY_VALUE"
    unit_cost = recorded_entry_value / entry_shares
    return unit_cost * exit_shares, "ENTRY_UNIT_COST_X_EXIT_SHARES"


def build_dividend_paper_trade_performance(
    rows: list[Mapping[str, Any]],
    *,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Reconstruct closed sleeve round trips and calculate realized win rate.

    A round trip begins with PAPER_BUY_OPEN or PAPER_BUY_FROM_SGOV and closes on
    the next PAPER_SELL_TO_SGOV for the same Pair + Sleeve + Ticker. Dividend
    cash logged for a pair is split equally between its A/B sleeves, matching the
    operational paper engine's 50/50 reinvestment rule, and is credited to an
    open round trip before classifying WIN/LOSS/FLAT.

    Historical entry rows can predate an Enterprise paper-allocation resize. The
    resize intentionally does not rewrite the ledger, so a later exit can contain
    proportionally more shares. Realized P/L therefore uses entry cost per share
    multiplied by the actual exit shares when both share quantities are reported.
    """
    open_trades: dict[tuple[str, str, str], dict[str, Any]] = {}
    closed: list[dict[str, Any]] = []
    warnings: list[str] = []

    for raw in rows:
        pair = str(raw.get("Pair") or "").strip()
        sleeve = str(raw.get("Sleeve") or "").strip().upper()
        ticker = str(raw.get("Ticker") or "").strip().upper()
        action = str(raw.get("Action") or "").strip().upper()
        date = str(raw.get("Date") or "").strip()
        value = max(0.0, _number(raw.get("Paper_Value"), 0.0))
        shares = _positive_number(raw.get("Shares"))
        price = _positive_number(raw.get("Price"))
        key = (pair, sleeve, ticker)

        if action in ENTRY_ACTIONS and pair and sleeve and ticker and ticker != "SGOV":
            if key in open_trades:
                warnings.append(
                    f"Duplicate open ignored for {pair} {sleeve} {ticker} on {date}."
                )
                continue
            open_trades[key] = {
                "pair": pair,
                "sleeve": sleeve,
                "symbol": ticker,
                "entry_date": date,
                "recorded_entry_value": value,
                "entry_value": value,
                "entry_shares": shares,
                "entry_price": price,
                "income_received": 0.0,
            }
            continue

        if action == DIVIDEND_ACTION and pair and value > 0:
            share = value / 2.0
            for open_key, trade in open_trades.items():
                if open_key[0] == pair:
                    trade["income_received"] += share
            continue

        if action in EXIT_ACTIONS and key in open_trades:
            trade = open_trades.pop(key)
            entry_value, cost_basis_method = _entry_cost_for_exit(trade, shares)
            income = float(trade["income_received"])
            realized_value = value + income
            pnl = realized_value - entry_value
            if pnl > 1e-9:
                outcome = "WIN"
            elif pnl < -1e-9:
                outcome = "LOSS"
            else:
                outcome = "FLAT"
            return_pct = ((realized_value / entry_value) - 1.0) * 100.0 if entry_value > 0 else 0.0
            closed.append({
                **trade,
                "entry_value": round(entry_value, 6),
                "cost_basis_method": cost_basis_method,
                "exit_date": date,
                "exit_shares": shares,
                "exit_price": price,
                "exit_value": round(value, 6),
                "realized_value": round(realized_value, 6),
                "pnl": round(pnl, 6),
                "total_return_pct": round(return_pct, 4),
                "outcome": outcome,
            })

    win_count = sum(item["outcome"] == "WIN" for item in closed)
    loss_count = sum(item["outcome"] == "LOSS" for item in closed)
    flat_count = sum(item["outcome"] == "FLAT" for item in closed)
    closed_count = len(closed)
    win_rate = round((win_count / closed_count) * 100.0, 2) if closed_count else None

    return {
        "schema_version": SCHEMA_VERSION,
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "generated_at_utc": generated_at_utc or _now_utc(),
        "strategy_id": STRATEGY_ID,
        "trade_count": closed_count + len(open_trades),
        "closed_trade_count": closed_count,
        "open_trade_count": len(open_trades),
        "win_count": win_count,
        "loss_count": loss_count,
        "flat_count": flat_count,
        "win_rate_percent": win_rate,
        "closed_trades": closed,
        "open_trades": list(open_trades.values()),
        "realized_cost_basis_policy": "ENTRY_UNIT_COST_X_EXIT_SHARES_WHEN_AVAILABLE",
        "evidence_status": "AVAILABLE" if closed_count else "INSUFFICIENT_DATA",
        "warnings": warnings + ([] if closed_count else ["No closed Dividend paper round trips are available for realized win rate."]),
        "paper_trade_mode": True,
        "reporting_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "order_placement_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
        "investor_governance_required": True,
    }


def _atomic_write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return path


def write_dividend_paper_trade_performance(
    root_dir: str | Path = ".",
    *,
    log_path: str | Path = DEFAULT_LOG_PATH,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    root = Path(root_dir)
    source = Path(log_path)
    if not source.is_absolute():
        source = root / source
    target = Path(output_path)
    if not target.is_absolute():
        target = root / target
    report = build_dividend_paper_trade_performance(_load_rows(source))
    return _atomic_write(target, json.dumps(report, indent=2, sort_keys=True) + "\n")
