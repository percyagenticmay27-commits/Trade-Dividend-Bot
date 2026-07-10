"""
Portfolio History Engine for the Dividend Bot.

Creates permanent, append-only paper portfolio snapshots for daily, weekly, and
monthly history. Records actual results separately from forecasts and provides a
five-year live-history retention policy with archive metadata for older records.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

MODULE_NAME = "portfolio_history_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True
HISTORY_RETENTION_YEARS = 5
SUPPORTED_PERIODS = ["DAILY", "WEEKLY", "MONTHLY"]
SUPPORTED_RECORD_TYPES = ["ACTUAL_RESULT", "FORECAST", "DECISION", "INCOME", "BENCHMARK"]
HISTORY_ROOT = "results/history"
SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "reporting_only is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "history records are append-only",
    "actual results remain separate from forecasts",
    "no Robinhood execution is performed",
    "no brokerage execution is performed",
    "no order placement is performed",
]
RETENTION_POLICY = [
    "Keep daily, weekly, monthly, and annual summaries available for five years.",
    "Records older than five years become eligible for dated ZIP archival.",
    "Archived records are never deleted and remain discoverable by archive metadata.",
    "Existing snapshots are never overwritten.",
]
SNAPSHOT_FIELDS = [
    "snapshot_id", "recorded_at_utc", "period", "record_type", "portfolio_value",
    "cash_balance", "sgov_balance", "total_return_pct", "monthly_return_pct",
    "annualized_return_pct", "monthly_income", "annual_income", "income_growth_pct",
    "max_drawdown_pct", "opportunity_score", "conviction_score", "momentum_score",
    "entry_score", "technical_score", "benchmark_return_pct", "benchmark_gap_pct",
    "objective_monthly_return_pct", "minimum_annual_return_pct", "notes",
]
REPORT_REQUIRED_FIELDS = [
    "bot_name", "bot_type", "module_name", "module_version", "schema_version",
    "generated_by", "generated_at_utc", "paper_trade_mode", "live_trading_enabled",
    "broker_execution_enabled", "reporting_only", "history_root",
    "history_retention_years", "supported_periods", "supported_record_types",
    "snapshots", "snapshot_count", "actual_result_count", "forecast_count",
    "archive_candidates", "warnings", "errors", "retention_policy",
    "safety_guarantees",
]

@dataclass(frozen=True)
class PortfolioHistorySnapshot:
    snapshot_id: str
    recorded_at_utc: str
    period: str
    record_type: str
    portfolio_value: float = 0.0
    cash_balance: float = 0.0
    sgov_balance: float = 0.0
    total_return_pct: float = 0.0
    monthly_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    monthly_income: float = 0.0
    annual_income: float = 0.0
    income_growth_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    opportunity_score: float = 0.0
    conviction_score: float = 0.0
    momentum_score: float = 0.0
    entry_score: float = 0.0
    technical_score: float = 0.0
    benchmark_return_pct: float = 0.0
    benchmark_gap_pct: float = 0.0
    objective_monthly_return_pct: float = 4.0
    minimum_annual_return_pct: float = 20.0
    notes: str = ""

@dataclass(frozen=True)
class PortfolioHistoryReport:
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
    history_root: str
    history_retention_years: int
    supported_periods: List[str]
    supported_record_types: List[str]
    snapshots: List[Dict[str, Any]]
    snapshot_count: int
    actual_result_count: int
    forecast_count: int
    archive_candidates: List[Dict[str, Any]]
    warnings: List[str]
    errors: List[str]
    retention_policy: List[str]
    safety_guarantees: List[str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _bounded_score(value: Any) -> float:
    return max(0.0, min(100.0, _number(value, 0.0)))


def _snapshot_id(recorded_at_utc: str, period: str, record_type: str) -> str:
    cleaned = recorded_at_utc.replace(":", "").replace("-", "").replace("+", "").replace("Z", "Z")
    return f"{cleaned}_{period}_{record_type}"


def build_history_snapshot(payload: Mapping[str, Any] | None = None, period: str = "DAILY", record_type: str = "ACTUAL_RESULT") -> Dict[str, Any]:
    payload = dict(payload or {})
    if period not in SUPPORTED_PERIODS:
        raise ValueError("period must be supported")
    if record_type not in SUPPORTED_RECORD_TYPES:
        raise ValueError("record_type must be supported")
    recorded_at = payload.get("recorded_at_utc", _utc_now())
    if not isinstance(recorded_at, str) or not recorded_at.strip():
        raise ValueError("recorded_at_utc must be a non-empty string")
    benchmark_return = _number(payload.get("benchmark_return_pct", 0.0))
    total_return = _number(payload.get("total_return_pct", 0.0))
    snapshot = asdict(PortfolioHistorySnapshot(
        snapshot_id=_snapshot_id(recorded_at, period, record_type),
        recorded_at_utc=recorded_at,
        period=period,
        record_type=record_type,
        portfolio_value=max(0.0, _number(payload.get("portfolio_value", 0.0))),
        cash_balance=max(0.0, _number(payload.get("cash_balance", 0.0))),
        sgov_balance=max(0.0, _number(payload.get("sgov_balance", 0.0))),
        total_return_pct=total_return,
        monthly_return_pct=_number(payload.get("monthly_return_pct", 0.0)),
        annualized_return_pct=_number(payload.get("annualized_return_pct", 0.0)),
        monthly_income=max(0.0, _number(payload.get("monthly_income", 0.0))),
        annual_income=max(0.0, _number(payload.get("annual_income", 0.0))),
        income_growth_pct=_number(payload.get("income_growth_pct", 0.0)),
        max_drawdown_pct=_number(payload.get("max_drawdown_pct", 0.0)),
        opportunity_score=_bounded_score(payload.get("opportunity_score", 0.0)),
        conviction_score=_bounded_score(payload.get("conviction_score", 0.0)),
        momentum_score=_bounded_score(payload.get("momentum_score", 0.0)),
        entry_score=_bounded_score(payload.get("entry_score", 0.0)),
        technical_score=_bounded_score(payload.get("technical_score", 0.0)),
        benchmark_return_pct=benchmark_return,
        benchmark_gap_pct=round(total_return - benchmark_return, 4),
        objective_monthly_return_pct=_number(payload.get("objective_monthly_return_pct", 4.0), 4.0),
        minimum_annual_return_pct=_number(payload.get("minimum_annual_return_pct", 20.0), 20.0),
        notes=str(payload.get("notes", "")),
    ))
    validate_history_snapshot(snapshot)
    return snapshot


def validate_history_snapshot(snapshot: Any) -> bool:
    if not isinstance(snapshot, Mapping):
        raise ValueError("snapshot must be a mapping")
    missing = [field for field in SNAPSHOT_FIELDS if field not in snapshot]
    if missing:
        raise ValueError(f"snapshot missing required fields: {', '.join(missing)}")
    if snapshot["period"] not in SUPPORTED_PERIODS:
        raise ValueError("period must be supported")
    if snapshot["record_type"] not in SUPPORTED_RECORD_TYPES:
        raise ValueError("record_type must be supported")
    for field_name in ["snapshot_id", "recorded_at_utc", "notes"]:
        if not isinstance(snapshot[field_name], str):
            raise ValueError(f"{field_name} must be a string")
    for field_name in SNAPSHOT_FIELDS:
        if field_name in {"snapshot_id", "recorded_at_utc", "period", "record_type", "notes"}:
            continue
        if isinstance(snapshot[field_name], bool) or not isinstance(snapshot[field_name], (int, float)):
            raise ValueError(f"{field_name} must be numeric")
    for field_name in ["portfolio_value", "cash_balance", "sgov_balance", "monthly_income", "annual_income"]:
        if snapshot[field_name] < 0:
            raise ValueError(f"{field_name} must be non-negative")
    for field_name in ["opportunity_score", "conviction_score", "momentum_score", "entry_score", "technical_score"]:
        if not 0 <= snapshot[field_name] <= 100:
            raise ValueError(f"{field_name} must be between 0 and 100")
    return True


def find_archive_candidates(snapshots: Iterable[Mapping[str, Any]], as_of_date: date | None = None) -> List[Dict[str, Any]]:
    as_of_date = as_of_date or date.today()
    cutoff_year = as_of_date.year - HISTORY_RETENTION_YEARS
    candidates = []
    for snapshot in snapshots:
        validate_history_snapshot(snapshot)
        try:
            recorded_year = int(snapshot["recorded_at_utc"][:4])
        except (TypeError, ValueError):
            continue
        if recorded_year < cutoff_year:
            candidates.append({
                "snapshot_id": snapshot["snapshot_id"],
                "recorded_at_utc": snapshot["recorded_at_utc"],
                "archive_name": f"portfolio_history_{recorded_year}.zip",
                "archive_eligible": True,
            })
    return candidates


def build_portfolio_history_report(snapshots: Iterable[Mapping[str, Any]] | None = None, as_of_date: date | None = None) -> Dict[str, Any]:
    normalized = [dict(snapshot) for snapshot in (snapshots or [])]
    for snapshot in normalized:
        validate_history_snapshot(snapshot)
    normalized.sort(key=lambda item: (item["recorded_at_utc"], item["snapshot_id"]))
    warnings = []
    if not normalized:
        warnings.append("No snapshots supplied; generated valid empty history report.")
    payload = asdict(PortfolioHistoryReport(
        bot_name=BOT_NAME,
        bot_type=BOT_TYPE,
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION,
        generated_by=GENERATED_BY,
        generated_at_utc=_utc_now(),
        paper_trade_mode=True,
        live_trading_enabled=False,
        broker_execution_enabled=False,
        reporting_only=True,
        history_root=HISTORY_ROOT,
        history_retention_years=HISTORY_RETENTION_YEARS,
        supported_periods=list(SUPPORTED_PERIODS),
        supported_record_types=list(SUPPORTED_RECORD_TYPES),
        snapshots=normalized,
        snapshot_count=len(normalized),
        actual_result_count=sum(1 for item in normalized if item["record_type"] == "ACTUAL_RESULT"),
        forecast_count=sum(1 for item in normalized if item["record_type"] == "FORECAST"),
        archive_candidates=find_archive_candidates(normalized, as_of_date),
        warnings=warnings,
        errors=[],
        retention_policy=list(RETENTION_POLICY),
        safety_guarantees=list(SAFETY_GUARANTEES),
    ))
    validate_portfolio_history_report(payload)
    return payload


def validate_portfolio_history_report(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    missing = [field for field in REPORT_REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"payload missing required fields: {', '.join(missing)}")
    required_flags = {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
    }
    for field_name, required_value in required_flags.items():
        if payload[field_name] is not required_value:
            raise ValueError(f"{field_name} must be {required_value}")
    if payload["history_retention_years"] != HISTORY_RETENTION_YEARS:
        raise ValueError("history_retention_years must match approved policy")
    if payload["supported_periods"] != SUPPORTED_PERIODS:
        raise ValueError("supported_periods must match approved list")
    if payload["supported_record_types"] != SUPPORTED_RECORD_TYPES:
        raise ValueError("supported_record_types must match approved list")
    for field_name in ["snapshots", "archive_candidates", "warnings", "errors", "retention_policy", "safety_guarantees"]:
        if not isinstance(payload[field_name], list):
            raise ValueError(f"{field_name} must be a list")
    if payload["snapshot_count"] != len(payload["snapshots"]):
        raise ValueError("snapshot_count must match snapshots length")
    if payload["actual_result_count"] != sum(1 for item in payload["snapshots"] if item["record_type"] == "ACTUAL_RESULT"):
        raise ValueError("actual_result_count mismatch")
    if payload["forecast_count"] != sum(1 for item in payload["snapshots"] if item["record_type"] == "FORECAST"):
        raise ValueError("forecast_count mismatch")
    for snapshot in payload["snapshots"]:
        validate_history_snapshot(snapshot)
    return True


def history_directory_for_snapshot(snapshot: Mapping[str, Any], root_path: str = HISTORY_ROOT) -> Path:
    validate_history_snapshot(snapshot)
    year_month = snapshot["recorded_at_utc"][:7]
    period_folder = snapshot["period"].lower()
    return Path(root_path) / year_month / period_folder


def write_history_snapshot(snapshot: Mapping[str, Any], root_path: str = HISTORY_ROOT) -> Path:
    validate_history_snapshot(snapshot)
    directory = history_directory_for_snapshot(snapshot, root_path)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{snapshot['snapshot_id']}.json"
    if path.exists():
        raise FileExistsError(f"history snapshot already exists: {path}")
    path.write_text(json.dumps(dict(snapshot), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_portfolio_history_json(path: str = "portfolio_history.json", snapshots: Iterable[Mapping[str, Any]] | None = None) -> Dict[str, Any]:
    payload = build_portfolio_history_report(snapshots)
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_portfolio_history_json(path: str = "portfolio_history.json") -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_portfolio_history_report(payload)
    return payload


def write_portfolio_history_csv(path: str = "portfolio_history.csv", snapshots: Iterable[Mapping[str, Any]] | None = None) -> Dict[str, Any]:
    payload = build_portfolio_history_report(snapshots)
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SNAPSHOT_FIELDS)
        writer.writeheader()
        for snapshot in payload["snapshots"]:
            writer.writerow({field: snapshot.get(field, "") for field in SNAPSHOT_FIELDS})
    return payload


def format_portfolio_history_markdown(payload: Mapping[str, Any]) -> str:
    validate_portfolio_history_report(payload)
    lines = [
        "# Portfolio History Report",
        "",
        f"- Snapshot Count: {payload['snapshot_count']}",
        f"- Actual Result Count: {payload['actual_result_count']}",
        f"- Forecast Count: {payload['forecast_count']}",
        f"- Retention Window: {payload['history_retention_years']} years",
        "",
        "## Historical Snapshots",
        "",
        "| Date | Period | Type | Portfolio Value | Total Return | Monthly Return | Benchmark Gap |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    if payload["snapshots"]:
        for item in payload["snapshots"]:
            lines.append(
                f"| {item['recorded_at_utc']} | {item['period']} | {item['record_type']} | {item['portfolio_value']} | {item['total_return_pct']} | {item['monthly_return_pct']} | {item['benchmark_gap_pct']} |"
            )
    else:
        lines.append("| None |  |  |  |  |  |  |")
    lines.extend(["", "## Retention Policy"] + [f"- {item}" for item in payload["retention_policy"]])
    lines.extend(["", "## Safety Guarantees"] + [f"- {item}" for item in payload["safety_guarantees"]])
    return "\n".join(lines) + "\n"


def write_portfolio_history_markdown(path: str = "portfolio_history.md", snapshots: Iterable[Mapping[str, Any]] | None = None) -> Dict[str, Any]:
    payload = build_portfolio_history_report(snapshots)
    Path(path).write_text(format_portfolio_history_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_portfolio_history_json()
    write_portfolio_history_csv()
    write_portfolio_history_markdown()
