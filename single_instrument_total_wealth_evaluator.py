"""Single-Instrument Total Wealth Evaluator for Trade-Dividend-Bot Version 2.

Transforms the shared read-only market-data snapshot into normalized Capital
Efficiency Score candidates. All recommendations remain paper-only.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Iterable, Mapping, Optional

from capital_efficiency_score_engine import build_capital_efficiency_score_report

MODULE_NAME = "single_instrument_total_wealth_evaluator"
MODULE_VERSION = "2.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_SNAPSHOT_FILE = "market_data_snapshot.json"
DEFAULT_OUTPUT_FILES = {
    "json": "single_instrument_total_wealth.json",
    "markdown": "single_instrument_total_wealth.md",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _clamp(value: Any) -> float:
    return round(max(0.0, min(100.0, _number(value))), 4)


def _records(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("records", "market_records", "symbols", "data", "results"):
        value = snapshot.get(key)
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, Mapping)]
    if isinstance(snapshot.get("symbol"), str):
        return [dict(snapshot)]
    return []


def _history_closes(record: Mapping[str, Any]) -> list[float]:
    raw = record.get("history") or record.get("historical_prices") or record.get("prices") or []
    if isinstance(raw, Mapping):
        raw = raw.get("records") or raw.get("prices") or raw.get("history") or []
    closes: list[float] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, Mapping):
                value = item.get("close", item.get("adj_close", item.get("price")))
            else:
                value = item
            number = _number(value, float("nan"))
            if math.isfinite(number) and number > 0:
                closes.append(number)
    return closes


def _returns(closes: list[float]) -> list[float]:
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes)) if closes[i - 1] > 0]


def _max_drawdown_pct(closes: list[float]) -> float:
    peak = 0.0
    worst = 0.0
    for value in closes:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1.0)
    return abs(worst) * 100.0


def _annualized_volatility_pct(closes: list[float]) -> float:
    returns = _returns(closes)
    return pstdev(returns) * math.sqrt(252.0) * 100.0 if len(returns) >= 2 else 0.0


def _growth_pct(record: Mapping[str, Any], closes: list[float]) -> float:
    if len(closes) >= 2 and closes[0] > 0:
        return (closes[-1] / closes[0] - 1.0) * 100.0
    price = _number(record.get("price"))
    previous = _number(record.get("previous_close"))
    return ((price / previous) - 1.0) * 100.0 if price > 0 and previous > 0 else 0.0


def _score_growth(growth_pct: float) -> float:
    return _clamp(50.0 + growth_pct * 1.5)


def _score_income(record: Mapping[str, Any]) -> float:
    yield_value = _number(record.get("dividend_yield", record.get("distribution_yield", 0.0)))
    if 0.0 < yield_value <= 1.0:
        yield_value *= 100.0
    return _clamp(yield_value * 7.0)


def _score_momentum(record: Mapping[str, Any], closes: list[float]) -> float:
    if len(closes) >= 21:
        short = mean(closes[-20:])
        long = mean(closes[-min(100, len(closes)):])
        latest = closes[-1]
        score = 50.0
        score += 20.0 if latest > short else -20.0
        score += 20.0 if short > long else -20.0
        return _clamp(score)
    price = _number(record.get("price"))
    previous = _number(record.get("previous_close"))
    return _clamp(50.0 + ((price / previous) - 1.0) * 500.0) if price > 0 and previous > 0 else 0.0


def _score_quality(record: Mapping[str, Any]) -> float:
    score = 45.0
    if _number(record.get("market_cap")) >= 10_000_000_000:
        score += 20.0
    if _number(record.get("volume")) >= 500_000:
        score += 15.0
    if record.get("sector"):
        score += 10.0
    if record.get("industry"):
        score += 10.0
    return _clamp(score)


def _score_sector(record: Mapping[str, Any]) -> float:
    explicit = record.get("sector_strength_score", record.get("sector_leadership"))
    if explicit is not None:
        return _clamp(explicit)
    return 55.0 if record.get("sector") else 0.0


def _score_regime(record: Mapping[str, Any], market_regime: str) -> float:
    regime = str(market_regime or "UNKNOWN").upper()
    beta = _number(record.get("beta"), 1.0)
    if regime in {"BULL", "RISK_ON", "TRENDING_UP"}:
        return _clamp(70.0 + min(20.0, max(0.0, beta - 1.0) * 20.0))
    if regime in {"BEAR", "RISK_OFF", "TRENDING_DOWN"}:
        return _clamp(65.0 if beta <= 0.8 else 30.0)
    return 55.0


def _score_distribution_sustainability(record: Mapping[str, Any]) -> float:
    count = int(_number(record.get("dividend_record_count")))
    total = _number(record.get("dividend_total"))
    yield_value = _number(record.get("dividend_yield"))
    if 0.0 < yield_value <= 1.0:
        yield_value *= 100.0
    score = 35.0 + min(35.0, count * 2.0) + (15.0 if total > 0 else 0.0)
    if yield_value > 20.0:
        score -= 20.0
    return _clamp(score)


def _confidence(record: Mapping[str, Any], closes: list[float]) -> tuple[float, list[str]]:
    missing: list[str] = []
    checks = {
        "price": _number(record.get("price")) > 0,
        "history": len(closes) >= 20,
        "dividend_yield": record.get("dividend_yield") is not None,
        "market_cap": _number(record.get("market_cap")) > 0,
        "sector": bool(record.get("sector")),
    }
    for name, present in checks.items():
        if not present:
            missing.append(name)
    score = 100.0 - len(missing) * 15.0
    if bool(record.get("is_stale")):
        score -= 20.0
        missing.append("fresh_market_data")
    return _clamp(score), missing


def evaluate_single_instrument(
    record: Mapping[str, Any],
    market_regime: str = "UNKNOWN",
) -> dict[str, Any]:
    symbol = str(record.get("symbol", "")).strip().upper()
    if not symbol:
        raise ValueError("record must include symbol")
    closes = _history_closes(record)
    growth_pct = _growth_pct(record, closes)
    volatility_pct = _annualized_volatility_pct(closes)
    drawdown_pct = _max_drawdown_pct(closes)
    confidence, missing = _confidence(record, closes)
    income_score = _score_income(record)
    candidate = {
        "candidate_id": symbol,
        "candidate_type": "SINGLE_INSTRUMENT",
        "symbols": [symbol],
        "expected_capital_appreciation": _score_growth(growth_pct),
        "expected_income": income_score,
        "reinvestment_potential": _clamp((income_score + _score_growth(growth_pct)) / 2.0),
        "momentum_trend_quality": _score_momentum(record, closes),
        "fundamental_or_fund_quality": _score_quality(record),
        "sector_leadership": _score_sector(record),
        "market_regime_support": _score_regime(record, market_regime),
        "distribution_sustainability": _score_distribution_sustainability(record),
        "evidence_confidence": confidence,
        "volatility_risk": _clamp(volatility_pct * 2.0),
        "drawdown_risk": _clamp(drawdown_pct * 2.5),
        "downside_risk": _clamp(max(0.0, -growth_pct) * 2.0 + drawdown_pct),
        "concentration_risk": 75.0,
        "correlation_risk": 0.0,
        "turnover_tax_friction": 0.0,
        "missing_evidence": missing,
        "source_metrics": {
            "growth_pct": round(growth_pct, 4),
            "annualized_volatility_pct": round(volatility_pct, 4),
            "maximum_drawdown_pct": round(drawdown_pct, 4),
            "dividend_yield": _number(record.get("dividend_yield")),
            "price": _number(record.get("price")),
            "is_stale": bool(record.get("is_stale")),
        },
        "eligible": _number(record.get("price")) > 0,
    }
    return candidate


def build_single_instrument_total_wealth_report(
    snapshot: Mapping[str, Any],
    market_regime: str = "UNKNOWN",
) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise ValueError("snapshot must be a mapping")
    records = _records(snapshot)
    candidates: list[dict[str, Any]] = []
    warnings: list[str] = []
    for record in records:
        try:
            candidates.append(evaluate_single_instrument(record, market_regime=market_regime))
        except ValueError as exc:
            warnings.append(str(exc))
    score_report = build_capital_efficiency_score_report(candidates)
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
        "market_regime": str(market_regime or "UNKNOWN").upper(),
        "instrument_count": len(candidates),
        "top_candidate_id": score_report.get("top_candidate_id"),
        "candidates": candidates,
        "capital_efficiency_report": score_report,
        "warnings": warnings,
        "errors": [],
    }


def format_single_instrument_total_wealth_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Single-Instrument Total Wealth Evaluation",
        "",
        f"- Market Regime: {payload.get('market_regime', 'UNKNOWN')}",
        f"- Instruments Evaluated: {payload.get('instrument_count', 0)}",
        f"- Top Candidate: {payload.get('top_candidate_id') or 'None'}",
        "",
        "## Rankings",
    ]
    results = payload.get("capital_efficiency_report", {}).get("results", [])
    if not results:
        lines.append("- None")
    for result in results:
        lines.append(
            f"- #{result.get('rank', 0)} {result.get('candidate_id')}: "
            f"CES {result.get('capital_efficiency_score', 0):.2f} — {result.get('recommendation', 'WATCHLIST')}"
        )
    if payload.get("warnings"):
        lines.extend(["", "## Warnings", *(f"- {item}" for item in payload["warnings"])])
    return "\n".join(lines) + "\n"


def write_single_instrument_total_wealth(
    root_path: str = ".",
    snapshot_file: str = DEFAULT_SNAPSHOT_FILE,
    market_regime: str = "UNKNOWN",
    output_files: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    root = Path(root_path)
    snapshot_path = root / snapshot_file
    if not snapshot_path.exists():
        raise FileNotFoundError(snapshot_path)
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    report = build_single_instrument_total_wealth_report(snapshot, market_regime=market_regime)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    (root / files["json"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_single_instrument_total_wealth_markdown(report), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = write_single_instrument_total_wealth()
    print(f"Single-Instrument Total Wealth Evaluation: {result['instrument_count']} instruments")
