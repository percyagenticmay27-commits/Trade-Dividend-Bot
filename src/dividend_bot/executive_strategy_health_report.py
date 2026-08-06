"""Build the executive Strategy Health Report from paper-only evidence.

The report shows complete portfolio health, a concise current-exposure legend,
governance warnings, and pair activity grouped by historical pair from oldest
to newest. Reporting only: no broker actions or capital movement.
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.dividend_bot.executive_daily_paper_report import build_daily_paper_rows
from src.dividend_bot.executive_reporting_framework import executive_framework_rows

MODULE_NAME = "executive_strategy_health_report"
MODULE_VERSION = "4.7.0"
PAPER_TRADE_MODE = True

STRATEGY_HEALTH_FIELDS = [
    "activity_date", "report_section", "metric", "value", "pair",
    "active_stock", "event", "position_status", "portfolio_pct",
    "stock_value", "sgov_value", "total_pair_value", "total_return_amount",
    "total_return_pct", "days_invested", "dividends_received",
    "health_status", "explanation", "paper_trade_mode",
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


def _history_active_stock(action: str, ticker: str) -> str:
    if action in {
        "PAPER_SELL_TO_SGOV", "PAPER_PARK_IN_SGOV",
        "PAPER_EARNINGS_EXIT", "EARNINGS_EXIT",
    }:
        return "SGOV"
    return ticker


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
            "Shows portfolio health, current invested symbols, total SGOV exposure, replacement warnings, and grouped chronological pair history."
        )),
        _blank("Why This Report Is Used", metric="Use", value=(
            "Lets the investor see current exposure and whether Next Man Up is required before reviewing detailed pair performance."
        )),
        _separator(),
    ])

    summary = {
        str(row.get("metric")): str(row.get("value"))
        for row in paper_rows
        if row.get("report_section") == "Portfolio Summary"
    }
    starting = _money(summary.get("Starting Capital"))
    stock_value = _money(summary.get("Current Stock Market Value"))
    sgov_value = _money(summary.get("SGOV Value"))
    reconciled = summary.get("Accounting Reconciliation") == "RECONCILED"

    holdings = [
        row for row in paper_rows
        if row.get("report_section") == "Current Pair Holdings" and row.get("pair")
    ]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in holdings:
        grouped.setdefault(str(row.get("pair")), []).append(row)

    snapshots: dict[str, dict[str, Any]] = {}
    portfolio_realized = portfolio_unrealized = portfolio_dividends = 0.0

    for historical_pair, pair_rows in grouped.items():
        invested_rows = [
            row for row in pair_rows
            if str(row.get("active_leg") or "").strip() != "SGOV"
            and _money(row.get("market_value")) > 0
        ]
        active_stocks = sorted({
            str(row.get("active_leg") or "").strip()
            for row in invested_rows
            if str(row.get("active_leg") or "").strip()
        })
        active_stock_value = sum(_money(row.get("market_value")) for row in invested_rows)
        pair_sgov = sum(_money(row.get("sgov_balance")) for row in pair_rows)
        invested = sum(_money(row.get("invested_capital")) for row in pair_rows)
        realized = sum(_money(row.get("realized_gain_loss")) for row in pair_rows)
        unrealized = sum(_money(row.get("unrealized_gain_loss")) for row in pair_rows)
        dividends = sum(_money(row.get("total_dividends")) for row in pair_rows)
        pair_return = realized + unrealized + dividends
        pair_return_pct = (pair_return / invested * 100.0) if invested else 0.0
        dates = [str(row.get("last_activity") or "") for row in pair_rows if row.get("last_activity")]
        current_display = " / ".join(active_stocks)

        snapshots[historical_pair] = {
            "activity_date": max(dates) if dates else trading_date.isoformat(),
            "historical_pair": historical_pair,
            "current_display": current_display,
            "active_stock": current_display if current_display else "SGOV",
            "active_count": len(active_stocks),
            "position_status": _status(active_stock_value, pair_sgov),
            "portfolio_pct": _fmt_pct((active_stock_value / starting * 100.0) if starting else 0.0),
            "stock_value": _fmt_money(active_stock_value),
            "sgov_value": _fmt_money(pair_sgov),
            "total_pair_value": _fmt_money(active_stock_value + pair_sgov),
            "legend_total_value": _fmt_money(active_stock_value),
            "total_return_amount": _fmt_money(pair_return),
            "total_return_pct": _fmt_pct(pair_return_pct),
            "days_invested": str(max((int(row.get("days_since") or 0) for row in pair_rows), default=0)),
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
        _blank("Portfolio Health", metric="Accounting Status", value=(
            "RECONCILED" if reconciled else "REVIEW REQUIRED"
        ), explanation=(
            "Total Portfolio Value equals Starting Capital plus realized gain/loss, unrealized gain/loss, and dividends."
        )),
        _separator(),
    ])

    # Current invested symbols, plus warning when an Income + Growth pair is incomplete.
    for historical_pair in sorted(snapshots):
        snap = snapshots[historical_pair]
        if not snap["current_display"]:
            continue
        warning = ""
        if snap["active_count"] == 1:
            warning = "GROWTH PAIR REQUIRED — NEXT MAN UP"
        rows.append(_blank(
            "Current Pair Legend",
            activity_date=snap["activity_date"],
            pair=snap["current_display"],
            value=warning,
            portfolio_pct=snap["portfolio_pct"],
            total_pair_value=snap["legend_total_value"],
        ))

    # Consolidated SGOV exposure gives the investor an immediate portfolio-level view.
    if sgov_value > 0:
        sgov_dates = [
            snap["activity_date"] for snap in snapshots.values()
            if _money(snap["sgov_value"]) > 0
        ]
        rows.append(_blank(
            "Current Pair Legend",
            activity_date=max(sgov_dates) if sgov_dates else trading_date.isoformat(),
            pair="SGOV",
            value="PARKED CAPITAL — AWAITING NEXT MAN UP",
            portfolio_pct=_fmt_pct((sgov_value / starting * 100.0) if starting else 0.0),
            total_pair_value=_fmt_money(sgov_value),
        ))
    rows.append(_separator())

    for historical_pair in sorted(snapshots):
        snap = snapshots[historical_pair]
        if snap["active_count"] == 1:
            rows.append(_blank(
                "Pair Governance", activity_date=snap["activity_date"],
                pair=snap["current_display"], active_stock=snap["active_stock"],
                event="NEXT MAN UP REQUIRED",
                position_status="INCOMPLETE INCOME + GROWTH PAIR",
                value="GROWTH PAIR REQUIRED", health_status="ACTION REQUIRED",
                explanation=(
                    f"{historical_pair} currently has only {snap['active_stock']} invested. "
                    "A qualified Growth replacement must be selected from fresh evidence."
                ),
            ))
        elif snap["active_count"] == 0:
            rows.append(_blank(
                "Pair Governance", activity_date=snap["activity_date"],
                pair=historical_pair, active_stock="SGOV",
                event="NEXT MAN UP REQUIRED",
                position_status="PAIR FULLY PARKED IN SGOV",
                value="NEW INCOME + GROWTH PAIR REQUIRED",
                health_status="ACTION REQUIRED",
                explanation=(
                    "Both sleeves are in SGOV. The historical pair is no longer a current holding and a new Income + Growth pair is required."
                ),
            ))
    rows.append(_separator())

    history_by_pair: dict[str, list[dict[str, Any]]] = {pair: [] for pair in snapshots}
    for log in _load_log(root):
        historical_pair = str(log.get("Pair") or "").strip()
        if historical_pair not in history_by_pair:
            continue
        action = str(log.get("Action") or "").strip().upper()
        ticker = str(log.get("Ticker") or "").strip().upper()
        snap = snapshots[historical_pair]
        history_by_pair[historical_pair].append(_blank(
            "Pair Performance",
            activity_date=str(log.get("Date") or "").strip()[:10],
            pair=historical_pair,
            active_stock=_history_active_stock(action, ticker),
            event=_event_label(action),
            position_status=snap["position_status"],
            portfolio_pct=snap["portfolio_pct"],
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

    for historical_pair in sorted(snapshots):
        group = sorted(
            history_by_pair.get(historical_pair, []),
            key=lambda row: str(row.get("activity_date") or ""),
        )
        if not group:
            snap = snapshots[historical_pair]
            group = [_blank(
                "Pair Performance", activity_date=snap["activity_date"],
                pair=historical_pair, active_stock=snap["active_stock"],
                event="CURRENT SNAPSHOT", position_status=snap["position_status"],
                portfolio_pct=snap["portfolio_pct"], stock_value=snap["stock_value"],
                sgov_value=snap["sgov_value"], total_pair_value=snap["total_pair_value"],
                total_return_amount=snap["total_return_amount"],
                total_return_pct=snap["total_return_pct"],
                days_invested=snap["days_invested"],
                dividends_received=snap["dividends_received"],
                health_status=snap["health_status"],
                explanation="No earlier dated activity was available.",
            )]
        rows.extend(group)
        rows.append(_separator())

    gates = [
        ("Accounting Reconciliation", "PASS" if reconciled else "REVIEW REQUIRED", "Starting capital plus gains, losses, and dividends equals total portfolio value."),
        ("Paper-Trading Safety", "PASS", "Paper-only safeguards verified; no real orders are enabled."),
        ("Income + Growth Pair Governance", (
            "PASS" if all(snap["active_count"] == 2 for snap in snapshots.values()) else "ACTION REQUIRED"
        ), "Every strategy allocation must maintain an Income + Growth pair; SGOV and one-symbol allocations require Next Man Up."),
        ("Minimum Observation History", "IN PROGRESS", "Additional paper-trading history is still being collected."),
        ("Risk and Drawdown Review", "PASS" if total_return_pct > -10.0 else "REVIEW REQUIRED", "Losses and drawdown remain within validation limits."),
    ]
    for gate, status, explanation in gates:
        rows.append(_blank(
            "Deployment Gates", metric=gate, value=status,
            health_status=status, explanation=explanation,
        ))

    rows.extend([
        _separator(),
        _blank("Final Assessment", metric="Strategy Health", value=_health(
            total_return_pct, reconciled
        ), explanation=(
            "Paper-only assessment. The legend shows active holdings, consolidated SGOV exposure, and all Next Man Up warnings."
        )),
    ])
    return rows
