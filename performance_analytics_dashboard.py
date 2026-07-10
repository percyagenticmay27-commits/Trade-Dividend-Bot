"""Browser-ready analytics dashboard for the paper-only Dividend Bot.

The module reads local report artifacts, including the shared read-only market-data
snapshot, and writes JSON, Markdown, and standalone HTML output.
"""
from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

MODULE_NAME = "performance_analytics_dashboard"
MODULE_VERSION = "1.2.0"
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
MARKET_DATA_FILE = "market_data_snapshot.json"
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
    "the dashboard reads local artifacts only",
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


def _market_records(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = snapshot.get("records", [])
    return [dict(row) for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _yield_fraction(value: Any) -> float:
    result = max(0.0, _number(value))
    return result / 100.0 if result > 1.0 else result


def _snapshot_metrics(snapshot: Mapping[str, Any], portfolio_value: float) -> Dict[str, Any]:
    records = _market_records(snapshot)
    if not records:
        return {}
    annual_yield = sum(_yield_fraction(row.get("dividend_yield")) for row in records) / len(records)
    returns = []
    positions = []
    stale_count = 0
    for row in records:
        price = _number(row.get("price"))
        previous = _number(row.get("previous_close"))
        if price > 0 and previous > 0:
            returns.append((price - previous) / previous)
        low = _number(row.get("fifty_two_week_low"))
        high = _number(row.get("fifty_two_week_high"))
        if price > 0 and high > low:
            positions.append((price - low) / (high - low))
        stale_count += int(bool(row.get("is_stale")))
    average_return = sum(returns) / len(returns) if returns else 0.0
    average_position = sum(positions) / len(positions) if positions else 0.5
    score = average_return * 900.0 + (average_position - 0.5) * 80.0
    if score >= 55:
        regime = "STRONG_BULL"
    elif score >= 15:
        regime = "BULL"
    elif score <= -55:
        regime = "STRONG_BEAR"
    elif score <= -15:
        regime = "BEAR"
    else:
        regime = "NEUTRAL"
    annual_income = max(0.0, portfolio_value) * annual_yield
    return {
        "annual_income": annual_income,
        "monthly_income": annual_income / 12.0,
        "average_return": average_return,
        "market_regime": regime,
        "record_count": len(records),
        "stale_count": stale_count,
    }


def build_performance_analytics_dashboard(
    daily_command_center: Optional[Mapping[str, Any]] = None,
    weekly_review: Optional[Mapping[str, Any]] = None,
    monthly_review: Optional[Mapping[str, Any]] = None,
    strategy_analytics: Optional[Mapping[str, Any]] = None,
    portfolio_lifecycle: Optional[Mapping[str, Any]] = None,
    market_data_snapshot: Optional[Mapping[str, Any]] = None,
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
    snapshot = _mapping(market_data_snapshot)
    explicit_input_mode = any(value is not None for value in direct_inputs.values()) or market_data_snapshot is not None
    warnings: list[str] = []
    errors: list[str] = []
    root = Path(root_path)

    if not explicit_input_mode:
        for name, filename in files.items():
            path = root / filename
            if path.exists():
                try:
                    supplied[name] = _load_json(path)
                except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                    errors.append(f"Unable to read {filename}: {exc}")
        snapshot_path = root / MARKET_DATA_FILE
        if snapshot_path.exists():
            try:
                snapshot = _load_json(snapshot_path)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                warnings.append(f"Unable to read {MARKET_DATA_FILE}: {exc}")

    available = [name for name, payload in supplied.items() if payload]
    if snapshot:
        available.append("market_data_snapshot")
    missing = [name for name in files if name not in available]
    if missing:
        warnings.append("One or more optional dashboard inputs are missing; available inputs were aggregated.")

    daily = supplied["daily_command_center"]
    monthly = supplied["monthly_review"]
    lifecycle = supplied["portfolio_lifecycle"]
    portfolio_value = _number(daily.get("portfolio_value", lifecycle.get("portfolio_value", monthly.get("ending_portfolio_value", 0.0))))
    starting_value = _number(monthly.get("starting_portfolio_value", portfolio_value))
    snapshot_values = _snapshot_metrics(snapshot, portfolio_value)

    monthly_income = _number(daily.get("expected_monthly_income", monthly.get("expected_monthly_income", 0.0)))
    annual_income = _number(daily.get("expected_annual_income", monthly.get("expected_annual_income", monthly_income * 12.0)))
    if annual_income <= 0 and snapshot_values:
        annual_income = _number(snapshot_values.get("annual_income"))
        monthly_income = _number(snapshot_values.get("monthly_income"))
        warnings.append("Income values were estimated from the equal-weight market snapshot because upstream income totals were unavailable.")

    appreciation = portfolio_value - starting_value
    appreciation_pct = (appreciation / starting_value * 100.0) if starting_value > 0 else 0.0
    if snapshot_values and abs(appreciation) < 0.005 and portfolio_value > 0:
        daily_return = _number(snapshot_values.get("average_return"))
        if daily_return > -0.99 and abs(daily_return) > 0.000001:
            starting_value = portfolio_value / (1.0 + daily_return)
            appreciation = portfolio_value - starting_value
            appreciation_pct = daily_return * 100.0
            warnings.append("Capital appreciation uses the latest equal-weight market-session change because no upstream cost-basis change was available.")

    yield_on_cost = (annual_income / starting_value * 100.0) if starting_value > 0 else 0.0
    cash_balance = _number(daily.get("cash_balance", lifecycle.get("cash_balance", 0.0)))
    reserve_target = _number(daily.get("cash_reserve_target_dollars", lifecycle.get("cash_reserve_target_dollars", 0.0)))
    reserve_coverage = (cash_balance / reserve_target * 100.0) if reserve_target > 0 else 0.0
    health = _number(daily.get("portfolio_health_score", 0.0))
    regime = str(daily.get("market_regime", lifecycle.get("market_regime", "UNKNOWN")))
    if regime in {"", "UNKNOWN", "None"} and snapshot_values:
        regime = str(snapshot_values.get("market_regime", "UNKNOWN"))
    if snapshot_values.get("stale_count"):
        warnings.append("One or more dashboard metrics used stale cached market records.")

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
    required = set(PerformanceAnalyticsDashboardReport.__dataclass_fields__)
    missing = required - set(payload)
    if missing:
        raise ValueError(f"missing required fields: {', '.join(sorted(missing))}")
    for field, expected in {"paper_trade_mode": True, "live_trading_enabled": False, "broker_execution_enabled": False, "reporting_only": True}.items():
        if payload[field] is not expected:
            raise ValueError(f"{field} must be {expected}")
    if payload["dashboard_status"] not in {"COMPLETE", "PARTIAL", "ERROR"}:
        raise ValueError("unsupported dashboard_status")
    numeric_fields = ["portfolio_value", "starting_portfolio_value", "capital_appreciation", "capital_appreciation_pct", "expected_monthly_income", "expected_annual_income", "yield_on_cost_pct", "cash_balance", "cash_reserve_target_dollars", "reserve_coverage_pct", "portfolio_health_score"]
    for field in numeric_fields:
        if isinstance(payload[field], bool) or not isinstance(payload[field], (int, float)):
            raise ValueError(f"{field} must be numeric")
    for field in ["warnings", "errors", "available_inputs", "missing_inputs", "safety_guarantees"]:
        if not isinstance(payload[field], list):
            raise ValueError(f"{field} must be a list")
    return True


def format_performance_analytics_dashboard_markdown(payload: Mapping[str, Any]) -> str:
    validate_performance_analytics_dashboard(payload)
    lines = [
        "# Dividend Bot Performance Analytics Dashboard", "",
        f"- Status: {payload['dashboard_status']}",
        f"- Portfolio Value: ${payload['portfolio_value']:.2f}",
        f"- Capital Appreciation: ${payload['capital_appreciation']:.2f} ({payload['capital_appreciation_pct']:.2f}%)",
        f"- Expected Monthly Income: ${payload['expected_monthly_income']:.2f}",
        f"- Expected Annual Income: ${payload['expected_annual_income']:.2f}",
        f"- Yield on Cost: {payload['yield_on_cost_pct']:.2f}%",
        f"- Cash Reserve Coverage: {payload['reserve_coverage_pct']:.2f}%",
        f"- Portfolio Health Score: {payload['portfolio_health_score']:.2f}",
        f"- Market Regime: {payload['market_regime']}", "", "## Action Counts",
        f"- Top Opportunities: {payload['top_opportunity_count']}",
        f"- Increase: {payload['increase_action_count']}",
        f"- Reduce: {payload['reduce_action_count']}",
        f"- Exit: {payload['exit_action_count']}", "", "## Warnings",
    ]
    lines.extend(f"- {item}" for item in payload["warnings"]) or lines.append("- None")
    lines += ["", "## Errors"]
    lines.extend(f"- {item}" for item in payload["errors"]) or lines.append("- None")
    return "\n".join(lines) + "\n"


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
    card_html = "".join(f"<section class='card'><h2>{html.escape(title)}</h2><p>{html.escape(str(value))}</p></section>" for title, value in cards)
    warning_html = "".join(f"<li>{html.escape(item)}</li>" for item in payload["warnings"])
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Dividend Bot Dashboard</title><style>
body{{font-family:Arial,sans-serif;margin:0;background:#f4f6f8;color:#1f2937}}header{{padding:24px;background:#111827;color:white}}main{{padding:24px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}.card{{background:white;border-radius:12px;padding:18px;box-shadow:0 2px 8px rgba(0,0,0,.08)}}.card h2{{font-size:14px;margin:0 0 10px;color:#6b7280}}.card p{{font-size:26px;margin:0;font-weight:700}}.notes{{margin-top:22px;background:white;padding:18px;border-radius:12px}}footer{{padding:24px;color:#6b7280}}
</style></head><body><header><h1>Dividend Bot Performance Analytics Dashboard</h1><p>Status: {html.escape(payload['dashboard_status'])}</p></header><main><div class='grid'>{card_html}</div><section class='notes'><h2>Data Notes</h2><ul>{warning_html or '<li>None</li>'}</ul></section></main><footer>Paper-only reporting. Local artifacts only.</footer></body></html>"""


def write_performance_analytics_dashboard(root_path: str = ".", output_files: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    root = Path(root_path)
    root.mkdir(parents=True, exist_ok=True)
    payload = build_performance_analytics_dashboard(root_path=root_path)
    (root / files["json"]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_performance_analytics_dashboard_markdown(payload), encoding="utf-8")
    (root / files["html"]).write_text(format_performance_analytics_dashboard_html(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    report = write_performance_analytics_dashboard()
    print(f"Performance Analytics Dashboard: {report['dashboard_status']}")
