"""Enterprise Investor Dashboard Integration for the Trade Dividend Bot.

Transforms existing paper-only reporting artifacts into a concise investor-facing
portfolio dashboard. This module is reporting-only: it cannot place orders,
communicate with a brokerage, or enable live trading.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "enterprise_investor_dashboard_integration"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_OUTPUT_FILES = {
    "json": "enterprise_investor_dashboard.json",
    "markdown": "enterprise_investor_dashboard.md",
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _money(value: Any) -> float:
    return round(_number(value), 2)


def _percent(value: Any) -> float:
    return round(_number(value), 4)


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    text = str(value or default).strip()
    return text.upper() if text else default


def _first(mapping: Mapping[str, Any], keys: Sequence[str], default: Any = 0.0) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _yield_percent(annual_income: float, portfolio_value: float, explicit: Any = None) -> float:
    explicit_value = _number(explicit, -1.0)
    if explicit_value >= 0:
        return round(explicit_value, 4)
    if portfolio_value <= 0:
        return 0.0
    return round((annual_income / portfolio_value) * 100.0, 4)


def _income_consistency(payments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    expected = 0
    received = 0
    late = 0
    missed = 0
    for item in payments:
        status = _upper(item.get("status"), "UNKNOWN")
        expected += 1
        if status in {"PAID", "RECEIVED", "COMPLETED", "ON_TIME"}:
            received += 1
        elif status in {"LATE", "DELAYED"}:
            late += 1
        elif status in {"MISSED", "FAILED", "SKIPPED"}:
            missed += 1
    score = 100.0 if expected == 0 else max(0.0, ((received + 0.5 * late) / expected) * 100.0)
    label = "STRONG" if score >= 90 else "STABLE" if score >= 75 else "WATCH" if score >= 50 else "WEAK"
    return {
        "expected_payment_count": expected,
        "received_payment_count": received,
        "late_payment_count": late,
        "missed_payment_count": missed,
        "consistency_score": round(score, 2),
        "consistency_label": label,
    }


def _allocation_summary(holdings: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    sector_totals: dict[str, float] = {}
    total_value = 0.0
    for item in holdings:
        symbol = _upper(_first(item, ("symbol", "ticker", "asset"), "UNKNOWN"))
        value = _number(_first(item, ("market_value", "position_value", "value"), 0.0))
        allocation = _number(_first(item, ("allocation_percent", "weight_percent", "portfolio_percent"), 0.0))
        annual_income = _number(_first(item, ("annual_income", "projected_annual_income", "annual_dividend_income"), 0.0))
        sector = str(_first(item, ("sector", "theme", "category"), "Unclassified") or "Unclassified").strip()
        row = dict(item)
        row.update({
            "symbol": symbol,
            "market_value": round(value, 2),
            "allocation_percent": round(allocation, 4),
            "projected_annual_income": round(annual_income, 2),
            "sector": sector,
        })
        normalized.append(row)
        total_value += value
        sector_totals[sector] = sector_totals.get(sector, 0.0) + allocation
    normalized.sort(key=lambda row: (-_number(row.get("allocation_percent")), row.get("symbol", "")))
    sector_rows = [
        {"sector": sector, "allocation_percent": round(percent, 4)}
        for sector, percent in sorted(sector_totals.items(), key=lambda item: (-item[1], item[0]))
    ]
    largest = normalized[0] if normalized else {}
    return {
        "holding_count": len(normalized),
        "total_position_value": round(total_value, 2),
        "largest_position_symbol": largest.get("symbol"),
        "largest_position_percent": _percent(largest.get("allocation_percent")),
        "holdings": normalized,
        "sector_allocation": sector_rows,
    }


def _risk_flags(
    *,
    portfolio_value: float,
    annual_income: float,
    allocation: Mapping[str, Any],
    consistency: Mapping[str, Any],
    review_flags: Sequence[Mapping[str, Any]],
    cash_percent: float,
) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    largest = _number(allocation.get("largest_position_percent"))
    if largest > 25.0:
        flags.append({"severity": "HIGH", "code": "POSITION_CONCENTRATION", "message": f"Largest position is {largest:.2f}% of the portfolio."})
    elif largest > 15.0:
        flags.append({"severity": "MEDIUM", "code": "POSITION_CONCENTRATION", "message": f"Largest position is {largest:.2f}% of the portfolio."})
    sectors = list(allocation.get("sector_allocation") or [])
    if sectors and _number(sectors[0].get("allocation_percent")) > 40.0:
        flags.append({"severity": "HIGH", "code": "SECTOR_CONCENTRATION", "message": f"{sectors[0].get('sector')} represents {_number(sectors[0].get('allocation_percent')):.2f}% of the portfolio."})
    if _number(consistency.get("missed_payment_count")) > 0:
        flags.append({"severity": "HIGH", "code": "MISSED_DIVIDEND_PAYMENT", "message": "One or more expected dividend payments were missed."})
    if _number(consistency.get("consistency_score"), 100.0) < 75.0:
        flags.append({"severity": "MEDIUM", "code": "INCOME_CONSISTENCY", "message": "Dividend payment consistency is below the stable threshold."})
    if portfolio_value > 0 and annual_income <= 0:
        flags.append({"severity": "MEDIUM", "code": "NO_PROJECTED_INCOME", "message": "Portfolio value is positive but projected annual dividend income is zero."})
    if cash_percent < 2.0:
        flags.append({"severity": "LOW", "code": "LOW_LIQUID_RESERVE", "message": "Cash or reserve allocation is below 2%."})
    for item in review_flags:
        flags.append({
            "severity": _upper(item.get("severity"), "MEDIUM"),
            "code": _upper(item.get("code") or item.get("flag") or "SOURCE_REVIEW_FLAG"),
            "message": str(item.get("message") or item.get("reason") or "Source report requires investor review."),
        })
    priority = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
    flags.sort(key=lambda item: (priority.get(item["severity"], 9), item["code"]))
    return flags


def _suggested_actions(flags: Sequence[Mapping[str, Any]], upcoming_payments: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    codes = {str(item.get("code")) for item in flags}
    if "POSITION_CONCENTRATION" in codes:
        actions.append({"priority": "HIGH", "action": "Review the largest position and compare its allocation with the portfolio concentration policy."})
    if "SECTOR_CONCENTRATION" in codes:
        actions.append({"priority": "HIGH", "action": "Review sector concentration before directing additional paper capital to that sector."})
    if "MISSED_DIVIDEND_PAYMENT" in codes or "INCOME_CONSISTENCY" in codes:
        actions.append({"priority": "HIGH", "action": "Validate dividend declarations and payment records for affected holdings."})
    if "LOW_LIQUID_RESERVE" in codes:
        actions.append({"priority": "MEDIUM", "action": "Review whether the paper portfolio should maintain a larger SGOV or cash reserve."})
    if upcoming_payments:
        actions.append({"priority": "LOW", "action": "Monitor the upcoming dividend payment schedule and confirm payments after their payable dates."})
    if not actions:
        actions.append({"priority": "INFO", "action": "Continue monitoring portfolio income, allocation, and dividend reliability."})
    priority = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
    actions.sort(key=lambda item: priority[item["priority"]])
    return actions


def build_enterprise_investor_dashboard(
    *,
    dividend_dashboard: Optional[Mapping[str, Any]] = None,
    portfolio_summary: Optional[Mapping[str, Any]] = None,
    holdings: Optional[Sequence[Mapping[str, Any]]] = None,
    payment_history: Optional[Sequence[Mapping[str, Any]]] = None,
    upcoming_payments: Optional[Sequence[Mapping[str, Any]]] = None,
    review_flags: Optional[Sequence[Mapping[str, Any]]] = None,
    confidence_report: Optional[Mapping[str, Any]] = None,
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Build an investor-facing dashboard from existing read-only artifacts."""
    dashboard = dict(dividend_dashboard or {})
    summary = dict(portfolio_summary or dashboard.get("portfolio_summary") or dashboard.get("summary") or {})
    positions = _rows(holdings if holdings is not None else dashboard.get("holdings") or dashboard.get("positions") or [])
    history = _rows(payment_history if payment_history is not None else dashboard.get("payment_history") or dashboard.get("payments") or [])
    upcoming = _rows(upcoming_payments if upcoming_payments is not None else dashboard.get("upcoming_payments") or [])
    source_flags = _rows(review_flags if review_flags is not None else dashboard.get("review_flags") or [])
    confidence = dict(confidence_report or dashboard.get("confidence_report") or dashboard.get("confidence") or {})

    portfolio_value = _money(_first(summary, ("portfolio_value", "market_value", "total_portfolio_value"), 0.0))
    cost_basis = _money(_first(summary, ("cost_basis", "total_cost_basis"), 0.0))
    capital_appreciation = _money(_first(summary, ("capital_appreciation", "unrealized_gain_loss", "total_gain_loss"), portfolio_value - cost_basis if cost_basis else 0.0))
    annual_income = _money(_first(summary, ("projected_annual_income", "annual_dividend_income", "annual_income"), 0.0))
    monthly_income = _money(_first(summary, ("projected_monthly_income", "monthly_dividend_income", "monthly_income"), annual_income / 12.0 if annual_income else 0.0))
    cash_value = _money(_first(summary, ("cash_value", "cash", "reserve_value", "sgov_value"), 0.0))
    cash_percent = _percent(_first(summary, ("cash_percent", "reserve_percent", "sgov_allocation_percent"), (cash_value / portfolio_value * 100.0) if portfolio_value else 0.0))
    current_yield = _yield_percent(annual_income, portfolio_value, _first(summary, ("current_yield_percent", "portfolio_yield", "dividend_yield_percent"), None))
    yield_on_cost = _yield_percent(annual_income, cost_basis, _first(summary, ("yield_on_cost_percent", "yield_on_cost"), None))

    allocation = _allocation_summary(positions)
    consistency = _income_consistency(history)
    flags = _risk_flags(
        portfolio_value=portfolio_value,
        annual_income=annual_income,
        allocation=allocation,
        consistency=consistency,
        review_flags=source_flags,
        cash_percent=cash_percent,
    )
    actions = _suggested_actions(flags, upcoming)
    high_count = sum(1 for item in flags if item["severity"] == "HIGH")
    medium_count = sum(1 for item in flags if item["severity"] == "MEDIUM")
    health = "ATTENTION_REQUIRED" if high_count else "WATCH" if medium_count else "STABLE"

    warnings: list[str] = []
    if not summary:
        warnings.append("Portfolio summary was not supplied.")
    if not positions:
        warnings.append("Holdings data was not supplied.")
    if not history:
        warnings.append("Payment history was not supplied; consistency defaults to no observed exceptions.")

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at_utc or _now_utc(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
        "dashboard_status": "READY" if summary else "PARTIAL",
        "portfolio_health": health,
        "investor_summary": {
            "portfolio_value": portfolio_value,
            "cost_basis": cost_basis,
            "capital_appreciation": capital_appreciation,
            "projected_annual_dividend_income": annual_income,
            "projected_monthly_dividend_income": monthly_income,
            "current_yield_percent": current_yield,
            "yield_on_cost_percent": yield_on_cost,
            "cash_or_reserve_value": cash_value,
            "cash_or_reserve_percent": cash_percent,
            "holding_count": allocation["holding_count"],
            "upcoming_payment_count": len(upcoming),
            "high_risk_flag_count": high_count,
            "medium_risk_flag_count": medium_count,
        },
        "income_reliability": consistency,
        "allocation": allocation,
        "upcoming_payments": upcoming,
        "confidence": confidence,
        "risk_flags": flags,
        "suggested_actions": actions,
        "warnings": warnings,
        "errors": [],
    }


