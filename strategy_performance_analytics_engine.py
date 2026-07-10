"""
Strategy Performance Analytics Engine for the Dividend Bot.

Evaluates historical paper-only strategy outcomes, compares Strategy A and B,
and summarizes whether scoring signals were predictive. No live trading,
brokerage execution, or order placement is performed.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

MODULE_NAME = "strategy_performance_analytics_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

STRATEGY_A = "STRATEGY_A"
STRATEGY_B = "STRATEGY_B"
UNKNOWN = "UNKNOWN"
SUPPORTED_STRATEGIES = [STRATEGY_A, STRATEGY_B, UNKNOWN]
SUPPORTED_OUTCOMES = ["WIN", "LOSS", "FLAT", "OPEN", UNKNOWN]
SUPPORTED_ANALYTICS_STATUSES = ["STRONG", "ACCEPTABLE", "WEAK", "INSUFFICIENT_DATA", UNKNOWN]

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "reporting_only is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no Robinhood execution is performed",
    "no brokerage execution is performed",
    "no order placement is performed",
    "historical paper-only analytics only",
]

ANALYTICS_RULES = [
    "Closed paper trades are used for realized performance metrics.",
    "Open paper trades are retained for exposure counts but excluded from realized win rate.",
    "Strategy A and Strategy B are compared using return, win rate, and income contribution.",
    "Signal effectiveness is measured by average return across score bands.",
    "Insufficient data produces warnings instead of failures.",
]

TRADE_FIELDS = [
    "trade_id", "symbol", "strategy", "opportunity_type", "entry_date", "exit_date",
    "entry_value", "exit_value", "income_received", "opportunity_score", "conviction_score",
    "momentum_score", "entry_score", "technical_score", "holding_days", "outcome",
    "total_return_pct", "notes",
]

REPORT_REQUIRED_FIELDS = [
    "bot_name", "bot_type", "module_name", "module_version", "schema_version", "generated_by",
    "generated_at_utc", "paper_trade_mode", "live_trading_enabled", "broker_execution_enabled",
    "reporting_only", "supported_strategies", "trade_count", "closed_trade_count", "open_trade_count",
    "overall_metrics", "strategy_metrics", "signal_effectiveness", "opportunity_type_metrics",
    "best_strategy", "analytics_status", "recommendations", "warnings", "errors",
    "analytics_rules", "safety_guarantees",
]


@dataclass(frozen=True)
class StrategyTradeRecord:
    trade_id: str
    symbol: str
    strategy: str = UNKNOWN
    opportunity_type: str = UNKNOWN
    entry_date: str = ""
    exit_date: str = ""
    entry_value: float = 0.0
    exit_value: float = 0.0
    income_received: float = 0.0
    opportunity_score: float = 0.0
    conviction_score: float = 0.0
    momentum_score: float = 0.0
    entry_score: float = 0.0
    technical_score: float = 0.0
    holding_days: int = 0
    outcome: str = UNKNOWN
    total_return_pct: float = 0.0
    notes: str = ""


@dataclass(frozen=True)
class StrategyMetric:
    strategy: str
    trade_count: int
    closed_trade_count: int
    win_count: int
    loss_count: int
    flat_count: int
    win_rate: float
    average_return_pct: float
    cumulative_return_pct: float
    total_income_received: float
    average_holding_days: float


@dataclass(frozen=True)
class StrategyPerformanceAnalyticsReport:
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
    supported_strategies: List[str]
    trade_count: int
    closed_trade_count: int
    open_trade_count: int
    overall_metrics: Dict[str, Any]
    strategy_metrics: List[Dict[str, Any]]
    signal_effectiveness: Dict[str, Any]
    opportunity_type_metrics: List[Dict[str, Any]]
    best_strategy: str
    analytics_status: str
    recommendations: List[str]
    warnings: List[str]
    errors: List[str]
    analytics_rules: List[str]
    safety_guarantees: List[str]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _num(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _score(value: Any) -> float:
    return max(0.0, min(100.0, _num(value, 0.0)))


def _symbol(value: Any) -> str:
    return value.strip().upper() if isinstance(value, str) and value.strip() else "UNKNOWN"


def _strategy(value: Any) -> str:
    return value if value in SUPPORTED_STRATEGIES else UNKNOWN


def _outcome(value: Any) -> str:
    return value if value in SUPPORTED_OUTCOMES else UNKNOWN


def normalize_trade_record(raw: Mapping[str, Any], index: int = 0) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("trade record must be a mapping")
    entry_value = max(0.0, _num(raw.get("entry_value", 0.0)))
    exit_value = max(0.0, _num(raw.get("exit_value", 0.0)))
    income = max(0.0, _num(raw.get("income_received", 0.0)))
    outcome = _outcome(raw.get("outcome", UNKNOWN))
    if outcome == UNKNOWN:
        if not raw.get("exit_date"):
            outcome = "OPEN"
        elif exit_value + income > entry_value:
            outcome = "WIN"
        elif exit_value + income < entry_value:
            outcome = "LOSS"
        else:
            outcome = "FLAT"
    total_return_pct = _num(raw.get("total_return_pct", 0.0))
    if "total_return_pct" not in raw and entry_value > 0 and outcome != "OPEN":
        total_return_pct = ((exit_value + income - entry_value) / entry_value) * 100.0
    return asdict(StrategyTradeRecord(
        trade_id=str(raw.get("trade_id", f"TRADE-{index + 1}")),
        symbol=_symbol(raw.get("symbol", "UNKNOWN")),
        strategy=_strategy(raw.get("strategy", UNKNOWN)),
        opportunity_type=str(raw.get("opportunity_type", UNKNOWN)),
        entry_date=str(raw.get("entry_date", "")),
        exit_date=str(raw.get("exit_date", "")),
        entry_value=round(entry_value, 2),
        exit_value=round(exit_value, 2),
        income_received=round(income, 2),
        opportunity_score=_score(raw.get("opportunity_score", 0.0)),
        conviction_score=_score(raw.get("conviction_score", 0.0)),
        momentum_score=_score(raw.get("momentum_score", 0.0)),
        entry_score=_score(raw.get("entry_score", 0.0)),
        technical_score=_score(raw.get("technical_score", 0.0)),
        holding_days=max(0, int(_num(raw.get("holding_days", 0), 0))),
        outcome=outcome,
        total_return_pct=round(total_return_pct, 4),
        notes=str(raw.get("notes", "")),
    ))


def calculate_strategy_metric(records: Iterable[Mapping[str, Any]], strategy: str) -> Dict[str, Any]:
    rows = [row for row in records if row.get("strategy") == strategy]
    closed = [row for row in rows if row.get("outcome") in ["WIN", "LOSS", "FLAT"]]
    wins = sum(1 for row in closed if row["outcome"] == "WIN")
    losses = sum(1 for row in closed if row["outcome"] == "LOSS")
    flats = sum(1 for row in closed if row["outcome"] == "FLAT")
    win_rate = round((wins / len(closed)) * 100.0, 2) if closed else 0.0
    average_return = round(sum(_num(row.get("total_return_pct")) for row in closed) / len(closed), 4) if closed else 0.0
    cumulative_return = round(sum(_num(row.get("total_return_pct")) for row in closed), 4)
    income = round(sum(_num(row.get("income_received")) for row in rows), 2)
    avg_days = round(sum(_num(row.get("holding_days")) for row in closed) / len(closed), 2) if closed else 0.0
    return asdict(StrategyMetric(strategy, len(rows), len(closed), wins, losses, flats, win_rate, average_return, cumulative_return, income, avg_days))


def _signal_band(score: float) -> str:
    if score >= 90:
        return "90_100"
    if score >= 80:
        return "80_89"
    if score >= 65:
        return "65_79"
    if score >= 50:
        return "50_64"
    return "0_49"


def calculate_signal_effectiveness(records: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    closed = [row for row in records if row.get("outcome") in ["WIN", "LOSS", "FLAT"]]
    result: Dict[str, Any] = {}
    for signal_name in ["opportunity_score", "conviction_score", "momentum_score", "entry_score", "technical_score"]:
        bands: Dict[str, List[float]] = {}
        for row in closed:
            band = _signal_band(_score(row.get(signal_name, 0)))
            bands.setdefault(band, []).append(_num(row.get("total_return_pct")))
        result[signal_name] = {
            band: {
                "trade_count": len(values),
                "average_return_pct": round(sum(values) / len(values), 4) if values else 0.0,
            }
            for band, values in sorted(bands.items())
        }
    return result


def calculate_opportunity_type_metrics(records: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Mapping[str, Any]]] = {}
    for row in records:
        groups.setdefault(str(row.get("opportunity_type", UNKNOWN)), []).append(row)
    metrics = []
    for opportunity_type, rows in groups.items():
        closed = [row for row in rows if row.get("outcome") in ["WIN", "LOSS", "FLAT"]]
        avg_return = round(sum(_num(row.get("total_return_pct")) for row in closed) / len(closed), 4) if closed else 0.0
        income = round(sum(_num(row.get("income_received")) for row in rows), 2)
        metrics.append({"opportunity_type": opportunity_type, "trade_count": len(rows), "closed_trade_count": len(closed), "average_return_pct": avg_return, "total_income_received": income})
    metrics.sort(key=lambda row: (-row["average_return_pct"], row["opportunity_type"]))
    return metrics


def build_strategy_performance_analytics_report(trades: Iterable[Mapping[str, Any]] | None = None) -> Dict[str, Any]:
    records = [normalize_trade_record(raw, index) for index, raw in enumerate(list(trades or []))]
    closed = [row for row in records if row["outcome"] in ["WIN", "LOSS", "FLAT"]]
    strategy_metrics = [calculate_strategy_metric(records, strategy) for strategy in [STRATEGY_A, STRATEGY_B]]
    eligible = [row for row in strategy_metrics if row["closed_trade_count"] > 0]
    best_strategy = max(eligible, key=lambda row: (row["average_return_pct"], row["win_rate"], row["total_income_received"]))["strategy"] if eligible else UNKNOWN
    overall = calculate_strategy_metric([{**row, "strategy": "OVERALL"} for row in records], "OVERALL")
    if len(closed) < 5:
        status = "INSUFFICIENT_DATA"
    elif overall["average_return_pct"] >= 5 and overall["win_rate"] >= 60:
        status = "STRONG"
    elif overall["average_return_pct"] >= 0 and overall["win_rate"] >= 45:
        status = "ACCEPTABLE"
    else:
        status = "WEAK"
    recommendations = []
    if best_strategy != UNKNOWN:
        recommendations.append(f"Continue monitoring {best_strategy} as the current leading paper strategy.")
    if status == "INSUFFICIENT_DATA":
        recommendations.append("Collect additional closed paper trades before changing strategy weights.")
    elif status == "WEAK":
        recommendations.append("Review score thresholds, sell signals, and opportunity selection rules before expansion.")
    warnings = []
    if not records:
        warnings.append("No paper trade records supplied; generated valid empty analytics report.")
    elif len(closed) < 5:
        warnings.append("Closed trade sample is small; analytics should not yet drive permanent architecture changes.")
    payload = asdict(StrategyPerformanceAnalyticsReport(
        BOT_NAME, BOT_TYPE, MODULE_NAME, MODULE_VERSION, SCHEMA_VERSION, GENERATED_BY, _now(),
        True, False, False, True, list(SUPPORTED_STRATEGIES), len(records), len(closed),
        sum(1 for row in records if row["outcome"] == "OPEN"), overall, strategy_metrics,
        calculate_signal_effectiveness(records), calculate_opportunity_type_metrics(records),
        best_strategy, status, recommendations, warnings, [], list(ANALYTICS_RULES), list(SAFETY_GUARANTEES),
    ))
    validate_strategy_performance_analytics_report(payload)
    return payload


def validate_strategy_performance_analytics_report(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    for field_name in REPORT_REQUIRED_FIELDS:
        if field_name not in payload:
            raise ValueError(f"missing required field: {field_name}")
    for field_name, expected in {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
    }.items():
        if payload[field_name] is not expected:
            raise ValueError(f"{field_name} must be {expected}")
    if payload["supported_strategies"] != SUPPORTED_STRATEGIES:
        raise ValueError("supported_strategies must match approved list")
    if payload["best_strategy"] not in SUPPORTED_STRATEGIES:
        raise ValueError("best_strategy must be supported")
    if payload["analytics_status"] not in SUPPORTED_ANALYTICS_STATUSES:
        raise ValueError("analytics_status must be supported")
    for field_name in ["trade_count", "closed_trade_count", "open_trade_count"]:
        if not isinstance(payload[field_name], int) or isinstance(payload[field_name], bool) or payload[field_name] < 0:
            raise ValueError(f"{field_name} must be a non-negative integer")
    if payload["closed_trade_count"] + payload["open_trade_count"] > payload["trade_count"]:
        raise ValueError("closed and open counts cannot exceed trade_count")
    for field_name in ["strategy_metrics", "opportunity_type_metrics", "recommendations", "warnings", "errors", "analytics_rules", "safety_guarantees"]:
        if not isinstance(payload[field_name], list):
            raise ValueError(f"{field_name} must be a list")
    if not isinstance(payload["overall_metrics"], Mapping):
        raise ValueError("overall_metrics must be a mapping")
    if not isinstance(payload["signal_effectiveness"], Mapping):
        raise ValueError("signal_effectiveness must be a mapping")
    return True


def write_strategy_performance_analytics_report_json(path: str = "strategy_performance_analytics.json") -> Dict[str, Any]:
    payload = build_strategy_performance_analytics_report()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_strategy_performance_analytics_report_json(path: str = "strategy_performance_analytics.json") -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_strategy_performance_analytics_report(payload)
    return payload


def write_strategy_performance_analytics_report_csv(path: str = "strategy_performance_analytics.csv") -> Dict[str, Any]:
    payload = build_strategy_performance_analytics_report()
    fieldnames = ["strategy", "trade_count", "closed_trade_count", "win_count", "loss_count", "flat_count", "win_rate", "average_return_pct", "cumulative_return_pct", "total_income_received", "average_holding_days"]
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in payload["strategy_metrics"]:
            writer.writerow({name: row.get(name, "") for name in fieldnames})
    return payload


def format_strategy_performance_analytics_markdown(payload: Mapping[str, Any]) -> str:
    validate_strategy_performance_analytics_report(payload)
    lines = [
        "# Strategy Performance Analytics Report", "",
        f"- Analytics Status: {payload['analytics_status']}",
        f"- Best Strategy: {payload['best_strategy']}",
        f"- Trade Count: {payload['trade_count']}",
        f"- Closed Trades: {payload['closed_trade_count']}",
        "", "## Strategy Metrics", "",
        "| Strategy | Trades | Closed | Win Rate | Avg Return | Income |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["strategy_metrics"]:
        lines.append(f"| {row['strategy']} | {row['trade_count']} | {row['closed_trade_count']} | {row['win_rate']} | {row['average_return_pct']} | {row['total_income_received']} |")
    lines.extend(["", "## Recommendations"] + [f"- {item}" for item in payload["recommendations"]])
    lines.extend(["", "## Analytics Rules"] + [f"- {item}" for item in payload["analytics_rules"]])
    lines.extend(["", "## Safety Guarantees"] + [f"- {item}" for item in payload["safety_guarantees"]])
    return "\n".join(lines) + "\n"


def write_strategy_performance_analytics_report_markdown(path: str = "strategy_performance_analytics.md") -> Dict[str, Any]:
    payload = build_strategy_performance_analytics_report()
    Path(path).write_text(format_strategy_performance_analytics_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_strategy_performance_analytics_report_json()
    write_strategy_performance_analytics_report_csv()
    write_strategy_performance_analytics_report_markdown()
