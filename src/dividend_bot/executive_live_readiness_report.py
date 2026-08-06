"""Build the executive Live Readiness Report from paper-only evidence.

Reporting only. This module does not place orders, connect to a broker, or
change portfolio state.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.dividend_bot.executive_reporting_framework import executive_framework_rows
from src.dividend_bot.executive_strategy_health_report import build_strategy_health_rows

MODULE_NAME = "executive_live_readiness_report"
MODULE_VERSION = "2.0.0"
PAPER_TRADE_MODE = True

LIVE_READINESS_FIELDS = [
    "report_section", "metric", "value", "notes", "activity_date", "pair",
    "portfolio_pct", "total_value", "warning", "gate", "status",
    "progress", "requirement", "explanation", "paper_trade_mode",
]


def _row(section: str, **values: Any) -> dict[str, Any]:
    row = {field: "" for field in LIVE_READINESS_FIELDS}
    row["report_section"] = section
    row["paper_trade_mode"] = True
    row.update(values)
    return row


def _separator() -> dict[str, Any]:
    return {field: "" for field in LIVE_READINESS_FIELDS}


def _clean(value: str) -> str:
    value = value.strip().replace("**", "").replace("`", "")
    return re.sub(r"^[-*+]\s+", "", value).strip()


def _read_markdown_metrics(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise RuntimeError(f"Required daily Dividend report is missing: {path}")
    metrics: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        text = _clean(raw)
        if not text or text.startswith("#") or ":" not in text:
            continue
        key, value = text.split(":", 1)
        if key.strip() and value.strip():
            metrics[key.strip().lower()] = value.strip()
    return metrics


def _metric(metrics: dict[str, str], *names: str, default: str = "Not reported") -> str:
    for name in names:
        value = metrics.get(name.lower())
        if value:
            return value
    return default


def build_live_readiness_rows(
    *, root_dir: str | Path, trading_date: date, generated_at: datetime | None = None
) -> list[dict[str, Any]]:
    root = Path(root_dir)
    metrics = _read_markdown_metrics(root / "live_readiness_report.md")
    strategy_rows = build_strategy_health_rows(
        root_dir=root, trading_date=trading_date, generated_at=generated_at
    )

    rows: list[dict[str, Any]] = []
    for item in executive_framework_rows(
        source_name="live_readiness_report.md",
        trading_date=trading_date,
        generated_at=generated_at,
    ):
        rows.append(_row(item["section"], metric=item["field"], value=item["value"]))

    rows.extend([
        _row("Executive Header", metric="Report Name", value="Executive Live Readiness Report"),
        _row("Executive Header", metric="Report Version", value=MODULE_VERSION),
        _row("Executive Header", metric="Trading Mode", value="PAPER ONLY"),
        _row("Executive Header", metric="Report Date", value=trading_date.isoformat()),
        _row("Executive Header", metric="What This Report Shows", value=(
            "Summarizes operational readiness, Income + Growth governance, deployment gates, and blocking issues."
        )),
        _row("Executive Header", metric="Why This Report Is Used", value=(
            "Supports deployment decisions without enabling live trading or broker execution."
        )),
        _separator(),
    ])

    summary_items = [
        ("Overall Readiness", _metric(metrics, "overall live readiness", "overall readiness")),
        ("Readiness Level", _metric(metrics, "status", "readiness level")),
        ("Paper Trading Days", _metric(metrics, "paper trading days", "paper trading days completed")),
        ("Required Paper Days", _metric(metrics, "required paper days", default="90")),
        ("Days Remaining", _metric(metrics, "days remaining")),
        ("Current Portfolio Value", _metric(metrics, "portfolio value", "current portfolio value")),
        ("Maximum Drawdown", _metric(metrics, "maximum drawdown")),
        ("Accounting Status", _metric(metrics, "accounting status", "accounting reconciliation")),
    ]
    for name, value in summary_items:
        rows.append(_row("Current Readiness Summary", metric=name, value=value))
    rows.append(_separator())

    legends = [row for row in strategy_rows if row.get("report_section") == "Current Pair Legend"]
    governance = [row for row in strategy_rows if row.get("report_section") == "Pair Governance"]
    sgov = next((row for row in legends if row.get("pair") == "SGOV"), None)
    active = [row for row in legends if row.get("pair") != "SGOV"]
    warnings = [row for row in legends if row.get("warning") or row.get("explanation")]

    governance_items = [
        ("Income + Growth Compliance", "ACTION REQUIRED" if governance else "PASS"),
        ("Current Active Holdings", str(len(active))),
        ("Next Man Up Requirements", str(len(governance))),
        ("Current SGOV Allocation", str((sgov or {}).get("portfolio_pct") or "0.00%")),
        ("Current Active Allocation", _metric(metrics, "current active allocation")),
    ]
    for name, value in governance_items:
        rows.append(_row("Governance Readiness", metric=name, value=value))
    rows.append(_separator())

    for legend in legends:
        rows.append(_row(
            "Current Pair Legend",
            activity_date=legend.get("activity_date", ""),
            pair=legend.get("pair", ""),
            portfolio_pct=legend.get("portfolio_pct", ""),
            total_value=legend.get("total_pair_value", ""),
            warning=legend.get("warning", "") or legend.get("explanation", ""),
        ))
    rows.append(_separator())

    gate_specs = [
        ("Operational Validation", "30 paper days"),
        ("Limited Capital Eligibility", "60 paper days"),
        ("Production Candidate", "90 paper days"),
        ("Accounting Reconciliation", "All balances reconcile"),
        ("Income + Growth Governance", "All active allocations have complete Income + Growth pairs"),
        ("Risk and Drawdown Review", "Risk remains within approved paper limits"),
    ]
    readiness_status = _metric(metrics, "status", "readiness level", default="IN PROGRESS").upper()
    for gate, requirement in gate_specs:
        if gate == "Income + Growth Governance":
            status = "ACTION REQUIRED" if governance else "PASS"
        elif gate == "Accounting Reconciliation":
            accounting = _metric(metrics, "accounting status", "accounting reconciliation", default="IN PROGRESS").upper()
            status = "PASS" if accounting in {"PASS", "RECONCILED"} else accounting
        elif gate == "Production Candidate":
            status = "PASS" if readiness_status in {"READY", "ELIGIBLE", "PASS"} else "NOT READY"
        else:
            status = "IN PROGRESS"
        rows.append(_row(
            "Deployment Gates", gate=gate, status=status,
            requirement=requirement,
            explanation=f"{gate} requirement: {requirement}.",
        ))
    rows.append(_separator())

    if governance:
        for item in governance:
            rows.append(_row(
                "Blocking Issues",
                metric=item.get("event") or "Governance action required",
                value=item.get("value") or item.get("position_status") or "ACTION REQUIRED",
                pair=item.get("pair", ""),
                warning=item.get("explanation", ""),
                status="OPEN",
            ))
    days_remaining = _metric(metrics, "days remaining", default="")
    if days_remaining and days_remaining not in {"0", "0 days"}:
        rows.append(_row(
            "Blocking Issues", metric="Paper Trading Duration",
            value=f"{days_remaining} remaining", status="OPEN",
            warning="Minimum observation period is not complete.",
        ))
    if not governance and not days_remaining:
        rows.append(_row("Blocking Issues", metric="No blocking issues reported", value="NONE", status="CLEAR"))
    rows.append(_separator())

    ready = not governance and readiness_status in {"READY", "ELIGIBLE", "PASS"}
    rows.extend([
        _row("Final Assessment", metric="Overall Status", value="READY" if ready else "NOT READY"),
        _row("Final Assessment", metric="Ready for Limited Deployment", value="YES" if ready else "NO"),
        _row("Final Assessment", metric="Ready for Production", value="YES" if ready else "NO"),
        _row("Final Assessment", metric="Primary Next Action", value=(
            "Complete all open readiness gates and Next Man Up replacements."
            if not ready else "Maintain governance and continue monitored validation."
        )),
    ])
    return rows
