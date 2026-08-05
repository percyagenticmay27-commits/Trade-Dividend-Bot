"""Generate fresh daily CSV exports for the Dividend paper strategy."""
from __future__ import annotations

import csv
import json
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

MODULE_NAME = "daily_dividend_csv_exports"
MODULE_VERSION = "1.0.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False

DEFAULT_STATE_PATH = Path("paper_portfolio_state.json")
DEFAULT_OUTPUT_DIR = Path("results/daily_dividend_csv")
DEFAULT_MAX_STATE_AGE_DAYS = 5

EXECUTIVE_SUMMARY_FILE = "dividend_executive_summary.csv"
PORTFOLIO_FILE = "dividend_portfolio.csv"
WATCHLIST_FILE = "dividend_watchlist.csv"


def _atomic_write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _parse_state_date(state: Mapping[str, Any]) -> date:
    raw = str(state.get("as_of_date") or state.get("last_processed_date") or "").strip()
    if not raw:
        raise RuntimeError("Dividend paper state has no as_of_date or last_processed_date")
    return date.fromisoformat(raw[:10])


def _validate_fresh_state(state: Mapping[str, Any], *, today: date, max_age_days: int) -> date:
    state_date = _parse_state_date(state)
    age_days = (today - state_date).days
    if age_days < 0:
        raise RuntimeError(f"Dividend paper state date is in the future: {state_date.isoformat()}")
    if age_days > max_age_days:
        raise RuntimeError(
            f"Dividend paper state is stale: {state_date.isoformat()} is {age_days} days old "
            f"(maximum {max_age_days})"
        )
    return state_date


def _number(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _text_map(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _portfolio_rows(state: Mapping[str, Any], state_date: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pairs = _text_map(state.get("pairs"))
    for pair_name in sorted(pairs):
        entry = _text_map(pairs[pair_name])
        prices = _text_map(entry.get("last_prices"))
        signals = _text_map(entry.get("last_signal"))
        a_shares = _number(entry.get("a_shares"))
        b_shares = _number(entry.get("b_shares"))
        a_price = _number(prices.get("A"))
        b_price = _number(prices.get("B"))
        a_value = a_shares * a_price
        b_value = b_shares * b_price
        sgov = _number(entry.get("sgov_balance"))
        rows.append({
            "as_of_date": state_date.isoformat(),
            "pair": pair_name,
            "a_shares": round(a_shares, 8),
            "a_current_price": round(a_price, 8),
            "a_market_value": round(a_value, 8),
            "a_signal": str(signals.get("A") or ""),
            "a_in_sgov": bool(entry.get("a_in_sgov", False)),
            "a_earnings_lock": bool(entry.get("a_earnings_lock", False)),
            "b_shares": round(b_shares, 8),
            "b_current_price": round(b_price, 8),
            "b_market_value": round(b_value, 8),
            "b_signal": str(signals.get("B") or ""),
            "b_in_sgov": bool(entry.get("b_in_sgov", False)),
            "b_earnings_lock": bool(entry.get("b_earnings_lock", False)),
            "sgov_balance": round(sgov, 8),
            "pair_total_value": round(a_value + b_value + sgov, 8),
            "total_dividends_received": round(_number(entry.get("total_dividends_received")), 8),
        })
    return rows


def _watchlist_rows(portfolio_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in portfolio_rows:
        for sleeve in ("a", "b"):
            signal = str(item[f"{sleeve}_signal"])
            in_sgov = bool(item[f"{sleeve}_in_sgov"])
            earnings_lock = bool(item[f"{sleeve}_earnings_lock"])
            if earnings_lock:
                action = "WAIT_POST_EARNINGS_BUY"
            elif signal == "BUY" and in_sgov:
                action = "REENTRY_WATCH"
            elif signal == "SELL" and not in_sgov:
                action = "EXIT_WATCH"
            elif in_sgov:
                action = "WAIT_FOR_BUY"
            else:
                action = "HOLD_MONITOR"
            rows.append({
                "as_of_date": item["as_of_date"],
                "pair": item["pair"],
                "sleeve": sleeve.upper(),
                "signal": signal,
                "current_price": item[f"{sleeve}_current_price"],
                "market_value": item[f"{sleeve}_market_value"],
                "in_sgov": in_sgov,
                "earnings_lock": earnings_lock,
                "watch_action": action,
            })
    return rows


def generate_daily_dividend_csv_exports(
    *,
    root_dir: str | Path = ".",
    state_path: str | Path = DEFAULT_STATE_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    now: datetime | None = None,
    max_state_age_days: int = DEFAULT_MAX_STATE_AGE_DAYS,
) -> list[Path]:
    root = Path(root_dir)
    state_file = root / Path(state_path)
    if not state_file.is_file():
        raise RuntimeError(f"Dividend paper state is missing: {state_file}")
    state = json.loads(state_file.read_text(encoding="utf-8"))
    current = now.astimezone(timezone.utc) if now is not None else datetime.now(timezone.utc)
    state_date = _validate_fresh_state(state, today=current.date(), max_age_days=max_state_age_days)
    portfolio_rows = _portfolio_rows(state, state_date)
    if not portfolio_rows:
        raise RuntimeError("Dividend paper state contains no portfolio pairs")
    watchlist_rows = _watchlist_rows(portfolio_rows)

    portfolio_value = sum(_number(row["pair_total_value"]) for row in portfolio_rows)
    etf_value = sum(_number(row["a_market_value"]) + _number(row["b_market_value"]) for row in portfolio_rows)
    sgov_value = sum(_number(row["sgov_balance"]) for row in portfolio_rows)
    dividends = sum(_number(row["total_dividends_received"]) for row in portfolio_rows)
    executive_rows = [{
        "as_of_date": state_date.isoformat(),
        "generated_at": current.isoformat(),
        "strategy": "DIVIDEND",
        "paper_trade_mode": True,
        "portfolio_value": round(portfolio_value, 8),
        "etf_exposure": round(etf_value, 8),
        "sgov_exposure": round(sgov_value, 8),
        "total_dividends_received": round(dividends, 8),
        "pair_count": len(portfolio_rows),
        "watchlist_item_count": len(watchlist_rows),
        "data_stale": False,
    }]

    destination = root / Path(output_dir)
    executive_path = destination / EXECUTIVE_SUMMARY_FILE
    portfolio_path = destination / PORTFOLIO_FILE
    watchlist_path = destination / WATCHLIST_FILE
    _atomic_write_csv(executive_path, list(executive_rows[0]), executive_rows)
    _atomic_write_csv(portfolio_path, list(portfolio_rows[0]), portfolio_rows)
    _atomic_write_csv(watchlist_path, list(watchlist_rows[0]), watchlist_rows)
    return [executive_path, portfolio_path, watchlist_path]
