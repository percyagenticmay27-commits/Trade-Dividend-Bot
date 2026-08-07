"""Read-only Dividend Quality scoring from the shared market-data snapshot.

Company securities use operating fundamentals. ETF/fund securities use observable
fund-quality evidence such as multi-year returns, expense ratio, and fund size.
Missing evidence contributes 0 and is disclosed explicitly.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

MODULE_NAME = "dividend_quality_engine"
MODULE_VERSION = "1.1.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
AUTOMATIC_ACTIVATION_ALLOWED = False
REPORTING_ONLY = True

DEFAULT_JSON_OUTPUT = Path("dividend_quality_report.json")
DEFAULT_MARKDOWN_OUTPUT = Path("dividend_quality_report.md")

COMPANY_QUALITY_METRICS = ("return_on_equity", "profit_margin", "operating_margin", "free_cash_flow")
ETF_QUALITY_METRICS = ("three_year_average_return", "five_year_average_return", "expense_ratio", "total_assets")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first(mapping: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in mapping:
            value = _number(mapping.get(key))
            if value is not None:
                return value
    return None


def _ratio(value: float | None) -> float | None:
    if value is None:
        return None
    return value / 100.0 if abs(value) > 2.0 else value


def _score_ratio(value: float | None, thresholds: tuple[tuple[float, float], ...]) -> float:
    if value is None:
        return 0.0
    for minimum, score in thresholds:
        if value >= minimum:
            return score
    return 0.0


def _return_score(value: float | None) -> float:
    return _score_ratio(value, ((0.10, 100.0), (0.06, 85.0), (0.03, 70.0), (0.0, 50.0), (-0.05, 25.0)))


def _expense_score(value: float | None) -> float:
    if value is None or value < 0:
        return 0.0
    if value <= 0.003:
        return 100.0
    if value <= 0.006:
        return 85.0
    if value <= 0.010:
        return 70.0
    if value <= 0.015:
        return 50.0
    return 30.0


def _assets_score(value: float | None) -> float:
    if value is None or value <= 0:
        return 0.0
    if value >= 10_000_000_000:
        return 100.0
    if value >= 2_000_000_000:
        return 85.0
    if value >= 500_000_000:
        return 70.0
    if value >= 100_000_000:
        return 50.0
    return 30.0


def _records(snapshot: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(snapshot, Mapping):
        return []
    rows = snapshot.get("records")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _is_fund(record: Mapping[str, Any], quote: Mapping[str, Any]) -> bool:
    quote_type = str(quote.get("quote_type") or record.get("quote_type") or "").upper()
    return quote_type in {"ETF", "MUTUALFUND", "MONEYMARKET"}


def build_dividend_quality_report(
    market_data_snapshot: Mapping[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []

    for record in _records(market_data_snapshot):
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        quote = record.get("quote") if isinstance(record.get("quote"), Mapping) else {}

        if _is_fund(record, quote):
            values = {
                "three_year_average_return": _ratio(_first(quote, "three_year_average_return", "threeYearAverageReturn")),
                "five_year_average_return": _ratio(_first(quote, "five_year_average_return", "fiveYearAverageReturn")),
                "expense_ratio": _ratio(_first(quote, "annual_report_expense_ratio", "annualReportExpenseRatio")),
                "total_assets": _first(quote, "total_assets", "totalAssets"),
            }
            metric_scores = {
                "three_year_average_return": _return_score(values["three_year_average_return"]),
                "five_year_average_return": _return_score(values["five_year_average_return"]),
                "expense_ratio": _expense_score(values["expense_ratio"]),
                "total_assets": _assets_score(values["total_assets"]),
            }
            metrics = ETF_QUALITY_METRICS
            model = "ETF_FUND_QUALITY"
        else:
            roe = _ratio(_first(quote, "return_on_equity", "returnOnEquity", "roe"))
            profit_margin = _ratio(_first(quote, "profit_margin", "profit_margins", "profitMargins"))
            operating_margin = _ratio(_first(quote, "operating_margin", "operating_margins", "operatingMargins"))
            free_cash_flow = _first(quote, "free_cash_flow", "free_cashflow", "freeCashflow")
            values = {
                "return_on_equity": roe,
                "profit_margin": profit_margin,
                "operating_margin": operating_margin,
                "free_cash_flow": free_cash_flow,
            }
            metric_scores = {
                "return_on_equity": _score_ratio(roe, ((0.25, 100.0), (0.15, 85.0), (0.08, 70.0), (0.0, 50.0))),
                "profit_margin": _score_ratio(profit_margin, ((0.20, 100.0), (0.10, 85.0), (0.05, 70.0), (0.0, 50.0))),
                "operating_margin": _score_ratio(operating_margin, ((0.20, 100.0), (0.10, 85.0), (0.05, 70.0), (0.0, 50.0))),
                "free_cash_flow": 100.0 if free_cash_flow is not None and free_cash_flow > 0 else 0.0,
            }
            metrics = COMPANY_QUALITY_METRICS
            model = "COMPANY_FUNDAMENTALS"

        missing = [name for name, value in values.items() if value is None]
        score = round(sum(metric_scores.values()) / len(metrics), 2)
        if missing:
            warnings.append(f"{symbol}: missing quality evidence defaults to 0: {', '.join(missing)}")

        entries.append({
            "symbol": symbol,
            "quality_score": score,
            "dividend_quality_score": score,
            "evidence_model": model,
            "metric_values": values,
            "metric_scores": metric_scores,
            "missing_metrics": missing,
            "evidence_status": "AVAILABLE" if not missing else ("PARTIAL" if len(missing) < len(metrics) else "NOT_REPORTED"),
        })

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "generated_at_utc": _now(),
        "paper_trade_mode": True,
        "reporting_only": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "order_placement_enabled": False,
        "capital_movement_enabled": False,
        "automatic_activation_allowed": False,
        "entries": entries,
        "entry_count": len(entries),
        "missing_evidence_policy": "MISSING_EVIDENCE_EQUALS_ZERO",
        "warnings": warnings,
        "errors": [],
    }


def format_dividend_quality_markdown(report: Mapping[str, Any]) -> str:
    lines = ["# Dividend Quality Report", "", f"Generated: {report.get('generated_at_utc', '')}", ""]
    entries = report.get("entries") if isinstance(report.get("entries"), list) else []
    if not entries:
        lines.append("No quality evidence records were available.")
    for row in entries:
        if not isinstance(row, Mapping):
            continue
        lines.extend([
            f"## {row.get('symbol', 'UNKNOWN')}",
            f"- Quality Score: {row.get('quality_score', 0)}",
            f"- Evidence Model: {row.get('evidence_model', 'UNKNOWN')}",
            f"- Evidence Status: {row.get('evidence_status', 'NOT_REPORTED')}",
            f"- Missing Metrics: {', '.join(row.get('missing_metrics', [])) or 'None'}",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def write_dividend_quality_report(
    market_data_snapshot: Mapping[str, Any] | None = None,
    *,
    root_dir: str | Path = ".",
    json_output: str | Path = DEFAULT_JSON_OUTPUT,
    markdown_output: str | Path = DEFAULT_MARKDOWN_OUTPUT,
) -> dict[str, Any]:
    root = Path(root_dir)
    report = build_dividend_quality_report(market_data_snapshot)
    json_path = Path(json_output)
    md_path = Path(markdown_output)
    if not json_path.is_absolute():
        json_path = root / json_path
    if not md_path.is_absolute():
        md_path = root / md_path
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_dividend_quality_markdown(report), encoding="utf-8")
    return report
