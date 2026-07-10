"""Browser-ready performance analytics dashboard for the paper-only Dividend Bot.

Reads existing report artifacts only and writes JSON, Markdown, and standalone HTML.
This reporting module never launches external programs, contacts trading platforms,
or performs trading actions.
"""
from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

MODULE_NAME = "performance_analytics_dashboard"
MODULE_VERSION = "1.1.1"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_INPUT_FILES = {
    "daily_command_center": "daily_portfolio_command_center.json",
    "weekly_review": "weekly_portfolio_review.json",
    "monthly_review": "monthly_portfolio_review.json",
    "strategy_analytics": "strategy_performance_analytics.json",
    "portfolio_lifecycle": "portfolio_lifecycle_report.json",
}

DEFAULT_OUTPUT_FILES = {
    "json": "performance_analytics_dashboard.json",
    "markdown": "performance_analytics_dashboard.md",
    "html": "performance_analytics_dashboard.html",
}

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "reporting_only is enforced as True",
    "reporting reads local artifacts only",
    "external programs are never launched",
    "trading platforms are never contacted",
    "trading actions are never performed",
]


@dataclass(frozen=True)
class PerformanceAnalyticsDashboardReport:
    module_name: str
    module_version: str
    schema_version: str
    generated_at_utc: str
    paper_trade_mode: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    reporting_only: bool
    dashboard_status: str
    portfolio_value: float
    starting_portfolio_value: float
    capital_appreciation: float
    capital_appreciation_pct: float
    expected_monthly_income: float
    expected_annual_income: float
    yield_on_cost_pct: float
    cash_balance: float
    cash_reserve_target_dollars: float
    reserve_coverage_pct: float
    portfolio_health_score: float
    market_regime: str
    top_opportunity_count: int
    increase_action_count: int
    reduce_action_count: int
    exit_action_count: int
    warnings: list[str]
    errors: list[str]
    available_inputs: list[str]
    missing_inputs: list[str]
    safety_guarantees: list[str]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path.name} must contain a JSON object")
    return dict(value)


