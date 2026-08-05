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
MODULE_VERSION = "4.0.0"
PAPER_TRADE_MODE = True

STRATEGY_HEALTH_FIELDS = [
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


def _money(value: Any) -> float:
    text = str(value or "").replace("$", "").replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return 0.0


def _percent(value: Any) -> float:
    text = str(value or "").replace("%", "").strip()
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

    rows.append(
        _blank(
            "What This Report Shows",
            metric="Purpose",
            value=(
                "Shows whether the Dividend Strategy is financially healthy, where each pair's capital is held, "
                "and whether paper-validation requirements are being met."
            ),
        )
    )
    rows.append(
        _blank(
            "Why This Report Is Used",
            metric="Use",
            value=(
                "Provides a simple portfolio-health review using total stock value, SGOV value, pair returns, "
                "dividends, and clearly explained deployment gates."
            ),
        )
    )

    summary = {
        str(row.get("metric")): str(row.get("value"))
        for row in paper_rows
        if row.get("report_section") == "Portfolio Summary"
    }
    total_value = _money(summary.get("Total Portfolio Value"))
    stock_value = _money(summary.get("Current Stock Market Value"))
    sgov_value = _money(summary.get("SGOV Value"))
    starting = _money(summary.get("Starting Capital"))
    total_return = total_value - starting
    total_return_pct = (total_return / starting * 100.0) if starting else 0.0
    reconciled = summary.get("Accounting Reconciliation") == "RECONCILED"

    rows.extend(
        [
            _blank("Portfolio Health", metric="Starting Capital", value=_fmt_money(starting)),
            _blank("Portfolio Health", metric="Current Stock Value", value=_fmt_money(stock_value)),
            _blank("Portfolio Health", metric="Current SGOV Value", value=_fmt_money(sgov_value)),
            _blank("Portfolio Health", metric="Total Portfolio Value", value=_fmt_money(total_value)),
            _blank("Portfolio Health", metric="Total Return Amount", value=_fmt_money(total_return)),
            _blank("Portfolio Health", metric="Total Return Percent", value=_fmt_pct(total_return_pct)),
            _blank(
                "Portfolio Health",
                metric="Accounting Status",
                value="RECONCILED" if reconciled else "REVIEW REQUIRED",
                health_status=_health(total_return_pct, reconciled),
            ),
        ]
    )

    holdings = [
        row for row in paper_rows
        if row.get("report_section") == "Current Pair Holdings" and row.get("pair")
    ]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in holdings:
        grouped.setdefault(str(row.get("pair")), []).append(row)

    for pair, pair_rows in grouped.items():
        stock = sum(_money(row.get("market_value")) for row in pair_rows if str(row.get("active_leg")) != "SGOV")
        sgov = sum(_money(row.get("sgov_balance")) for row in pair_rows)
        pair_value = stock + sgov
        invested = sum(_money(row.get("invested_capital")) for row in pair_rows)
        realized = sum(_money(row.get("realized_gain_loss")) for row in pair_rows)
        unrealized = sum(_money(row.get("unrealized_gain_loss")) for row in pair_rows)
        dividends = sum(_money(row.get("total_dividends")) for row in pair_rows)
        pair_return = realized + unrealized + dividends
        pair_return_pct = (pair_return / invested * 100.0) if invested else 0.0
        days = max((int(row.get("days_since") or 0) for row in pair_rows), default=0)
        states = {str(row.get("position_state")) for row in pair_rows if row.get("position_state")}
        if stock <= 0 and sgov > 0:
            status = "MOVED INTO SGOV"
        elif stock > 0 and sgov > 0:
            status = "PARTIALLY INVESTED / PARTIALLY IN SGOV"
        elif stock > 0:
            status = "INVESTED"
        else:
            status = "NO ACTIVE CAPITAL"
        rows.append(
            _blank(
                "Pair Performance",
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
                    "Return amount includes realized gain/loss, unrealized gain/loss, and dividends. "
                    "Return percent is measured against invested capital."
                ),
                value="; ".join(sorted(states)),
            )
        )

    gates = [
        (
            "Accounting Reconciliation",
            "Confirms that stock value, SGOV, and reserved cash reconcile to the approved portfolio capital.",
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

    rows.append(
        _blank(
            "Final Assessment",
            metric="Strategy Health",
            value=_health(total_return_pct, reconciled),
            explanation="Paper-only assessment. No real trades or broker actions were executed.",
        )
    )
    return rows
