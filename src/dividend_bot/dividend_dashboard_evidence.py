"""Build strategy-scoped DIVIDEND-001 dashboard evidence from paper-only artifacts.

This module is read-only/reporting-only. It normalizes the Dividend Bot's existing
paper state, candidate discovery, trade history, market snapshot, and performance
evidence into the fields consumed by the Enterprise strategy workspace. It never
changes allocations, moves capital, contacts a broker, or places orders.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping

from .dividend_position_analytics import (
    enrich_holdings_with_position_analytics,
    total_unrealized_pnl,
)

STRATEGY_ID = "DIVIDEND-001"
PAPER_TRADE_MODE = True
REPORTING_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
AUTOMATIC_ACTIVATION_ALLOWED = False


def _number(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except (OSError, UnicodeError, csv.Error):
        return []


def _pair_symbols(pair: str) -> tuple[str, str]:
    parts = [item.strip().upper() for item in str(pair).split("/")]
    if len(parts) >= 2:
        return parts[0], parts[1]
    symbol = parts[0] if parts else "UNKNOWN"
    return symbol, symbol


def _holdings_from_state(state: Mapping[str, Any]) -> tuple[list[dict[str, Any]], float, float]:
    holdings: list[dict[str, Any]] = []
    portfolio_value = 0.0
    total_income = 0.0
    total_sgov = 0.0

    pairs = state.get("pairs")
    if not isinstance(pairs, Mapping):
        return holdings, portfolio_value, total_income

    for pair_name, raw_entry in pairs.items():
        if not isinstance(raw_entry, Mapping):
            continue
        symbol_a, symbol_b = _pair_symbols(str(pair_name))
        prices = raw_entry.get("last_prices") if isinstance(raw_entry.get("last_prices"), Mapping) else {}
        for sleeve, symbol in (("A", symbol_a), ("B", symbol_b)):
            shares = _number(raw_entry.get(f"{sleeve.lower()}_shares"), 0.0) or 0.0
            price = _number(prices.get(sleeve), 0.0) or 0.0
            market_value = shares * price
            if shares > 0 and market_value > 0:
                holdings.append({
                    "symbol": symbol,
                    "pair": str(pair_name),
                    "sleeve": sleeve,
                    "shares": round(shares, 10),
                    "price": round(price, 6),
                    "market_value": round(market_value, 2),
                    "position_status": "OPEN",
                    "source": "paper_state.json",
                })
                portfolio_value += market_value

        sgov_value = _number(raw_entry.get("sgov_balance"), 0.0) or 0.0
        total_sgov += max(0.0, sgov_value)
        total_income += _number(raw_entry.get("total_dividends_received"), 0.0) or 0.0

    if total_sgov > 0:
        holdings.append({
            "symbol": "SGOV",
            "pair": "CASH RESERVE",
            "sleeve": "RESERVE",
            "shares": None,
            "price": None,
            "market_value": round(total_sgov, 2),
            "position_status": "PARKED",
            "source": "paper_state.json",
        })
        portfolio_value += total_sgov

    holdings.sort(key=lambda row: (str(row.get("symbol")), str(row.get("sleeve"))))
    return holdings, round(portfolio_value, 2), round(total_income, 2)


def _watchlist_from_candidates(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("candidates")
    if not isinstance(rows, list):
        return []
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping) or row.get("on_watchlist") is not True:
            continue
        result.append({
            "symbol": str(row.get("symbol") or row.get("candidate_id") or "UNKNOWN"),
            "status": row.get("status"),
            "currently_held": bool(row.get("currently_held", False)),
            "market_data_stale": bool(row.get("market_data_stale", False)),
            "sources": list(row.get("sources", [])) if isinstance(row.get("sources"), list) else [],
        })
    return result


def _income_events(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in rows:
        action = str(row.get("Action") or "").strip().upper()
        if action != "PAPER_DIVIDEND_RECEIVED":
            continue
        events.append({
            "date": row.get("Date"),
            "symbol": row.get("Ticker") or row.get("Pair") or "DIVIDEND",
            "pair": row.get("Pair"),
            "amount": round(_number(row.get("Paper_Value"), 0.0) or 0.0, 2),
            "event_type": "DIVIDEND_RECEIVED",
            "source": "paper_trade_log.csv",
        })
    return events[-50:]


def _alerts(
    *,
    state: Mapping[str, Any],
    candidate_payload: Mapping[str, Any],
    performance: Mapping[str, Any],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    pairs = state.get("pairs")
    if isinstance(pairs, Mapping):
        for pair_name, entry in pairs.items():
            if not isinstance(entry, Mapping):
                continue
            for sleeve in ("a", "b"):
                if entry.get(f"{sleeve}_earnings_lock") is True:
                    alerts.append({
                        "alert_type": "EARNINGS_LOCK",
                        "pair": str(pair_name),
                        "sleeve": sleeve.upper(),
                        "severity": "WARNING",
                        "status": "ACTIVE",
                    })
    for warning in candidate_payload.get("warnings", []) if isinstance(candidate_payload.get("warnings"), list) else []:
        alerts.append({"alert_type": "DISCOVERY_WARNING", "severity": "WARNING", "message": str(warning), "status": "ACTIVE"})
    for warning in performance.get("warnings", []) if isinstance(performance.get("warnings"), list) else []:
        alerts.append({"alert_type": "PERFORMANCE_WARNING", "severity": "INFO", "message": str(warning), "status": "ACTIVE"})
    return alerts[:100]


def build_dividend_dashboard_evidence(root_dir: str | Path = ".") -> dict[str, Any]:
    root = Path(root_dir)
    state = _read_json(root / "paper_state.json")
    state = state if isinstance(state, Mapping) else {}
    candidate_payload = _read_json(root / "candidate_discovery.json")
    candidate_payload = candidate_payload if isinstance(candidate_payload, Mapping) else {}
    performance = _read_json(root / "results" / "dividend_paper_trade_performance.json")
    performance = performance if isinstance(performance, Mapping) else {}
    market_snapshot = _read_json(root / "market_data_snapshot.json")
    log_rows = _read_csv(root / "paper_trade_log.csv")

    holdings, portfolio_value, state_income = _holdings_from_state(state)
    holdings = enrich_holdings_with_position_analytics(holdings, log_rows, market_snapshot)
    watchlist = _watchlist_from_candidates(candidate_payload)
    income_events = _income_events(log_rows)
    realized_gain = round(sum(_number(item.get("pnl"), 0.0) or 0.0 for item in performance.get("closed_trades", []) if isinstance(item, Mapping)), 2) if isinstance(performance.get("closed_trades"), list) else None
    unrealized_gain = total_unrealized_pnl(holdings)

    return {
        "strategy_id": STRATEGY_ID,
        "portfolio_value": portfolio_value if holdings else None,
        "position_count": len(holdings),
        "holdings": holdings,
        "positions": holdings,
        "watchlist_count": len(watchlist),
        "watchlist": watchlist,
        "income": state_income,
        "income_events": income_events,
        "realized_gain": realized_gain,
        "unrealized_gain": unrealized_gain,
        "alerts": _alerts(state=state, candidate_payload=candidate_payload, performance=performance),
        "risk_flags": _alerts(state=state, candidate_payload=candidate_payload, performance=performance),
        "performance_detail": {
            "trade_count": performance.get("trade_count"),
            "closed_trade_count": performance.get("closed_trade_count"),
            "open_trade_count": performance.get("open_trade_count"),
            "win_count": performance.get("win_count"),
            "loss_count": performance.get("loss_count"),
            "flat_count": performance.get("flat_count"),
            "win_rate_percent": performance.get("win_rate_percent"),
            "closed_trades": list(performance.get("closed_trades", [])) if isinstance(performance.get("closed_trades"), list) else [],
            "open_trades": list(performance.get("open_trades", [])) if isinstance(performance.get("open_trades"), list) else [],
        },
        "evidence_sources": [
            path for path in (
                "paper_state.json" if (root / "paper_state.json").is_file() else None,
                "paper_trade_log.csv" if (root / "paper_trade_log.csv").is_file() else None,
                "candidate_discovery.json" if (root / "candidate_discovery.json").is_file() else None,
                "market_data_snapshot.json" if (root / "market_data_snapshot.json").is_file() else None,
                "results/dividend_paper_trade_performance.json" if (root / "results" / "dividend_paper_trade_performance.json").is_file() else None,
            ) if path is not None
        ],
        "paper_trade_mode": True,
        "reporting_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "order_placement_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
        "investor_governance_required": True,
    }
