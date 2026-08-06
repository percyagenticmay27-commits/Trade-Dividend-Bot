"""Build the executive Strategy Health Report from paper-only evidence.

The report preserves the complete portfolio-health presentation, adds a Current
Pair Legend, and shows pair performance history grouped by pair and ordered from
oldest to newest. Reporting only: no broker actions or capital movement.
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.dividend_bot.executive_daily_paper_report import build_daily_paper_rows
from src.dividend_bot.executive_reporting_framework import executive_framework_rows

MODULE_NAME = "executive_strategy_health_report"
MODULE_VERSION = "4.4.0"
PAPER_TRADE_MODE = True

STRATEGY_HEALTH_FIELDS = [
    "activity_date", "report_section", "metric", "value", "pair", "event",
    "state", "position_status", "stock_value", "sgov_value", "total_pair_value",
    "total_return_amount", "total_return_pct", "days_invested",
    "dividends_received", "health_status", "explanation", "paper_trade_mode",
]


def _blank(section: str, **values: Any) -> dict[str, Any]:
    row = {field: "" for field in STRATEGY_HEALTH_FIELDS}
    row["report_section"] = section
    row["paper_trade_mode"] = True
    row.update(values)
    return row


def _separator() -> dict[str, Any]:
    return {field: "" for field in STRATEGY_HEALTH_FIELDS}


def _money(value: Any) -> float:
    try:
        return float(str(value or "").replace("$", "").replace(",", "").strip())
    except ValueError:
        return 0.0


def _fmt_money(value: float) -> str:
    return f"${value:,.2f}"


def _fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def _health(return_pct: float, reconciled: bool) -> str:
    if not reconciled:
        return "REVIEW REQUIRED"
    if return_pct <= -10.0:
        return "AT RISK"
    if return_pct < 0.0:
        return "WATCH"
    return "HEALTHY"


def _load_log(root: Path) -> list[dict[str, str]]:
    path = root / "paper_trade_log.csv"
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _event_label(action: str) -> str:
    return {
        "PAPER_BUY_OPEN": "INVESTED",
        "PAPER_BUY_FROM_SGOV": "RE-INVESTED FROM SGOV",
        "PAPER_SELL_TO_SGOV": "MOVED INTO SGOV",
        "PAPER_PARK_IN_SGOV": "PARKED IN SGOV",
        "PAPER_DIVIDEND_RECEIVED": "DIVIDEND RECEIVED",
        "PAPER_EARNINGS_EXIT": "EARNINGS EXIT TO SGOV",
        "EARNINGS_EXIT": "EARNINGS EXIT TO SGOV",
    }.get(action, action.replace("_", " ") or "RECORDED ACTIVITY")


def _status(stock: float, sgov: float) -> str:
    if stock <= 0 and sgov > 0:
        return "MOVED INTO SGOV"
    if stock > 0 and sgov > 0:
        return "PARTIALLY INVESTED / PARTIALLY IN SGOV"
    if stock > 0:
        return "INVESTED"
    return "NO ACTIVE CAPITAL"


def build_strategy_health_rows(
    *, root_dir: str | Path, trading_date: date, generated_at: datetime | None = None
) -> list[dict[str, Any]]:
    root = Path(root_dir)
    paper_rows = build_daily_paper_rows(
        root_dir=root, trading_date=trading_date, generated_at=generated_at
    )

    rows: list[dict[str, Any]] = []
    for item in executive_framework_rows(
        source_name="strategy_health_report.md",
        trading_date=trading_date,
        generated_at=generated_at,
    ):
        rows.append(_blank(item["section"], metric=item["field"], value=item["value"]))

    rows.extend([
        _blank("What This Report Shows", metric="Purpose", value=(
            "Shows current Dividend Strategy health, current pair assignments, and the full chronological development of each pair."
        )),
        _blank("Why This Report Is Used", metric="Use", value=(
            "Lets the reader identify current holdings first, then trace each pair from its earliest recorded activity through its present state."
        )),
        _separator(),
    ])

    summary = {
        str(r.get("metric")): str(r.get("value"))
        for r in paper_rows if r.get("report_section") == "Portfolio Summary"
    }
    starting = _money(summary.get("Starting Capital"))
    stock_value = _money(summary.get("Current Stock Market Value"))
    sgov_value = _money(summary.get("SGOV Value"))
    reconciled = summary.get("Accounting Reconciliation") == "RECONCILED"

    holdings = [
        r for r in paper_rows
        if r.get("report_section") == "Current Pair Holdings" and r.get("pair")
    ]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in holdings:
        grouped.setdefault(str(row.get("pair")), []).append(row)

    snapshots: dict[str, dict[str, Any]] = {}
    portfolio_realized = portfolio_unrealized = portfolio_dividends = 0.0
    for pair, pair_rows in grouped.items():
        stock = sum(_money(r.get("market_value")) for r in pair_rows if str(r.get("active_leg")) != "SGOV")
        sgov = sum(_money(r.get("sgov_balance")) for r in pair_rows)
        invested = sum(_money(r.get("invested_capital")) for r in pair_rows)
        realized = sum(_money(r.get("realized_gain_loss")) for r in pair_rows)
        unrealized = sum(_money(r.get("unrealized_gain_loss")) for r in pair_rows)
        dividends = sum(_money(r.get("total_dividends")) for r in pair_rows)
        pair_return = realized + unrealized + dividends
        pair_return_pct = (pair_return / invested * 100.0) if invested else 0.0
        activity_dates = [str(r.get("last_activity") or "") for r in pair_rows if r.get("last_activity")]
        states = sorted({str(r.get("position_state")) for r in pair_rows if r.get("position_state")})
        snapshots[pair] = {
            "activity_date": max(activity_dates) if activity_dates else trading_date.isoformat(),
            "pair": pair,
            "state": "; ".join(states),
            "position_status": _status(stock, sgov),
            "stock_value": _fmt_money(stock),
            "sgov_value": _fmt_money(sgov),
            "total_pair_value": _fmt_money(stock + sgov),
            "total_return_amount": _fmt_money(pair_return),
            "total_return_pct": _fmt_pct(pair_return_pct),
            "days_invested": str(max((int(r.get("days_since") or 0) for r in pair_rows), default=0)),
            "dividends_received": _fmt_money(dividends),
            "health_status": _health(pair_return_pct, reconciled),
        }
        portfolio_realized += realized
        portfolio_unrealized += unrealized
        portfolio_dividends += dividends

    capital_gain_loss = portfolio_realized + portfolio_unrealized
    total_return = capital_gain_loss + portfolio_dividends
    total_return_pct = (total_return / starting * 100.0) if starting else 0.0
    total_portfolio_value = starting + total_return
    reserved_cash = total_portfolio_value - stock_value - sgov_value

    rows.extend([
        _blank("Portfolio Health", metric="Starting Capital", value=_fmt_money(starting)),
        _blank("Portfolio Health", metric="Current Stock Value", value=_fmt_money(stock_value)),
        _blank("Portfolio Health", metric="Current SGOV Value", value=_fmt_money(sgov_value)),
        _blank("Portfolio Health", metric="Reserved / Unallocated Cash", value=_fmt_money(reserved_cash)),
        _blank("Portfolio Health", metric="Realized Capital Gain/Loss", value=_fmt_money(portfolio_realized)),
        _blank("Portfolio Health", metric="Unrealized Gain/Loss", value=_fmt_money(portfolio_unrealized)),
        _blank("Portfolio Health", metric="Capital Gain/Loss", value=_fmt_money(capital_gain_loss)),
        _blank("Portfolio Health", metric="Dividends Received", value=_fmt_money(portfolio_dividends)),
        _blank("Portfolio Health", metric="Total Return Amount", value=_fmt_money(total_return)),
        _blank("Portfolio Health", metric="Total Return Percent", value=_fmt_pct(total_return_pct)),
        _blank("Portfolio Health", metric="Total Portfolio Value", value=_fmt_money(total_portfolio_value)),
        _blank("Portfolio Health", metric="Accounting Status", value=("RECONCILED" if reconciled else "REVIEW REQUIRED"), explanation=(
            "Total Portfolio Value equals Starting Capital plus realized gain/loss, unrealized gain/loss, and dividends."
        )),
        _separator(),
    ])

    # Current holdings legend before historical performance.
    for pair in sorted(snapshots):
        snap = snapshots[pair]
        rows.append(_blank(
            "Current Pair Legend",
            activity_date=snap["activity_date"], pair=pair, state=snap["state"],
            position_status=snap["position_status"], stock_value=snap["stock_value"],
            sgov_value=snap["sgov_value"], total_pair_value=snap["total_pair_value"],
            total_return_amount=snap["total_return_amount"],
            total_return_pct=snap["total_return_pct"],
            dividends_received=snap["dividends_received"],
            health_status=snap["health_status"],
            explanation="Current authoritative pair assignment and current capital location.",
        ))
    rows.append(_separator())

    # Group history by current pair and order each group oldest to newest.
    log_rows = _load_log(root)
    history_by_pair: dict[str, list[dict[str, Any]]] = {pair: [] for pair in snapshots}
    for log in log_rows:
        pair = str(log.get("Pair") or "").strip()
        if pair not in history_by_pair:
            continue
        activity_date = str(log.get("Date") or "").strip()[:10]
        action = str(log.get("Action") or "").strip().upper()
        event = _event_label(action)
        snap = snapshots[pair]
        history_by_pair[pair].append(_blank(
            "Pair Performance",
            activity_date=activity_date,
            pair=pair,
            event=event,
            state=snap["state"],
            position_status=snap["position_status"],
            stock_value=snap["stock_value"],
            sgov_value=snap["sgov_value"],
            total_pair_value=snap["total_pair_value"],
            total_return_amount=snap["total_return_amount"],
            total_return_pct=snap["total_return_pct"],
            days_invested=snap["days_invested"],
            dividends_received=snap["dividends_received"],
            health_status=snap["health_status"],
            explanation=str(log.get("Reason") or "Recorded paper-trading activity."),
        ))

    for pair in sorted(snapshots):
        group = sorted(history_by_pair.get(pair, []), key=lambda r: str(r.get("activity_date") or ""))
        if not group:
            snap = snapshots[pair]
            group = [_blank(
                "Pair Performance", activity_date=snap["activity_date"], pair=pair,
                event="CURRENT SNAPSHOT", state=snap["state"],
                position_status=snap["position_status"], stock_value=snap["stock_value"],
                sgov_value=snap["sgov_value"], total_pair_value=snap["total_pair_value"],
                total_return_amount=snap["total_return_amount"], total_return_pct=snap["total_return_pct"],
                days_invested=snap["days_invested"], dividends_received=snap["dividends_received"],
                health_status=snap["health_status"], explanation="No earlier dated activity was available.",
            )]
        rows.extend(group)
        rows.append(_separator())

    gates = [
        ("Accounting Reconciliation", "PASS" if reconciled else "REVIEW REQUIRED", "Starting capital plus gains, losses, and dividends equals total portfolio value."),
        ("Paper-Trading Safety", "PASS", "Paper-only safeguards verified; no real orders are enabled."),
        ("Minimum Observation History", "IN PROGRESS", "Additional paper-trading history is still being collected."),
        ("Risk and Drawdown Review", "PASS" if total_return_pct > -10.0 else "REVIEW REQUIRED", "Losses and drawdown remain within validation limits."),
    ]
    for gate, status, explanation in gates:
        rows.append(_blank("Deployment Gates", metric=gate, value=status, health_status=status, explanation=explanation))
    rows.extend([
        _separator(),
        _blank("Final Assessment", metric="Strategy Health", value=_health(total_return_pct, reconciled), explanation=(
            "Paper-only assessment. All current pair states and grouped chronological history are included."
        )),
    ])
    return rows