def render_enterprise_investor_dashboard_markdown(report: Mapping[str, Any]) -> str:
    summary = dict(report.get("investor_summary") or {})
    reliability = dict(report.get("income_reliability") or {})
    allocation = dict(report.get("allocation") or {})
    lines = [
        "# Enterprise Investor Dashboard",
        "",
        "> Paper-only investor reporting. No brokerage execution or order placement.",
        "",
        "## Portfolio Overview",
        "",
        f"- **Portfolio Health:** {report.get('portfolio_health', 'UNKNOWN')}",
        f"- **Portfolio Value:** ${_number(summary.get('portfolio_value')):,.2f}",
        f"- **Cost Basis:** ${_number(summary.get('cost_basis')):,.2f}",
        f"- **Capital Appreciation:** ${_number(summary.get('capital_appreciation')):,.2f}",
        f"- **Projected Annual Dividend Income:** ${_number(summary.get('projected_annual_dividend_income')):,.2f}",
        f"- **Projected Monthly Dividend Income:** ${_number(summary.get('projected_monthly_dividend_income')):,.2f}",
        f"- **Current Yield:** {_number(summary.get('current_yield_percent')):.2f}%",
        f"- **Yield on Cost:** {_number(summary.get('yield_on_cost_percent')):.2f}%",
        f"- **Cash / Reserve:** ${_number(summary.get('cash_or_reserve_value')):,.2f} ({_number(summary.get('cash_or_reserve_percent')):.2f}%)",
        "",
        "## Income Reliability",
        "",
        f"- **Consistency:** {reliability.get('consistency_label', 'UNKNOWN')} ({_number(reliability.get('consistency_score')):.2f}%)",
        f"- **Received:** {int(_number(reliability.get('received_payment_count')))}",
        f"- **Late:** {int(_number(reliability.get('late_payment_count')))}",
        f"- **Missed:** {int(_number(reliability.get('missed_payment_count')))}",
        "",
        "## Holdings",
        "",
        "| Symbol | Market Value | Allocation | Annual Income | Sector |",
        "|---|---:|---:|---:|---|",
    ]
    for item in allocation.get("holdings", []):
        lines.append(
            f"| {item.get('symbol', 'UNKNOWN')} | ${_number(item.get('market_value')):,.2f} | "
            f"{_number(item.get('allocation_percent')):.2f}% | ${_number(item.get('projected_annual_income')):,.2f} | "
            f"{item.get('sector', 'Unclassified')} |"
        )
    if not allocation.get("holdings"):
        lines.append("| No holdings supplied | $0.00 | 0.00% | $0.00 | Unclassified |")

    lines.extend(["", "## Upcoming Dividend Payments", ""])
    upcoming = list(report.get("upcoming_payments") or [])
    if upcoming:
        lines.extend(["| Symbol | Payable Date | Expected Amount | Status |", "|---|---|---:|---|"])
        for item in upcoming:
            lines.append(
                f"| {_upper(item.get('symbol') or item.get('ticker'))} | {item.get('payable_date') or item.get('date') or 'Unknown'} | "
                f"${_number(item.get('expected_amount') or item.get('amount')):,.2f} | {_upper(item.get('status'), 'EXPECTED')} |"
            )
    else:
        lines.append("No upcoming dividend payments were supplied.")

    lines.extend(["", "## Risk Flags", ""])
    flags = list(report.get("risk_flags") or [])
    if flags:
        for item in flags:
            lines.append(f"- **{item.get('severity')} — {item.get('code')}:** {item.get('message')}")
    else:
        lines.append("No dashboard risk flags were generated.")

    lines.extend(["", "## Suggested Actions", ""])
    for item in report.get("suggested_actions", []):
        lines.append(f"- **{item.get('priority')}:** {item.get('action')}")

    warnings = list(report.get("warnings") or [])
    if warnings:
        lines.extend(["", "## Data Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.append("")
    return "\n".join(lines)


def write_enterprise_investor_dashboard(
    report: Mapping[str, Any],
    output_dir: str | Path = "reports",
    output_files: Optional[Mapping[str, str]] = None,
) -> dict[str, str]:
    """Write JSON and Markdown investor dashboard outputs."""
    if not isinstance(report, Mapping):
        raise ValueError("report must be a mapping")
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    json_path = target / files["json"]
    markdown_path = target / files["markdown"]
    json_path.write_text(json.dumps(dict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_enterprise_investor_dashboard_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def build_and_write_enterprise_investor_dashboard(
    *,
    output_dir: str | Path = "reports",
    output_files: Optional[Mapping[str, str]] = None,
    **inputs: Any,
) -> tuple[dict[str, Any], dict[str, str]]:
    report = build_enterprise_investor_dashboard(**inputs)
    paths = write_enterprise_investor_dashboard(report, output_dir, output_files)
    return report, paths
