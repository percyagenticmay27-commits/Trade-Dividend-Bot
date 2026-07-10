"""
Portfolio Forecast Engine for the Dividend Bot.

Produces deterministic, paper-only portfolio projections under conservative,
expected, and optimistic scenarios. Forecasts are planning estimates only and
never place orders or connect to brokerage systems.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping

MODULE_NAME = "portfolio_forecast_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

CONSERVATIVE = "CONSERVATIVE"
EXPECTED = "EXPECTED"
OPTIMISTIC = "OPTIMISTIC"
SUPPORTED_SCENARIOS = [CONSERVATIVE, EXPECTED, OPTIMISTIC]
SUPPORTED_CONFIDENCE_LEVELS = ["LOW", "MEDIUM", "HIGH"]
CASH_SHIELD_SYMBOL = "SGOV"
DEFAULT_FORECAST_YEARS = 10
DEFAULT_MONTHLY_INCOME_MILESTONES = [100.0, 500.0, 1000.0]

SCENARIO_ASSUMPTIONS = {
    CONSERVATIVE: {
        "annual_capital_growth_rate": 0.04,
        "annual_dividend_growth_rate": 0.02,
        "annual_cash_yield": 0.025,
        "confidence": 0.55,
        "confidence_level": "LOW",
    },
    EXPECTED: {
        "annual_capital_growth_rate": 0.08,
        "annual_dividend_growth_rate": 0.06,
        "annual_cash_yield": 0.035,
        "confidence": 0.70,
        "confidence_level": "MEDIUM",
    },
    OPTIMISTIC: {
        "annual_capital_growth_rate": 0.12,
        "annual_dividend_growth_rate": 0.10,
        "annual_cash_yield": 0.045,
        "confidence": 0.50,
        "confidence_level": "LOW",
    },
}

FORECAST_PRINCIPLES = [
    "Forecasts are deterministic planning estimates, not guarantees.",
    "Income and capital growth are projected separately.",
    "Reinvested income compounds into future portfolio value.",
    "SGOV reserve growth is projected independently using scenario cash yield.",
    "No live market data or external APIs are consumed.",
]

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "reporting_only is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no Robinhood execution is performed",
    "no brokerage execution is performed",
    "no order placement is performed",
    "forecasts are informational estimates only",
]

REPORT_REQUIRED_FIELDS = [
    "bot_name", "bot_type", "module_name", "module_version", "schema_version",
    "generated_by", "generated_at_utc", "paper_trade_mode", "live_trading_enabled",
    "broker_execution_enabled", "reporting_only", "starting_portfolio_value",
    "starting_monthly_income", "starting_cash_reserve", "annual_contribution",
    "forecast_years", "supported_scenarios", "scenario_assumptions", "forecasts",
    "income_milestones", "warnings", "errors", "forecast_principles",
    "safety_guarantees",
]

FORECAST_FIELDS = [
    "scenario", "year", "projected_portfolio_value", "projected_monthly_income",
    "projected_annual_income", "projected_cash_reserve", "yield_on_cost",
    "annual_capital_growth_rate", "annual_dividend_growth_rate", "confidence",
    "confidence_level",
]


@dataclass(frozen=True)
class ForecastScenario:
    scenario: str
    annual_capital_growth_rate: float
    annual_dividend_growth_rate: float
    annual_cash_yield: float
    confidence: float
    confidence_level: str


@dataclass(frozen=True)
class PortfolioForecastPoint:
    scenario: str
    year: int
    projected_portfolio_value: float
    projected_monthly_income: float
    projected_annual_income: float
    projected_cash_reserve: float
    yield_on_cost: float
    annual_capital_growth_rate: float
    annual_dividend_growth_rate: float
    confidence: float
    confidence_level: str


@dataclass(frozen=True)
class PortfolioForecastReport:
    bot_name: str
    bot_type: str
    module_name: str
    module_version: str
    schema_version: str
    generated_by: str
    generated_at_utc: str
    paper_trade_mode: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    reporting_only: bool
    starting_portfolio_value: float
    starting_monthly_income: float
    starting_cash_reserve: float
    annual_contribution: float
    forecast_years: int
    supported_scenarios: List[str]
    scenario_assumptions: Dict[str, Dict[str, Any]]
    forecasts: List[Dict[str, Any]]
    income_milestones: List[Dict[str, Any]]
    warnings: List[str]
    errors: List[str]
    forecast_principles: List[str]
    safety_guarantees: List[str]


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def project_scenario(
    scenario: str,
    starting_portfolio_value: float,
    starting_monthly_income: float,
    starting_cash_reserve: float,
    annual_contribution: float = 0.0,
    forecast_years: int = DEFAULT_FORECAST_YEARS,
) -> List[Dict[str, Any]]:
    if scenario not in SUPPORTED_SCENARIOS:
        raise ValueError("unsupported forecast scenario")
    if starting_portfolio_value <= 0:
        raise ValueError("starting_portfolio_value must be positive")
    if starting_monthly_income < 0 or starting_cash_reserve < 0 or annual_contribution < 0:
        raise ValueError("income, reserve, and contribution values must be non-negative")
    if not isinstance(forecast_years, int) or isinstance(forecast_years, bool) or forecast_years <= 0:
        raise ValueError("forecast_years must be a positive integer")

    assumptions = SCENARIO_ASSUMPTIONS[scenario]
    portfolio_value = float(starting_portfolio_value)
    monthly_income = float(starting_monthly_income)
    cash_reserve = float(starting_cash_reserve)
    points: List[Dict[str, Any]] = []

    for year in range(1, forecast_years + 1):
        annual_income = monthly_income * 12.0
        reinvested_income = annual_income
        portfolio_value = (
            portfolio_value * (1.0 + assumptions["annual_capital_growth_rate"])
            + reinvested_income
            + annual_contribution
        )
        monthly_income *= 1.0 + assumptions["annual_dividend_growth_rate"]
        cash_reserve *= 1.0 + assumptions["annual_cash_yield"]
        yield_on_cost = (monthly_income * 12.0) / starting_portfolio_value

        points.append(asdict(PortfolioForecastPoint(
            scenario=scenario,
            year=year,
            projected_portfolio_value=round(portfolio_value, 2),
            projected_monthly_income=round(monthly_income, 2),
            projected_annual_income=round(monthly_income * 12.0, 2),
            projected_cash_reserve=round(cash_reserve, 2),
            yield_on_cost=round(yield_on_cost, 4),
            annual_capital_growth_rate=assumptions["annual_capital_growth_rate"],
            annual_dividend_growth_rate=assumptions["annual_dividend_growth_rate"],
            confidence=assumptions["confidence"],
            confidence_level=assumptions["confidence_level"],
        )))
    return points


def calculate_income_milestones(
    forecasts: List[Mapping[str, Any]],
    milestones: List[float] | None = None,
) -> List[Dict[str, Any]]:
    targets = list(milestones or DEFAULT_MONTHLY_INCOME_MILESTONES)
    results: List[Dict[str, Any]] = []
    for scenario in SUPPORTED_SCENARIOS:
        scenario_points = [point for point in forecasts if point.get("scenario") == scenario]
        for target in targets:
            year_reached = None
            for point in scenario_points:
                if _number(point.get("projected_monthly_income", 0.0)) >= target:
                    year_reached = int(point["year"])
                    break
            results.append({
                "scenario": scenario,
                "monthly_income_target": float(target),
                "year_reached": year_reached,
                "reached_within_forecast": year_reached is not None,
            })
    return results


def build_portfolio_forecast_report(
    starting_portfolio_value: float = 500.0,
    starting_monthly_income: float = 0.0,
    starting_cash_reserve: float = 100.0,
    annual_contribution: float = 0.0,
    forecast_years: int = DEFAULT_FORECAST_YEARS,
) -> Dict[str, Any]:
    forecasts: List[Dict[str, Any]] = []
    for scenario in SUPPORTED_SCENARIOS:
        forecasts.extend(project_scenario(
            scenario,
            starting_portfolio_value,
            starting_monthly_income,
            starting_cash_reserve,
            annual_contribution,
            forecast_years,
        ))

    warnings = [
        "Forecasts are estimates and should not be interpreted as guaranteed investment outcomes."
    ]
    if starting_monthly_income == 0:
        warnings.append("Starting monthly income is zero; income milestones may not be reached without future income inputs.")

    payload = asdict(PortfolioForecastReport(
        bot_name=BOT_NAME,
        bot_type=BOT_TYPE,
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION,
        generated_by=GENERATED_BY,
        generated_at_utc=_now_utc(),
        paper_trade_mode=True,
        live_trading_enabled=False,
        broker_execution_enabled=False,
        reporting_only=True,
        starting_portfolio_value=float(starting_portfolio_value),
        starting_monthly_income=float(starting_monthly_income),
        starting_cash_reserve=float(starting_cash_reserve),
        annual_contribution=float(annual_contribution),
        forecast_years=forecast_years,
        supported_scenarios=list(SUPPORTED_SCENARIOS),
        scenario_assumptions={key: dict(value) for key, value in SCENARIO_ASSUMPTIONS.items()},
        forecasts=forecasts,
        income_milestones=calculate_income_milestones(forecasts),
        warnings=warnings,
        errors=[],
        forecast_principles=list(FORECAST_PRINCIPLES),
        safety_guarantees=list(SAFETY_GUARANTEES),
    ))
    validate_portfolio_forecast_report(payload)
    return payload


def validate_portfolio_forecast_report(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    for field_name in REPORT_REQUIRED_FIELDS:
        if field_name not in payload:
            raise ValueError(f"missing required field: {field_name}")

    expected_flags = {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
    }
    for field_name, expected in expected_flags.items():
        if payload[field_name] is not expected:
            raise ValueError(f"{field_name} must be {expected}")

    for field_name in [
        "starting_portfolio_value", "starting_monthly_income", "starting_cash_reserve",
        "annual_contribution",
    ]:
        value = payload[field_name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"{field_name} must be a non-negative number")
    if payload["starting_portfolio_value"] <= 0:
        raise ValueError("starting_portfolio_value must be positive")
    if not isinstance(payload["forecast_years"], int) or isinstance(payload["forecast_years"], bool) or payload["forecast_years"] <= 0:
        raise ValueError("forecast_years must be a positive integer")

    if payload["supported_scenarios"] != SUPPORTED_SCENARIOS:
        raise ValueError("supported_scenarios must match approved list")
    if payload["scenario_assumptions"] != SCENARIO_ASSUMPTIONS:
        raise ValueError("scenario_assumptions must match approved model")

    for list_field in ["forecasts", "income_milestones", "warnings", "errors", "forecast_principles", "safety_guarantees"]:
        if not isinstance(payload[list_field], list):
            raise ValueError(f"{list_field} must be a list")

    expected_forecast_count = payload["forecast_years"] * len(SUPPORTED_SCENARIOS)
    if len(payload["forecasts"]) != expected_forecast_count:
        raise ValueError("forecast row count does not match scenarios and forecast_years")

    for row in payload["forecasts"]:
        if not isinstance(row, Mapping):
            raise ValueError("forecast rows must be mappings")
        for field_name in FORECAST_FIELDS:
            if field_name not in row:
                raise ValueError(f"forecast row missing field: {field_name}")
        if row["scenario"] not in SUPPORTED_SCENARIOS:
            raise ValueError("forecast scenario unsupported")
        if row["confidence_level"] not in SUPPORTED_CONFIDENCE_LEVELS:
            raise ValueError("forecast confidence_level unsupported")
        if not isinstance(row["year"], int) or row["year"] <= 0:
            raise ValueError("forecast year must be a positive integer")
        for field_name in [
            "projected_portfolio_value", "projected_monthly_income", "projected_annual_income",
            "projected_cash_reserve", "yield_on_cost", "annual_capital_growth_rate",
            "annual_dividend_growth_rate", "confidence",
        ]:
            value = row[field_name]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative number")
        if not 0.0 <= row["confidence"] <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
    return True


def write_portfolio_forecast_report_json(path: str = "portfolio_forecast_report.json") -> Dict[str, Any]:
    payload = build_portfolio_forecast_report()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_portfolio_forecast_report_json(path: str = "portfolio_forecast_report.json") -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_portfolio_forecast_report(payload)
    return payload


def write_portfolio_forecast_report_csv(path: str = "portfolio_forecast_report.csv") -> Dict[str, Any]:
    payload = build_portfolio_forecast_report()
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FORECAST_FIELDS)
        writer.writeheader()
        for row in payload["forecasts"]:
            writer.writerow({field: row.get(field, "") for field in FORECAST_FIELDS})
    return payload


def format_portfolio_forecast_report_markdown(payload: Mapping[str, Any]) -> str:
    validate_portfolio_forecast_report(payload)
    lines = [
        "# Portfolio Forecast Report",
        "",
        f"- Starting Portfolio Value: ${payload['starting_portfolio_value']:.2f}",
        f"- Starting Monthly Income: ${payload['starting_monthly_income']:.2f}",
        f"- Starting Cash Reserve: ${payload['starting_cash_reserve']:.2f}",
        f"- Forecast Years: {payload['forecast_years']}",
        "",
        "## Forecast Scenarios",
        "",
        "| Scenario | Year | Portfolio Value | Monthly Income | Annual Income | Cash Reserve | Yield on Cost |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["forecasts"]:
        lines.append(
            f"| {row['scenario']} | {row['year']} | {row['projected_portfolio_value']} | "
            f"{row['projected_monthly_income']} | {row['projected_annual_income']} | "
            f"{row['projected_cash_reserve']} | {row['yield_on_cost']} |"
        )
    lines.extend(["", "## Income Milestones"])
    for milestone in payload["income_milestones"]:
        year_text = milestone["year_reached"] if milestone["year_reached"] is not None else "Not reached"
        lines.append(
            f"- {milestone['scenario']}: ${milestone['monthly_income_target']:.2f}/month — {year_text}"
        )
    lines.extend(["", "## Forecast Principles"])
    lines.extend(f"- {item}" for item in payload["forecast_principles"])
    lines.extend(["", "## Safety Guarantees"])
    lines.extend(f"- {item}" for item in payload["safety_guarantees"])
    return "\n".join(lines) + "\n"


def write_portfolio_forecast_report_markdown(path: str = "portfolio_forecast_report.md") -> Dict[str, Any]:
    payload = build_portfolio_forecast_report()
    Path(path).write_text(format_portfolio_forecast_report_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_portfolio_forecast_report_json()
    write_portfolio_forecast_report_csv()
    write_portfolio_forecast_report_markdown()
