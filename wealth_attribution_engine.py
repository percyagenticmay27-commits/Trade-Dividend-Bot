"""Wealth Attribution Engine for the paper-only AI CIO.

Explains why Total Wealth changed by separating market appreciation, income,
SGOV interest, estimated protection value, replacement value created, and
portfolio-turnover impact. Every investor-facing metric includes a permanent
Details record explaining what it means, how it is calculated, why it matters,
and which records contributed to the current value.

This module is reporting-only. It never places orders or communicates with a
brokerage.
"""
from __future__ import annotations

import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

MODULE_NAME = "wealth_attribution_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_OUTPUT_FILES = {
    "json": "wealth_attribution.json",
    "markdown": "wealth_attribution.md",
    "html": "wealth_attribution.html",
}

METRIC_ORDER = (
    "capital_appreciation",
    "dividend_income",
    "sgov_interest",
    "estimated_protection_value",
    "replacement_value_created",
    "portfolio_turnover_impact",
)

METRIC_DETAILS = {
    "capital_appreciation": {
        "label": "Capital Appreciation",
        "definition": "The increase or decrease in market value produced by investments during the reporting period. It excludes dividends and interest.",
        "calculation": "Sum of realized and unrealized price changes attributable to qualifying portfolio allocations during the period.",
        "why_it_matters": "Shows how much Total Wealth changed because the market value of owned investments moved.",
        "is_estimate": False,
    },
    "dividend_income": {
        "label": "Dividend Income",
        "definition": "Cash distributions earned from portfolio investments during the reporting period, including reinvested distributions when supplied.",
        "calculation": "Sum of confirmed dividend and distribution records assigned to portfolio allocations during the period.",
        "why_it_matters": "Shows how much Total Wealth came from portfolio income rather than price appreciation.",
        "is_estimate": False,
    },
    "sgov_interest": {
        "label": "SGOV Interest",
        "definition": "Interest or distributions earned while capital was temporarily held in SGOV as reserve or protected capital.",
        "calculation": "Sum of confirmed SGOV income records during the reporting period.",
        "why_it_matters": "Shows whether protected or waiting capital continued producing income while outside higher-risk opportunities.",
        "is_estimate": False,
    },
    "estimated_protection_value": {
        "label": "Estimated Protection Value",
        "definition": "An estimate of portfolio value preserved after an approved protection action reduced exposure before a subsequent adverse price move.",
        "calculation": "For each protection event, compare the protected capital with the observed movement of the prior allocation over the approved evaluation window.",
        "why_it_matters": "Shows the possible benefit of protection rules while clearly distinguishing estimated preservation from realized investment return.",
        "is_estimate": True,
    },
    "replacement_value_created": {
        "label": "Replacement Value Created",
        "definition": "The measured or estimated difference between a replacement allocation and the allocation it replaced over the same comparison window.",
        "calculation": "Replacement performance minus prior-allocation performance, applied to the capital involved in the replacement event.",
        "why_it_matters": "Shows whether approved replacements improved Total Wealth after capital was moved to a stronger qualified opportunity.",
        "is_estimate": True,
    },
    "portfolio_turnover_impact": {
        "label": "Portfolio Turnover Impact",
        "definition": "The estimated drag or benefit associated with changing allocations, including spread, slippage, fees, and other supplied trading-friction assumptions.",
        "calculation": "Sum of supplied turnover-cost records. Costs should be represented as negative values.",
        "why_it_matters": "Shows whether frequent changes reduced the benefit created by otherwise stronger opportunities.",
        "is_estimate": True,
    },
    "net_total_wealth_contribution": {
        "label": "Net Total Wealth Contribution",
        "definition": "The combined change in Total Wealth explained by all attribution categories in this report.",
        "calculation": "Capital Appreciation + Dividend Income + SGOV Interest + Estimated Protection Value + Replacement Value Created + Portfolio Turnover Impact.",
        "why_it_matters": "Provides one reconciled view of how growth, income, protection, replacements, and turnover affected the portfolio.",
        "is_estimate": True,
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        value = [value]
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise ValueError("attribution records must be a list of mappings")
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("each attribution record must be a mapping")
        result.append(dict(item))
    return result


def _normalize_contributors(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contributors: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        amount = _number(record.get("amount", record.get("value", 0.0)))
        contributors.append({
            "id": str(record.get("id") or f"record-{index}"),
            "allocation": str(record.get("allocation") or record.get("symbol") or record.get("source") or "Unspecified"),
            "amount": round(amount, 4),
            "percentage": round(_number(record.get("percentage")), 4),
            "description": str(record.get("description") or record.get("reason") or "").strip(),
            "source_reference": str(record.get("source_reference") or record.get("journal_entry_id") or "").strip() or None,
            "observed": bool(record.get("observed", True)),
        })
    return contributors


def _metric(metric_id: str, records: Any) -> dict[str, Any]:
    normalized = _normalize_contributors(_records(records))
    detail = dict(METRIC_DETAILS[metric_id])
    amount = round(sum(item["amount"] for item in normalized), 4)
    percentage = round(sum(item["percentage"] for item in normalized), 4)
    return {
        "metric_id": metric_id,
        "label": detail["label"],
        "amount": amount,
        "percentage": percentage,
        "details_link": f"#details-{metric_id.replace('_', '-')}",
        "details": {
            "what_it_is": detail["definition"],
            "how_calculated": detail["calculation"],
            "why_it_matters": detail["why_it_matters"],
            "is_estimate": detail["is_estimate"],
            "contributors": normalized,
        },
    }


def build_wealth_attribution(
    *,
    period_start: str,
    period_end: str,
    starting_portfolio_value: float,
    ending_portfolio_value: float,
    capital_appreciation: Any = None,
    dividend_income: Any = None,
    sgov_interest: Any = None,
    estimated_protection_value: Any = None,
    replacement_value_created: Any = None,
    portfolio_turnover_impact: Any = None,
    portfolio_name: str = "Trade Dividend Bot Paper Portfolio",
    notes: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Build an investor-facing explanation of why Total Wealth changed."""
    if not str(period_start).strip() or not str(period_end).strip():
        raise ValueError("period_start and period_end are required")
    starting_value = _number(starting_portfolio_value)
    ending_value = _number(ending_portfolio_value)
    if starting_value < 0 or ending_value < 0:
        raise ValueError("portfolio values cannot be negative")

    inputs = {
        "capital_appreciation": capital_appreciation,
        "dividend_income": dividend_income,
        "sgov_interest": sgov_interest,
        "estimated_protection_value": estimated_protection_value,
        "replacement_value_created": replacement_value_created,
        "portfolio_turnover_impact": portfolio_turnover_impact,
    }
    metrics = [_metric(metric_id, inputs[metric_id]) for metric_id in METRIC_ORDER]
    explained_change = round(sum(item["amount"] for item in metrics), 4)
    actual_change = round(ending_value - starting_value, 4)
    unexplained_change = round(actual_change - explained_change, 4)
    net_percentage = round((actual_change / starting_value * 100.0), 4) if starting_value else 0.0

    net_detail = dict(METRIC_DETAILS["net_total_wealth_contribution"])
    net_metric = {
        "metric_id": "net_total_wealth_contribution",
        "label": net_detail["label"],
        "amount": actual_change,
        "percentage": net_percentage,
        "details_link": "#details-net-total-wealth-contribution",
        "details": {
            "what_it_is": net_detail["definition"],
            "how_calculated": net_detail["calculation"],
            "why_it_matters": net_detail["why_it_matters"],
            "is_estimate": net_detail["is_estimate"],
            "contributors": [
                {"allocation": item["label"], "amount": item["amount"], "percentage": item["percentage"]}
                for item in metrics
            ],
        },
    }

    positive = [item for item in metrics if item["amount"] > 0]
    negative = [item for item in metrics if item["amount"] < 0]
    primary_driver = max(positive, key=lambda item: item["amount"], default=None)
    largest_drag = min(negative, key=lambda item: item["amount"], default=None)
    warnings: list[str] = []
    if abs(unexplained_change) > max(1.0, abs(actual_change) * 0.01):
        warnings.append("The supplied attribution records do not fully reconcile to the observed portfolio-value change.")
    if any(item["details"]["is_estimate"] and item["amount"] != 0 for item in metrics):
        warnings.append("Estimated Protection Value, Replacement Value Created, and Portfolio Turnover Impact are estimates and are not realized returns unless separately confirmed.")

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
        "portfolio_name": str(portfolio_name),
        "period_start": str(period_start),
        "period_end": str(period_end),
        "starting_portfolio_value": round(starting_value, 4),
        "ending_portfolio_value": round(ending_value, 4),
        "observed_total_wealth_change": actual_change,
        "observed_total_wealth_change_percentage": net_percentage,
        "explained_change": explained_change,
        "unexplained_change": unexplained_change,
        "primary_driver": primary_driver["label"] if primary_driver else None,
        "largest_drag": largest_drag["label"] if largest_drag else None,
        "metrics": metrics,
        "net_total_wealth_contribution": net_metric,
        "details_standard": {
            "required_questions": ["What is it?", "How is it calculated?", "Why does it matter?", "What contributed to today's value?"],
            "investor_rule": "The investor should never have to guess what a metric means.",
        },
        "notes": [str(item) for item in (notes or [])],
        "warnings": warnings,
        "errors": [],
    }


def _money(value: Any) -> str:
    number = _number(value)
    sign = "-" if number < 0 else ""
    return f"{sign}${abs(number):,.2f}"


def _percent(value: Any) -> str:
    number = _number(value)
    return f"{number:+.2f}%"


def format_wealth_attribution_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# AI CIO Wealth Attribution",
        "",
        f"**Reporting Period:** {report.get('period_start')} through {report.get('period_end')}",
        "",
        "## Executive Summary",
        "",
        f"- **Starting Portfolio Value:** {_money(report.get('starting_portfolio_value'))}",
        f"- **Ending Portfolio Value:** {_money(report.get('ending_portfolio_value'))}",
        f"- **Net Total Wealth Contribution:** {_money(report.get('observed_total_wealth_change'))} ({_percent(report.get('observed_total_wealth_change_percentage'))}) [Details](#details-net-total-wealth-contribution)",
        f"- **Primary Driver:** {report.get('primary_driver') or 'No positive contributor'}",
        f"- **Largest Drag:** {report.get('largest_drag') or 'No negative contributor'}",
        "",
        "## Attribution Summary",
        "",
        "| Label | Amount | Portfolio Contribution | Reference |",
        "|---|---:|---:|---|",
    ]
    for metric in report.get("metrics", []):
        lines.append(f"| {metric['label']} | {_money(metric['amount'])} | {_percent(metric['percentage'])} | [Details]({metric['details_link']}) |")
    lines.extend(["", "## Details and Definitions", ""])
    all_metrics = list(report.get("metrics", [])) + [report.get("net_total_wealth_contribution", {})]
    for metric in all_metrics:
        if not metric:
            continue
        anchor = metric["metric_id"].replace("_", "-")
        details = metric["details"]
        lines.extend([
            f"<a id=\"details-{anchor}\"></a>",
            f"### {metric['label']}",
            "",
            f"**Current Value:** {_money(metric['amount'])} ({_percent(metric['percentage'])})",
            "",
            f"**What is it?** {details['what_it_is']}",
            "",
            f"**How is it calculated?** {details['how_calculated']}",
            "",
            f"**Why does it matter?** {details['why_it_matters']}",
            "",
            f"**Estimate Status:** {'Estimated; not a realized return unless separately confirmed.' if details['is_estimate'] else 'Based on supplied observed records.'}",
            "",
            "**Current Contributors**",
            "",
        ])
        contributors = details.get("contributors", [])
        if contributors:
            for contributor in contributors:
                lines.append(f"- **{contributor.get('allocation', 'Unspecified')}:** {_money(contributor.get('amount'))} ({_percent(contributor.get('percentage'))}){(' — ' + contributor.get('description')) if contributor.get('description') else ''}")
        else:
            lines.append("- No contributor records were supplied for this period.")
        lines.append("")

    lines.extend([
        "## How to Interpret This Report",
        "",
        "Capital Appreciation explains market-value movement. Dividend Income and SGOV Interest explain cash income. Estimated Protection Value and Replacement Value Created are counterfactual estimates based on approved comparison methods. Portfolio Turnover Impact estimates the cost of changing allocations. Net Total Wealth Contribution is the observed portfolio-value change for the period.",
        "",
        "## Paper-Only Safety",
        "",
        "This report is advisory and paper-only. It does not place orders or communicate with a brokerage.",
        "",
    ])
    return "\n".join(lines)


def format_wealth_attribution_html(report: Mapping[str, Any]) -> str:
    cards = []
    for metric in report.get("metrics", []):
        details = metric["details"]
        contributors = "".join(
            f"<li><strong>{html.escape(str(item.get('allocation')))}</strong>: {_money(item.get('amount'))} ({_percent(item.get('percentage'))})</li>"
            for item in details.get("contributors", [])
        ) or "<li>No contributor records were supplied.</li>"
        cards.append(
            f"<section class='metric'><h2>{html.escape(metric['label'])}</h2><p class='value'>{_money(metric['amount'])} <span>{_percent(metric['percentage'])}</span></p>"
            f"<details id='details-{metric['metric_id'].replace('_', '-')}'><summary>Details</summary>"
            f"<h3>What is it?</h3><p>{html.escape(details['what_it_is'])}</p>"
            f"<h3>How is it calculated?</h3><p>{html.escape(details['how_calculated'])}</p>"
            f"<h3>Why does it matter?</h3><p>{html.escape(details['why_it_matters'])}</p>"
            f"<h3>Current Contributors</h3><ul>{contributors}</ul></details></section>"
        )
    return """<!doctype html><html><head><meta charset='utf-8'><title>AI CIO Wealth Attribution</title>
<style>body{font-family:Arial,sans-serif;background:#f3f5f8;color:#172033;margin:0}header{background:#111b2e;color:white;padding:24px}main{max-width:1100px;margin:24px auto;padding:0 18px}.summary,.metric{background:white;border-radius:10px;padding:18px;margin-bottom:16px;box-shadow:0 2px 8px #0001}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}.value{font-size:1.5rem;font-weight:bold}.value span{font-size:1rem;font-weight:normal}summary{cursor:pointer;font-weight:bold;margin-top:12px}h3{margin-bottom:4px}</style></head><body>""" + \
        f"<header><h1>AI CIO Wealth Attribution</h1><p>{html.escape(str(report.get('period_start')))} through {html.escape(str(report.get('period_end')))}</p></header>" + \
        f"<main><section class='summary'><h2>Executive Summary</h2><p><strong>Net Total Wealth Contribution:</strong> {_money(report.get('observed_total_wealth_change'))} ({_percent(report.get('observed_total_wealth_change_percentage'))})</p><p><strong>Primary Driver:</strong> {html.escape(str(report.get('primary_driver') or 'None'))}</p><p><strong>Largest Drag:</strong> {html.escape(str(report.get('largest_drag') or 'None'))}</p></section><div class='grid'>{''.join(cards)}</div><section class='summary'><h2>How to Interpret This Report</h2><p>Every metric includes a Details section explaining what it is, how it is calculated, why it matters, and which records contributed to the current value.</p><p>This report is advisory and paper-only.</p></section></main></body></html>"


def write_wealth_attribution(report: Mapping[str, Any], root_path: str = ".", output_files: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    root = Path(root_path)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    root.mkdir(parents=True, exist_ok=True)
    (root / files["json"]).write_text(json.dumps(dict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_wealth_attribution_markdown(report), encoding="utf-8")
    (root / files["html"]).write_text(format_wealth_attribution_html(report), encoding="utf-8")
    return {name: str(root / path) for name, path in files.items()}


def build_and_write_wealth_attribution(root_path: str = ".", **kwargs: Any) -> dict[str, Any]:
    report = build_wealth_attribution(**kwargs)
    report["output_files"] = write_wealth_attribution(report, root_path=root_path)
    return report


if __name__ == "__main__":
    sample = build_and_write_wealth_attribution(
        period_start="2026-07-01",
        period_end="2026-07-12",
        starting_portfolio_value=500.00,
        ending_portfolio_value=539.20,
        capital_appreciation=[{"allocation": "AMDW + PLTU", "amount": 21.55, "percentage": 4.31}],
        dividend_income=[{"allocation": "AMDW", "amount": 10.40, "percentage": 2.08}],
        sgov_interest=[{"allocation": "SGOV", "amount": 1.30, "percentage": 0.26}],
        estimated_protection_value=[{"allocation": "PLTU protection event", "amount": 3.70, "percentage": 0.74, "description": "Estimated value preserved during an earnings-protection window."}],
        replacement_value_created=[{"allocation": "QQQI replaced by AMDW", "amount": 3.05, "percentage": 0.61}],
        portfolio_turnover_impact=[{"allocation": "Replacement friction", "amount": -0.80, "percentage": -0.16}],
    )
    print(f"Wealth Attribution: {sample['observed_total_wealth_change_percentage']:+.2f}%")
