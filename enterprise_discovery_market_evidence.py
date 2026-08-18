"""Read-only market evidence for confirmed Enterprise discovery nominees."""
from __future__ import annotations

from datetime import date, datetime, timezone
from statistics import mean
from typing import Any, Mapping


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _history_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("rows") or payload.get("history") or payload.get("records") or []
    rows = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, Mapping):
            continue
        text = str(item.get("date") or item.get("timestamp") or "")[:10]
        try:
            observed = date.fromisoformat(text)
        except ValueError:
            continue
        close = _number(item.get("close", item.get("Close")))
        volume = _number(item.get("volume", item.get("Volume")))
        if close is None or close <= 0:
            continue
        rows.append({"date": observed, "close": close, "volume": volume})
    return sorted(rows, key=lambda row: row["date"])


def _return_percent(rows: list[dict[str, Any]], sessions: int = 5) -> float | None:
    if len(rows) <= sessions:
        return None
    start = rows[-(sessions + 1)]["close"]
    end = rows[-1]["close"]
    return round(((end / start) - 1.0) * 100.0, 6) if start > 0 else None


def build_candidate_market_evidence(
    symbol: str,
    history: Mapping[str, Any],
    benchmark_history: Mapping[str, Any] | None,
    *,
    quote: Mapping[str, Any] | None = None,
    benchmark_symbol: str = "SPY",
) -> dict[str, Any]:
    rows = _history_rows(history)
    benchmark_rows = _history_rows(benchmark_history or {})
    weekly_return = _return_percent(rows)
    benchmark_return = _return_percent(benchmark_rows)
    latest = rows[-1] if rows else None
    prior_volumes = [row["volume"] for row in rows[-21:-1] if row.get("volume") is not None and row["volume"] > 0]
    latest_volume = latest.get("volume") if latest else None
    average_volume = mean(prior_volumes) if len(prior_volumes) >= 5 else None
    volume_ratio = (
        round(latest_volume / average_volume, 6)
        if latest_volume is not None and average_volume and average_volume > 0 else None
    )
    relative_strength = (
        round(weekly_return - benchmark_return, 6)
        if weekly_return is not None and benchmark_return is not None else None
    )
    dollar_volume = (
        round(latest["close"] * latest_volume, 2)
        if latest and latest_volume is not None else None
    )
    available = latest is not None
    complete = available and weekly_return is not None and relative_strength is not None and volume_ratio is not None
    return {
        "status": "AVAILABLE" if complete else ("PARTIAL" if available else "UNAVAILABLE"),
        "symbol": str(symbol).upper(),
        "benchmark_symbol": benchmark_symbol,
        "latest_session": latest["date"].isoformat() if latest else None,
        "latest_close": round(latest["close"], 6) if latest else None,
        "latest_volume": round(latest_volume, 6) if latest_volume is not None else None,
        "weekly_return_percent": weekly_return,
        "benchmark_weekly_return_percent": benchmark_return,
        "relative_strength_vs_benchmark_percent": relative_strength,
        "prior_average_volume": round(average_volume, 6) if average_volume is not None else None,
        "volume_expansion_ratio": volume_ratio,
        "latest_dollar_volume": dollar_volume,
        "sector": (quote or {}).get("sector"),
        "industry": (quote or {}).get("industry"),
        "quote_type": (quote or {}).get("quote_type"),
        "history_source": history.get("data_source") or history.get("provider") or "NOT_REPORTED",
        "quote_source": (quote or {}).get("data_source") or (quote or {}).get("provider") or "NOT_REPORTED",
        "is_stale": bool(history.get("is_stale") or (quote or {}).get("is_stale")),
        "inference_allowed": False,
    }


def attach_candidate_market_evidence(
    report: dict[str, Any],
    service: Any,
    *,
    benchmark_symbol: str = "SPY",
) -> dict[str, Any]:
    eligible = [row for row in report.get("observations", []) if row.get("nomination_eligible") is True]
    if not eligible:
        return report
    try:
        benchmark = service.get_history(benchmark_symbol, period="3mo", interval="1d")
    except Exception as exc:  # provider/cache boundary; fail closed with disclosure
        benchmark = {}
        report.setdefault("warnings", []).append(f"Market benchmark {benchmark_symbol} unavailable: {exc}")
    for row in eligible:
        symbol = str(row.get("underlying_symbol") or "").upper()
        try:
            history = service.get_history(symbol, period="3mo", interval="1d")
            quote = service.get_quote(symbol)
            row["market_evidence"] = build_candidate_market_evidence(
                symbol, history, benchmark, quote=quote, benchmark_symbol=benchmark_symbol,
            )
            warnings = row.setdefault("evidence_warnings", [])
            warnings[:] = [warning for warning in warnings if not warning.startswith("Market evidence is unavailable")]
            if row["market_evidence"]["status"] != "AVAILABLE":
                warnings.append("Market evidence is partial; unavailable metrics were not inferred.")
        except Exception as exc:  # provider/cache boundary; candidate evidence remains unchanged
            row["market_evidence"] = {
                "status": "UNAVAILABLE",
                "symbol": symbol,
                "benchmark_symbol": benchmark_symbol,
                "inference_allowed": False,
            }
            row.setdefault("evidence_warnings", []).append(f"Market evidence unavailable for {symbol}: {exc}")
    report["market_evidence_policy"] = "AUTHORITATIVE_HISTORY_ONLY"
    report["market_evidence_benchmark"] = benchmark_symbol
    return report
