"""Build the Step 4 executive Strategy Health Report.

Reporting only. This module reads the authoritative paper ledger and reuses the
validated Step 2 portfolio rows. It never places orders, moves capital, or
changes strategy decisions.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.dividend_bot.executive_daily_paper_report import build_daily_paper_rows
from src.dividend_bot.executive_reporting_framework import executive_framework_rows

MODULE_NAME = "executive_strategy_health_report"
MODULE_VERSION = "4.3.0"
PAPER_TRADE_MODE = True

STRATEGY_HEALTH_FIELDS = [
    "activity_date",
    "report_section",
    "metric",
    "value",
    "pair",
    "position_status",
    "stock_value",
    "sgov_value",
    "total_pair_value",
    "total_return_amount",
    "total_return_pct",
    "days_invested",
    "dividends_received",
    "health_status",
    "explanation",
    "paper_trade_mode",
]


def _blank(section: str, **values: Any) -> dict[str, Any]:
    row = {field: "" for field in STRATEGY_HEALTH_FIELDS}
    row["report_section"] = section
    row["paper_trade_mode"] = True
    row.update(values)
    return row


def _separator() -> dict[str, Any]:
    """Return a fully blank CSV row so executive sections are easy to scan."""
    return {field: "" for field in STRATEGY_HEALTH_FIELDS}


def _money(value: Any) -> float:
    text = str(value or "").replace("$", "").replace(",", "").strip()
    try:
        return float(text)
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


def _latest_activity_date(pair_rows: list[dict[str, Any]], fallback: date) -> str:
    """Return the latest date that established the displayed pair position status."""
    candidates = [
        str(row.get("last_activity") or row.get("activity_date") or "").strip()
        for row in pair_rows
    ]
    candidates = [value for value in candidates if value]
    return max(candidates) if candidates else fallback.isoformat()


def build_strategy_health_rows(
    *,
    root_dir: str | Path,
    trading_date: date,
    generated_at: datetime | None = None,
) -> list[dict[str, Any]]:
    paper_rows = build_daily_paper_rows(
        root_dir=root_dir,
        trading_date=trading_date,
        generated_at=generated_at,
    )

    rows: list[dict[str, Any]] = []
    for item in executive_framework_rows(
        source_name="strategy_health_report.md",
        trading_date=trading_date,
        generated_at=generated_at,
    ):
        rows.append(_blank(item["section"], metric=item["field"], value=item["value"]))

    rows.extend(
        [
            _blank(
                "What This Report Shows",
                metric="Purpose",
                value=(
                    "Shows whether the Dividend Strategy is financially healthy, where each pair's capital is held, "
                    "and how capital gains, losses, and dividends combine into total return."
                ),
            ),
            _blank(
                "Why This Report Is Used",
                metric="Use",
                value=(
                    "Provides a simple portfolio-health review in which every pair's return and dividend income "
                    "reconcile to the portfolio's total return and current value."
                ),
            ),
            _separator(),
        ]
    )

    summary = {
        str(row.get("metric")): str(row.get("value"))
        for row in paper_rows
        if row.get("report_section") == "Portfolio Summary"
    }
    stock_value = _money(summary.get("Current Stock Market Value"))
    sgov_value = _money(summary.get("SGOV Value"))
    starting = _money(summary.get("Starting Capital"))
    reconciled = summary.get("Accounting Reconciliation") == "RECONCILED"

    holdings = [
        row
        for row in paper_rows
        if row.get("report_section") == "Current Pair Holdings" and row.get("pair")
    ]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in holdings:
        grouped.setdefault(str(row.get("pair")), []).append(row)

    pair_output_rows: list[dict[str, Any]] = []
    portfolio_realized = 0.0
    portfolio_unrealized = 0.0
    portfolio_dividends = 0.0

    for pair, pair_rows in grouped.items():
        stock = sum(
            _money(row.get("market_value"))
            for row in pair_rows
            if str(row.get("active_leg")) != "SGOV"
        )
        sgov = sum(_money(row.get("sgov_balance")) for row in pair_rows)
        pair_value = stock + sgov
        invested = sum(_money(row.get("invested_capital")) for row in pair_rows)
        realized = sum(_money(row.get("realized_gain_loss")) for row in pair_rows)
        unrealized = sum(_money(row.get("unrealized_gain_loss")) for row in pair_rows)
        dividends = sum(_money(row.get("total_dividends")) for row in pair_rows)
        pair_return = realized + unrealized + dividends
        pair_return_pct = (pair_return / invested * 100.0) if invested else 0.0
        days = max((int(row.get("days_since") or 0) for row in pair_rows), default=0)
        states = {
            str(row.get("position_state"))
            for row in pair_rows
            if row.get("position_state")
        }

        portfolio_realized += realized
        portfolio_unrealized += unrealized
        portfolio_dividends += dividends

        if stock <= 0 and sgov > 0:
            status = "MOVED INTO SGOV"
        elif stock > 0 and sgov > 0:
            status = "PARTIALLY INVESTED / PARTIALLY IN SGOV"
        elif stock > 0:
            status = "INVESTED"
        else:
            status = "NO ACTIVE CAPITAL"

        pair_output_rows.append(
            _blank(
                "Pair Performance",
                activity_date=_latest_activity_date(pair_rows, trading_date),
                pair=pair,
                position_status=status,
                stock_value=_fmt_money(stock),
                sgov_value=_fmt_money(sgov),
                total_pair_value=_fmt_money(pair_value),
                total_return_amount=_fmt_money(pair_return),
                total_return_pct=_fmt_pct(pair_return_pct),
                days_invested=str(days),
                dividends_received=_fmt_money(dividends),
                health_status=_health(pair_return_pct, reconciled),
                explanation=(
                    "Date is the activity that established the displayed position status. "
                    "Rows are grouped by pair and ordered oldest to newest so the pair's development is easy to follow. "
                    "Total return equals realized gain/loss plus unrealized gain/loss plus dividends."
                ),
                value="; ".join(sorted(states)),
            )
        )

    # Keep each pair together, then show its activity chronologically from oldest
    # to newest. This is intentionally not a newest-first executive activity sort.
    pair_output_rows.sort(
        key=lambda row: (str(row.get("pair") or ""), str(row.get("activity_date") or ""))
    )

    current_pair_legend = [
        _blank(
            "Current Pair Legend",
            activity_date=str(row.get("activity_date") or ""),
            metric="Current Pair",
            value=str(row.get("position_status") or ""),
            pair=str(row.get("pair") or ""),
            position_status=str(row.get("position_status") or ""),
            stock_value=str(row.get("stock_value") or ""),
            sgov_value=str(row.get("sgov_value") or ""),
            total_pair_value=str(row.get("total_pair_value") or ""),
            explanation="This is the pair currently assigned and its present capital location before reviewing its performance history.",
        )
        for row in sorted(pair_output_rows, key=lambda item: str(item.get("pair") or ""))
    ]

    capital_gain_loss = portfolio_realized + portfolio_unrealized
    total_return = capital_gain_loss + portfolio_dividends
    total_return_pct = (total_return / starting * 100.0) if starting else 0.0
    total_portfolio_value = starting + total_return
    reserved_cash = total_portfolio_value - stock_value - sgov_value

    rows.extend(
        [
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
            _blank(
                "Portfolio Health",
                metric="Accounting Status",
                value="RECONCILED" if reconciled else "REVIEW REQUIRED",
                health_status=_health(total_return_pct, reconciled),
                explanation=(
                    "Total Portfolio Value equals Starting Capital plus Total Return. "
                    "Total Return includes pair gains/losses and dividends."
                ),
            ),
            _separator(),
        ]
    )

    rows.extend(current_pair_legend)
    rows.append(_separator())
    rows.extend(pair_output_rows)
    rows.append(_separator())

    gates = [
        (
            "Accounting Reconciliation",
            "Confirms that starting capital plus gains, losses, and dividends equals total portfolio value.",
            "PASS" if reconciled else "REVIEW REQUIRED",
        ),
        (
            "Paper-Trading Safety",
            "Confirms that the strategy remains paper-only and no real broker orders are enabled.",
            "PASS",
        ),
        (
            "Minimum Observation History",
            "Confirms that enough paper-trading history exists before any future production-readiness decision.",
            "IN PROGRESS",
        ),
        (
            "Risk and Drawdown Review",
            "Confirms that losses and drawdown remain within the strategy's approved validation limits.",
            "PASS" if total_return_pct > -10.0 else "REVIEW REQUIRED",
        ),
    ]
    for gate, meaning, status in gates:
        rows.append(
            _blank(
                "Deployment Gates",
                metric=gate,
                value=status,
                health_status=status,
                explanation=meaning,
            )
        )

    rows.extend(
        [
            _separator(),
            _blank(
                "Final Assessment",
                metric="Strategy Health",
                value=_health(total_return_pct, reconciled),
                explanation=(
                    "Paper-only assessment. Portfolio return includes realized gains/losses, "
                    "unrealized gains/losses, and dividends."
                ),
            ),
        ]
    )
    return rows
