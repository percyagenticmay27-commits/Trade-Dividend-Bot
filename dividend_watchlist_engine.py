"""Evidence-driven Dividend watchlist promotion engine.

This module converts ranked, non-held Dividend candidates into an explicit
strategy-owned monitoring list. It is reporting-only and paper-only: it never
moves capital, places orders, or changes portfolio state.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

MODULE_NAME = "dividend_watchlist_engine"
MODULE_VERSION = "1.0.1"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
STRATEGY_ID = "DIVIDEND-001"

PAPER_TRADE_MODE = True
REPORTING_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
AUTOMATIC_ACTIVATION_ALLOWED = False

MIN_WATCHLIST_SCORE = 50.0
READY_SCORE = 80.0
MONITOR_SCORE = 65.0
MAX_WATCHLIST_SIZE = 10


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _pair_symbols(pair: str) -> tuple[str, str]:
    parts = [part.strip().upper() for part in str(pair).split("/") if part.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    if parts:
        return parts[0], parts[0]
    return "", ""


def _held_symbols(state: Mapping[str, Any]) -> set[str]:
    """Return invested symbols plus strategy-owned reserve assets.

    Reserve cash parked in SGOV is already deployed to the strategy's reserve
    sleeve and must not be promoted as a new watchlist opportunity simply because
    it has no share-count field in legacy paper_state.json.
    """
    held: set[str] = set()
    pairs = state.get("pairs")
    if not isinstance(pairs, Mapping):
        return held
    for pair_name, raw in pairs.items():
        if not isinstance(raw, Mapping):
            continue
        a, b = _pair_symbols(str(pair_name))
        a_shares = _number(raw.get("a_shares")) or 0.0
        b_shares = _number(raw.get("b_shares")) or 0.0
        if a and a_shares > 0:
            held.add(a)
        if b and b_shares > 0:
            held.add(b)
        sgov_balance = _number(raw.get("sgov_balance")) or 0.0
        if sgov_balance > 0:
            held.add("SGOV")
    return held


def _market_map(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    records = snapshot.get("records")
    if not isinstance(records, list):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for row in records:
        if not isinstance(row, Mapping):
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        if symbol:
            result[symbol] = row
    return result


def _first(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _market_name(row: Mapping[str, Any]) -> Any:
    direct = _first(row, "name", "security_name", "long_name", "short_name", "display_name")
    if direct is not None:
        return direct
    quote = row.get("quote")
    if isinstance(quote, Mapping):
        return _first(quote, "long_name", "short_name", "name", "display_name")
    return None


def _market_daily_change(row: Mapping[str, Any]) -> float | None:
    direct = _first(row, "daily_change_percent", "daily_change_pct", "change_percent", "percent_change")
    value = _number(direct)
    if value is not None:
        return round(value, 4)
    quote = row.get("quote")
    if isinstance(quote, Mapping):
        value = _number(_first(quote, "daily_change_percent", "daily_change_pct", "regular_market_change_percent"))
        if value is not None:
            return round(value, 4)
    return None


def _status_for_score(score: float) -> str:
    if score >= READY_SCORE:
        return "READY"
    if score >= MONITOR_SCORE:
        return "MONITOR"
    return "WATCH"


def build_dividend_watchlist(
    rankings: Mapping[str, Any],
    *,
    paper_state: Mapping[str, Any] | None = None,
    market_snapshot: Mapping[str, Any] | None = None,
    max_watchlist_size: int = MAX_WATCHLIST_SIZE,
) -> dict[str, Any]:
    """Build an explicit, ranked strategy watchlist from authoritative evidence."""
    raw_rankings = rankings.get("rankings") if isinstance(rankings, Mapping) else None
    rows = [row for row in raw_rankings if isinstance(row, Mapping)] if isinstance(raw_rankings, list) else []
    held = _held_symbols(paper_state or {})
    markets = _market_map(market_snapshot or {})

    candidates: list[dict[str, Any]] = []
    for ranking in rows:
        symbol = str(ranking.get("symbol") or "").strip().upper()
        if not symbol or symbol in held:
            continue
        score = _number(ranking.get("overall_score"))
        if score is None or score < MIN_WATCHLIST_SCORE:
            continue
        rating = str(ranking.get("overall_rating") or "").strip().upper()
        if rating == "AVOID":
            continue
        market = markets.get(symbol, {})
        stale = bool(market.get("is_stale")) if market else None
        if stale is True:
            continue
        candidates.append({
            "symbol": symbol,
            "name": _market_name(market) if market else None,
            "status": _status_for_score(score),
            "watchlist_status": _status_for_score(score),
            "currently_held": False,
            "market_data_stale": stale,
            "opportunity_score": round(score, 2),
            "overall_rating": rating or None,
            "quality_score": _number(ranking.get("quality_score")),
            "momentum_score": _number(ranking.get("momentum_score")),
            "growth_score": _number(ranking.get("growth_score")),
            "safety_score": _number(ranking.get("safety_score")),
            "valuation_score": _number(ranking.get("valuation_score")),
            "conviction_score": _number(ranking.get("conviction_score") or ranking.get("confidence")),
            "daily_change_percent": _market_daily_change(market) if market else None,
            "recommendation": ranking.get("recommendation"),
            "trend_direction": ranking.get("trend_direction"),
            "sources": ["DIVIDEND_RANKING", "MARKET_SNAPSHOT" if market else "DIVIDEND_RANKING"],
            "evidence": ["dividend_rankings.json"] + (["market_data_snapshot.json"] if market else []),
        })

    candidates.sort(key=lambda row: (-float(row["opportunity_score"]), str(row["symbol"])))
    candidates = candidates[: max(0, int(max_watchlist_size))]
    for index, row in enumerate(candidates, start=1):
        row["rank"] = index
        row["on_watchlist"] = True

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "generated_at_utc": _now(),
        "strategy_id": STRATEGY_ID,
        "paper_trade_mode": True,
        "reporting_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "order_placement_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
        "promotion_policy": {
            "minimum_watchlist_score": MIN_WATCHLIST_SCORE,
            "monitor_score": MONITOR_SCORE,
            "ready_score": READY_SCORE,
            "maximum_watchlist_size": max(0, int(max_watchlist_size)),
            "exclude_current_holdings": True,
            "exclude_reserve_assets": True,
            "exclude_stale_market_data": True,
        },
        "watchlist_count": len(candidates),
        "watchlist": candidates,
        "warnings": [] if candidates else ["No non-held ranked candidates currently meet the Dividend watchlist policy."],
        "errors": [],
    }


def format_watchlist_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Dividend Strategy Watchlist",
        "",
        f"- Strategy: {report.get('strategy_id', STRATEGY_ID)}",
        f"- Active candidates: {report.get('watchlist_count', 0)}",
        "",
        "| Rank | Symbol | Status | Opportunity | Momentum | Rating |",
        "|---:|---|---|---:|---:|---|",
    ]
    rows = report.get("watchlist") if isinstance(report.get("watchlist"), list) else []
    if not rows:
        lines.append("| - | None | - | - | - | - |")
    for row in rows:
        lines.append(
            f"| {row.get('rank')} | {row.get('symbol')} | {row.get('status')} | "
            f"{row.get('opportunity_score')} | {row.get('momentum_score')} | {row.get('overall_rating')} |"
        )
    return "\n".join(lines) + "\n"


def write_dividend_watchlist(root_path: str | Path = ".") -> dict[str, Any]:
    root = Path(root_path)
    rankings = _read_json(root / "dividend_rankings.json")
    state = _read_json(root / "paper_state.json")
    market = _read_json(root / "market_data_snapshot.json")
    report = build_dividend_watchlist(
        rankings if isinstance(rankings, Mapping) else {},
        paper_state=state if isinstance(state, Mapping) else {},
        market_snapshot=market if isinstance(market, Mapping) else {},
    )
    (root / "watchlist_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "watchlist_report.md").write_text(format_watchlist_markdown(report), encoding="utf-8")
    with (root / "watchlist_report.csv").open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["rank", "symbol", "name", "status", "opportunity_score", "momentum_score", "overall_rating", "market_data_stale"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in report["watchlist"]:
            writer.writerow({key: row.get(key) for key in fieldnames})
    return report


if __name__ == "__main__":
    result = write_dividend_watchlist()
    print(f"Dividend Watchlist: {result['watchlist_count']} active candidate(s)")
