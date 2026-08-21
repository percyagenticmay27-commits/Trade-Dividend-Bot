"""AI CIO market-snapshot adapter for Discovery Leadership.

Production Discovery Leadership consumes the existing read-only
``market_data_snapshot.json`` contract. The legacy CSV loader remains available
in ``discovery_leadership.py`` for deterministic unit tests and compatibility,
but the weekly producer does not depend on Swing-owned data or a second market
data store.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from src.dividend_bot.discovery_leadership import (
    BENCHMARK_SYMBOL,
    CLASS_SCORES,
    HORIZON_SESSIONS,
    MIN_OUTPERFORMANCE_FOR_2X_EVIDENCE_PCT,
    _as_date,
    _composite,
    _float,
    _peer_assessment,
    _period_result,
    _source_confluence_score,
    _theme_assessment,
    classify_composite,
)


def _history_rows(history: Mapping[str, Any] | None) -> list[tuple[Any, float]]:
    """Normalize closes from the existing MarketDataService history payload."""
    if not isinstance(history, Mapping):
        return []
    raw_rows = (
        history.get("rows")
        or history.get("history")
        or history.get("prices")
        or history.get("records")
        or []
    )
    if not isinstance(raw_rows, list):
        return []
    rows: dict[Any, float] = {}
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            continue
        observed = _as_date(raw.get("date") or raw.get("timestamp") or raw.get("datetime"))
        close = _float(
            raw.get("adj_close", raw.get("adjusted_close", raw.get("close", raw.get("Close"))))
        )
        if observed is not None and close is not None and close > 0:
            rows[observed] = close
    return sorted(rows.items())


def _snapshot_records(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    records = snapshot.get("records") or []
    if not isinstance(records, list):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for row in records:
        if not isinstance(row, Mapping):
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        if symbol:
            result[symbol] = row
    return result


def calculate_relative_leadership_from_snapshot(
    snapshot: Mapping[str, Any],
    symbol: str,
    *,
    benchmark_symbol: str = BENCHMARK_SYMBOL,
    observed_on=None,
) -> dict[str, Any]:
    """Calculate 1M/3M/6M/YTD leadership from the AI CIO snapshot only."""
    records = _snapshot_records(snapshot)
    ticker = str(symbol or "").strip().upper()
    stock_record = records.get(ticker)
    benchmark_record = records.get(str(benchmark_symbol).strip().upper())
    stock_rows = _history_rows(stock_record.get("history")) if stock_record else []
    benchmark_rows = _history_rows(benchmark_record.get("history")) if benchmark_record else []

    warnings: list[str] = []
    if stock_record is None:
        warnings.append("STOCK_SNAPSHOT_RECORD_MISSING")
    elif not stock_rows:
        warnings.append("STOCK_HISTORY_MISSING")
    if benchmark_record is None:
        warnings.append("BENCHMARK_SNAPSHOT_RECORD_MISSING")
    elif not benchmark_rows:
        warnings.append("BENCHMARK_HISTORY_MISSING")
    if stock_record and bool(stock_record.get("is_stale")):
        warnings.append("STOCK_MARKET_DATA_STALE")
    if benchmark_record and bool(benchmark_record.get("is_stale")):
        warnings.append("BENCHMARK_MARKET_DATA_STALE")

    if not stock_rows or not benchmark_rows:
        return {
            "benchmark_symbol": benchmark_symbol,
            "evidence_status": "MISSING",
            "evidence_source": "AI_CIO_MARKET_DATA_SNAPSHOT",
            "horizons": {},
            "evaluated_horizons": 0,
            "leader_horizons": 0,
            "leadership_persistence": None,
            "leadership_score": None,
            "leadership_classification": None,
            "stock_history_source": stock_record.get("history_source") if stock_record else None,
            "benchmark_history_source": benchmark_record.get("history_source") if benchmark_record else None,
            "warnings": sorted(set(warnings)),
        }

    horizons: dict[str, dict[str, Any]] = {}
    for name, sessions in HORIZON_SESSIONS.items():
        horizons[name] = _period_result(
            stock_rows,
            benchmark_rows,
            horizon=name,
            sessions=sessions,
            observed_on=observed_on,
        )
    horizons["ytd"] = _period_result(
        stock_rows,
        benchmark_rows,
        horizon="ytd",
        sessions=None,
        observed_on=observed_on,
    )
    available = [row for row in horizons.values() if row.get("evidence_status") == "AVAILABLE"]
    for row in horizons.values():
        warning = row.get("warning")
        if row.get("evidence_status") != "AVAILABLE" and warning:
            warnings.append(f"{row['horizon'].upper()}_{warning}")

    if not available:
        return {
            "benchmark_symbol": benchmark_symbol,
            "evidence_status": "MISSING",
            "evidence_source": "AI_CIO_MARKET_DATA_SNAPSHOT",
            "horizons": horizons,
            "evaluated_horizons": 0,
            "leader_horizons": 0,
            "leadership_persistence": None,
            "leadership_score": None,
            "leadership_classification": None,
            "stock_history_source": stock_record.get("history_source"),
            "benchmark_history_source": benchmark_record.get("history_source"),
            "warnings": sorted(set(warnings)),
        }

    scores = [CLASS_SCORES[row["leadership_classification"]] for row in available]
    leader_count = sum(
        row["leadership_classification"] in {"LEADER", "EXCEPTIONAL_LEADER"}
        for row in available
    )
    score = round(sum(scores) / len(scores), 6)
    return {
        "benchmark_symbol": benchmark_symbol,
        "evidence_status": "AVAILABLE",
        "evidence_source": "AI_CIO_MARKET_DATA_SNAPSHOT",
        "horizons": horizons,
        "evaluated_horizons": len(available),
        "leader_horizons": leader_count,
        "leadership_persistence": round(leader_count / len(available), 6),
        "leadership_score": score,
        "leadership_classification": classify_composite(score),
        "stock_history_source": stock_record.get("history_source") or stock_record.get("history", {}).get("data_source"),
        "benchmark_history_source": benchmark_record.get("history_source") or benchmark_record.get("history", {}).get("data_source"),
        "warnings": sorted(set(warnings)),
    }


def enrich_swing_discovery_bucket_from_snapshot(
    bucket: Mapping[str, Any],
    weekly_report: Mapping[str, Any],
    observations: Iterable[Mapping[str, Any]],
    market_data_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    """Enrich SWING-001 using only the AI CIO-owned market snapshot."""
    if str(bucket.get("schema_version")) != "1.0" or str(bucket.get("strategy_id")) != "SWING-001":
        raise ValueError("unexpected SWING-001 discovery contract")
    if not isinstance(market_data_snapshot, Mapping):
        raise ValueError("market_data_snapshot must be a mapping")

    records = _snapshot_records(market_data_snapshot)
    weekly_by_symbol = {
        str(row.get("underlying_symbol") or "").upper(): row
        for row in weekly_report.get("candidates", [])
        if isinstance(row, Mapping)
    }
    observation_by_symbol = {
        str(row.get("underlying_symbol") or "").upper(): row
        for row in observations
        if isinstance(row, Mapping)
    }
    observed_on = _as_date(weekly_report.get("generated_at"))

    relative_by_symbol: dict[str, dict[str, Any]] = {}
    sectors: dict[str, list[float]] = defaultdict(list)
    industries: dict[str, list[float]] = defaultdict(list)
    metadata: dict[str, tuple[str | None, str | None]] = {}

    for base in bucket.get("candidates", []):
        symbol = str(base.get("underlying_symbol") or "").upper()
        weekly = weekly_by_symbol.get(symbol, {})
        observation = observation_by_symbol.get(symbol, {})
        market_record = records.get(symbol, {})
        sector = str(
            market_record.get("sector")
            or weekly.get("sector")
            or observation.get("sector")
            or ""
        ).strip() or None
        industry = str(
            market_record.get("industry")
            or observation.get("industry")
            or observation.get("sub_industry")
            or ""
        ).strip() or None
        if sector == "UNKNOWN":
            sector = None
        if industry == "UNKNOWN":
            industry = None
        metadata[symbol] = (sector, industry)
        relative = calculate_relative_leadership_from_snapshot(
            market_data_snapshot,
            symbol,
            observed_on=observed_on,
        )
        relative_by_symbol[symbol] = relative
        relative_score = _float(relative.get("leadership_score"))
        if relative_score is not None:
            if sector:
                sectors[sector].append(relative_score)
            if industry:
                industries[industry].append(relative_score)

    enriched: list[dict[str, Any]] = []
    for base in bucket.get("candidates", []):
        symbol = str(base.get("underlying_symbol") or "").upper()
        weekly = weekly_by_symbol.get(symbol, {})
        observation = observation_by_symbol.get(symbol, {})
        sector_name, industry_name = metadata.get(symbol, (None, None))
        relative = relative_by_symbol[symbol]
        sector = _peer_assessment(sector_name, sectors, dimension="sector")
        industry = _peer_assessment(industry_name, industries, dimension="industry")
        theme = _theme_assessment(weekly, observation)
        source_score = _source_confluence_score(weekly)
        score, classification = _composite(relative, sector, industry, theme, source_score)

        reasons: set[str] = set()
        warnings: set[str] = set(relative.get("warnings") or [])
        available_horizons = [
            value
            for value in relative.get("horizons", {}).values()
            if value.get("evidence_status") == "AVAILABLE"
        ]
        if any((_float(item.get("relative_outperformance_pct")) or 0.0) > 0 for item in available_horizons):
            reasons.add("OUTPERFORMING_SPY")
        if any(
            (_float(item.get("relative_multiple")) or 0.0) >= 2.0
            and (_float(item.get("relative_outperformance_pct")) or 0.0)
            >= MIN_OUTPERFORMANCE_FOR_2X_EVIDENCE_PCT
            for item in available_horizons
        ):
            reasons.add("TRAPPER_2X_SPY_EVIDENCE")
        if (_float(relative.get("leadership_persistence")) or 0.0) >= 0.5:
            reasons.add("MULTI_HORIZON_LEADER")
        if relative.get("leadership_classification") in {"LEADER", "EXCEPTIONAL_LEADER"}:
            reasons.add("MARKET_LEADER")
        if sector.get("classification") == "LEADING":
            reasons.add("LEADING_SECTOR")
        if industry.get("classification") == "LEADING":
            reasons.add("LEADING_INDUSTRY")
        if theme.get("classification") in {"RISING", "STRONG", "HOT", "LEADING"}:
            reasons.add("RISING_THEME")
        if source_score is not None and source_score >= 75.0:
            reasons.add("STRONG_SOURCE_CONFLUENCE")
        for assessment in (sector, industry, theme):
            warning = assessment.get("warning")
            if warning:
                warnings.add(str(warning))

        candidate = dict(base)
        candidate.update(
            {
                "relative_leadership": relative,
                "sector_leadership": sector,
                "industry_leadership": industry,
                "theme_leadership": theme,
                "discovery_leadership_score": score,
                "discovery_leadership_classification": classification,
                "discovery_reasons": sorted(reasons),
                "discovery_warnings": sorted(warnings),
            }
        )
        enriched.append(candidate)

    enriched.sort(
        key=lambda row: (
            row.get("discovery_leadership_score") is None,
            -(row.get("discovery_leadership_score") or 0.0),
            str(row.get("underlying_symbol") or ""),
        )
    )
    return {"schema_version": "1.0", "strategy_id": "SWING-001", "candidates": enriched}