def build_performance_analytics_dashboard(
    daily_command_center: Optional[Mapping[str, Any]] = None,
    weekly_review: Optional[Mapping[str, Any]] = None,
    monthly_review: Optional[Mapping[str, Any]] = None,
    strategy_analytics: Optional[Mapping[str, Any]] = None,
    portfolio_lifecycle: Optional[Mapping[str, Any]] = None,
    root_path: str = ".",
    input_files: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    files = dict(DEFAULT_INPUT_FILES)
    if input_files:
        files.update(input_files)

    direct_inputs = {
        "daily_command_center": daily_command_center,
        "weekly_review": weekly_review,
        "monthly_review": monthly_review,
        "strategy_analytics": strategy_analytics,
        "portfolio_lifecycle": portfolio_lifecycle,
    }
    supplied = {name: _mapping(value) for name, value in direct_inputs.items()}
    explicit_input_mode = any(value is not None for value in direct_inputs.values())

    warnings: list[str] = []
    errors: list[str] = []
    root = Path(root_path)

    # Direct-input mode is deterministic: only explicitly supplied payloads count.
    # File-loading mode is used by the command-line writer when no payloads are passed.
    if not explicit_input_mode:
        for name, filename in files.items():
            path = root / filename
            if path.exists():
                try:
                    supplied[name] = _load_json(path)
                except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                    errors.append(f"Unable to read {filename}: {exc}")

    available = [name for name, payload in supplied.items() if payload]
    missing = [name for name in files if name not in available]
    if missing:
        warnings.append("One or more optional dashboard inputs are missing; available inputs were aggregated.")

    daily = supplied["daily_command_center"]
    monthly = supplied["monthly_review"]
    lifecycle = supplied["portfolio_lifecycle"]

    portfolio_value = _number(
        daily.get("portfolio_value", lifecycle.get("portfolio_value", monthly.get("ending_portfolio_value", 0.0)))
    )
    starting_value = _number(monthly.get("starting_portfolio_value", portfolio_value))
    appreciation = portfolio_value - starting_value
    appreciation_pct = (appreciation / starting_value * 100.0) if starting_value > 0 else 0.0
    monthly_income = _number(daily.get("expected_monthly_income", monthly.get("expected_monthly_income", 0.0)))
    annual_income = _number(
        daily.get("expected_annual_income", monthly.get("expected_annual_income", monthly_income * 12.0))
    )
    yield_on_cost = (annual_income / starting_value * 100.0) if starting_value > 0 else 0.0
    cash_balance = _number(daily.get("cash_balance", lifecycle.get("cash_balance", 0.0)))
    reserve_target = _number(
        daily.get("cash_reserve_target_dollars", lifecycle.get("cash_reserve_target_dollars", 0.0))
    )
    reserve_coverage = (cash_balance / reserve_target * 100.0) if reserve_target > 0 else 0.0
    health = _number(daily.get("portfolio_health_score", 0.0))
    regime = str(daily.get("market_regime", lifecycle.get("market_regime", "UNKNOWN")))

    status = "ERROR" if errors else ("PARTIAL" if missing else "COMPLETE")
    report = asdict(PerformanceAnalyticsDashboardReport(
        MODULE_NAME, MODULE_VERSION, SCHEMA_VERSION, _now(), True, False, False, True,
        status, round(portfolio_value, 2), round(starting_value, 2), round(appreciation, 2),
        round(appreciation_pct, 2), round(monthly_income, 2), round(annual_income, 2),
        round(yield_on_cost, 2), round(cash_balance, 2), round(reserve_target, 2),
        round(reserve_coverage, 2), round(health, 2), regime,
        len(daily.get("top_opportunities", [])) if isinstance(daily.get("top_opportunities", []), list) else 0,
        len(daily.get("increase_actions", [])) if isinstance(daily.get("increase_actions", []), list) else 0,
        len(daily.get("reduce_actions", [])) if isinstance(daily.get("reduce_actions", []), list) else 0,
        len(daily.get("exit_actions", [])) if isinstance(daily.get("exit_actions", []), list) else 0,
        warnings, errors, available, missing, list(SAFETY_GUARANTEES),
    ))
    validate_performance_analytics_dashboard(report)
    return report


def validate_performance_analytics_dashboard(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    required = {field.name for field in PerformanceAnalyticsDashboardReport.__dataclass_fields__.values()}
    missing = required - set(payload)
    if missing:
        raise ValueError(f"missing required fields: {', '.join(sorted(missing))}")
    for field, expected in {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
    }.items():
        if payload[field] is not expected:
            raise ValueError(f"{field} must be {expected}")
    if payload["dashboard_status"] not in {"COMPLETE", "PARTIAL", "ERROR"}:
        raise ValueError("unsupported dashboard_status")
    numeric_fields = [
        "portfolio_value", "starting_portfolio_value", "capital_appreciation",
        "capital_appreciation_pct", "expected_monthly_income", "expected_annual_income",
        "yield_on_cost_pct", "cash_balance", "cash_reserve_target_dollars",
        "reserve_coverage_pct", "portfolio_health_score",
    ]
    for field in numeric_fields:
        if isinstance(payload[field], bool) or not isinstance(payload[field], (int, float)):
            raise ValueError(f"{field} must be numeric")
    for field in ["warnings", "errors", "available_inputs", "missing_inputs", "safety_guarantees"]:
        if not isinstance(payload[field], list):
            raise ValueError(f"{field} must be a list")
    return True


def format_performance_analytics_dashboard_markdown(payload: Mapping[str, Any]) -> str:
    validate_performance_analytics_dashboard(payload)
    return "\n".join([
        "# Dividend Bot Performance Analytics Dashboard",
        "",
        f"- Status: {payload['dashboard_status']}",
        f"- Portfolio Value: ${payload['portfolio_value']:.2f}",
        f"- Capital Appreciation: ${payload['capital_appreciation']:.2f} ({payload['capital_appreciation_pct']:.2f}%)",
        f"- Expected Monthly Income: ${payload['expected_monthly_income']:.2f}",
        f"- Expected Annual Income: ${payload['expected_annual_income']:.2f}",
        f"- Yield on Cost: {payload['yield_on_cost_pct']:.2f}%",
        f"- Cash Reserve Coverage: {payload['reserve_coverage_pct']:.2f}%",
        f"- Portfolio Health Score: {payload['portfolio_health_score']:.2f}",
        f"- Market Regime: {payload['market_regime']}",
        "",
        "## Action Counts",
        f"- Top Opportunities: {payload['top_opportunity_count']}",
        f"- Increase: {payload['increase_action_count']}",
        f"- Reduce: {payload['reduce_action_count']}",
        f"- Exit: {payload['exit_action_count']}",
        "",
        "## Warnings",
        *(f"- {item}" for item in payload["warnings"]),
        *(["- None"] if not payload["warnings"] else []),
        "",
        "## Errors",
        *(f"- {item}" for item in payload["errors"]),
        *(["- None"] if not payload["errors"] else []),
    ]) + "\n"


def format_performance_analytics_dashboard_html(payload: Mapping[str, Any]) -> str:
    validate_performance_analytics_dashboard(payload)
    cards = [
        ("Portfolio Value", f"${payload['portfolio_value']:.2f}"),
        ("Capital Appreciation", f"${payload['capital_appreciation']:.2f} ({payload['capital_appreciation_pct']:.2f}%)"),
        ("Monthly Income", f"${payload['expected_monthly_income']:.2f}"),
        ("Annual Income", f"${payload['expected_annual_income']:.2f}"),
        ("Yield on Cost", f"{payload['yield_on_cost_pct']:.2f}%"),
        ("Reserve Coverage", f"{payload['reserve_coverage_pct']:.2f}%"),
        ("Health Score", f"{payload['portfolio_health_score']:.2f}"),
        ("Market Regime", payload["market_regime"]),
    ]
    card_html = "".join(
        f"<section class='card'><h2>{html.escape(title)}</h2><p>{html.escape(str(value))}</p></section>"
        for title, value in cards
    )
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Dividend Bot Dashboard</title><style>
body{{font-family:Arial,sans-serif;margin:0;background:#f4f6f8;color:#1f2937}}header{{padding:24px;background:#111827;color:white}}main{{padding:24px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}.card{{background:white;border-radius:12px;padding:18px;box-shadow:0 2px 8px rgba(0,0,0,.08)}}.card h2{{font-size:14px;margin:0 0 10px;color:#6b7280}}.card p{{font-size:26px;margin:0;font-weight:700}}footer{{padding:24px;color:#6b7280}}
</style></head><body><header><h1>Dividend Bot Performance Analytics Dashboard</h1><p>Status: {html.escape(payload['dashboard_status'])}</p></header><main><div class='grid'>{card_html}</div></main><footer>Paper-only reporting. Local artifacts only.</footer></body></html>"""


def write_performance_analytics_dashboard(
    root_path: str = ".",
    output_files: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    root = Path(root_path)
    payload = build_performance_analytics_dashboard(root_path=root_path)
    (root / files["json"]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_performance_analytics_dashboard_markdown(payload), encoding="utf-8")
    (root / files["html"]).write_text(format_performance_analytics_dashboard_html(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    report = write_performance_analytics_dashboard()
    print(f"Performance Analytics Dashboard: {report['dashboard_status']}")
