"""Read-only per-symbol momentum evidence derived from the shared market snapshot.

This module uses already-fetched historical prices and volume. It performs no provider
calls, broker access, portfolio mutation, or order placement. Missing evidence remains
explicit and contributes zero only to the missing signal.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Mapping

MODULE_NAME = "market_momentum_evidence"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

PAPER_TRADE_MODE = True
REPORTING_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
AUTOMATIC_ACTIVATION_ALLOWED = False

DEFAULT_OUTPUT = Path("momentum_score_report.json")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _records(snapshot: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(snapshot, Mapping):
        return []
    rows = snapshot.get("records")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _history_rows(record: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    history = record.get("history") if isinstance(record.get("history"), Mapping) else {}
    rows = history.get("rows") or history.get("history") or history.get("prices") or history.get("records") or []
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _series(rows: list[Mapping[str, Any]], key: str) -> list[float]:
    result: list[float] = []
    for row in rows:
        value = _number(row.get(key))
        if value is not None:
            result.append(value)
    return result


def _return_over(closes: list[float], sessions: int) -> float | None:
    if len(closes) <= sessions or closes[-sessions - 1] == 0:
        return None
    return (closes[-1] / closes[-sessions - 1]) - 1.0


def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return mean(values[-window:])


def _score_return(value: float | None) -> float:
    if value is None:
        return 0.0
    if value >= 0.15:
        return 100.0
    if value >= 0.08:
        return 85.0
    if value >= 0.03:
        return 70.0
    if value >= 0:
        return 55.0
    if value >= -0.05:
        return 35.0
    if value >= -0.12:
        return 15.0
    return 0.0


def _score_ma(price: float | None, sma20: float | None, sma50: float | None, sma200: float | None) -> float:
    if price is None:
        return 0.0
    known = [item for item in (sma20, sma50, sma200) if item is not None]
    if not known:
        return 0.0
    points = 0.0
    maximum = 0.0
    if sma20 is not None:
        maximum += 35.0
        points += 35.0 if price >= sma20 else 0.0
    if sma50 is not None:
        maximum += 35.0
        points += 35.0 if price >= sma50 else 0.0
    if sma200 is not None:
        maximum += 30.0
        points += 30.0 if price >= sma200 else 0.0
    return round((points / maximum) * 100.0, 2) if maximum else 0.0


def _score_volume(volumes: list[float]) -> float:
    if len(volumes) < 20:
        return 0.0
    recent = mean(volumes[-5:])
    baseline = mean(volumes[-20:])
    if baseline <= 0:
        return 0.0
    ratio = recent / baseline
    if ratio >= 1.5:
        return 100.0
    if ratio >= 1.2:
        return 85.0
    if ratio >= 1.0:
        return 70.0
    if ratio >= 0.8:
        return 50.0
    return 30.0


def _score_volatility_adjusted(closes: list[float], return_63: float | None) -> tuple[float, float | None]:
    if len(closes) < 22 or return_63 is None:
        return 0.0, None
    daily: list[float] = []
    for prior, current in zip(closes[-64:-1], closes[-63:]):
        if prior > 0:
            daily.append((current / prior) - 1.0)
    if len(daily) < 20:
        return 0.0, None
    annualized_volatility = pstdev(daily) * math.sqrt(252.0)
    if annualized_volatility <= 0:
        return 100.0 if return_63 > 0 else 0.0, annualized_volatility
    ratio = return_63 / annualized_volatility
    if ratio >= 0.75:
        score = 100.0
    elif ratio >= 0.40:
        score = 85.0
    elif ratio >= 0.15:
        score = 70.0
    elif ratio >= 0:
        score = 55.0
    elif ratio >= -0.20:
        score = 30.0
    else:
        score = 0.0
    return score, round(annualized_volatility, 6)


def _status(score: float) -> str:
    if score >= 80:
        return "STRONG"
    if score >= 55:
        return "MODERATE"
    if score >= 30:
        return "WEAK"
    return "NEGATIVE"


def _trend(price: float | None, sma20: float | None, sma50: float | None) -> str:
    if price is None or sma20 is None:
        return "UNKNOWN"
    if price > sma20 and (sma50 is None or sma20 >= sma50):
        return "UP"
    if price < sma20 and (sma50 is None or sma20 <= sma50):
        return "DOWN"
    return "SIDEWAYS"


def build_market_momentum_report(
    market_data_snapshot: Mapping[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []

    for record in _records(market_data_snapshot):
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        rows = _history_rows(record)
        closes = _series(rows, "close")
        volumes = _series(rows, "volume")
        price = closes[-1] if closes else _number(record.get("price"))
        r20 = _return_over(closes, 20)
        r63 = _return_over(closes, 63)
        r126 = _return_over(closes, 126)
        sma20 = _sma(closes, 20)
        sma50 = _sma(closes, 50)
        sma200 = _sma(closes, 200)
        volatility_score, annualized_volatility = _score_volatility_adjusted(closes, r63)

        metric_values = {
            "return_20d": r20,
            "return_63d": r63,
            "return_126d": r126,
            "sma_20": sma20,
            "sma_50": sma50,
            "sma_200": sma200,
            "annualized_volatility": annualized_volatility,
        }
        signal_scores = {
            "price_trend": _score_return(r20),
            "relative_strength": _score_return(r63),
            "medium_term_momentum": _score_return(r126),
            "moving_average_alignment": _score_ma(price, sma20, sma50, sma200),
            "volume_confirmation": _score_volume(volumes),
            "volatility_adjusted_momentum": volatility_score,
        }
        missing = [name for name, value in metric_values.items() if value is None]
        score = round(sum(signal_scores.values()) / len(signal_scores), 2)
        available_signals = sum(1 for value in metric_values.values() if value is not None)
        confidence = round(available_signals / len(metric_values), 4)
        confidence_level = "HIGH" if confidence >= 0.70 else ("MEDIUM" if confidence >= 0.40 else "LOW")
        trend_direction = _trend(price, sma20, sma50)
        if missing:
            warnings.append(f"{symbol}: partial momentum evidence: {', '.join(missing)}")

        entries.append({
            "symbol": symbol,
            "momentum_score": score,
            "score": score,
            "momentum_status": _status(score),
            "confidence": confidence,
            "confidence_level": confidence_level,
            "trend_direction": trend_direction,
            "metric_values": metric_values,
            "signal_scores": signal_scores,
            "history_row_count": len(rows),
            "missing_metrics": missing,
            "evidence_status": "AVAILABLE" if not missing else ("PARTIAL" if available_signals else "NOT_REPORTED"),
            "source": "SHARED_MARKET_DATA_SNAPSHOT",
        })

    aggregate = round(mean([row["momentum_score"] for row in entries]), 2) if entries else 0.0
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
        "momentum_score": aggregate,
        "entries": entries,
        "entry_count": len(entries),
        "missing_evidence_policy": "MISSING_SIGNAL_EVIDENCE_EQUALS_ZERO",
        "warnings": warnings,
        "errors": [],
    }


def write_market_momentum_report(
    market_data_snapshot: Mapping[str, Any] | None = None,
    *,
    root_dir: str | Path = ".",
    output_path: str | Path = DEFAULT_OUTPUT,
) -> Path:
    root = Path(root_dir)
    path = Path(output_path)
    if not path.is_absolute():
        path = root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    report = build_market_momentum_report(market_data_snapshot)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
