"""Benchmark-relative discovery leadership evidence for AI CIO.

AI CIO discovers leadership. SWING-001 evaluates the trade.

This module intentionally contains no Swing entry/setup logic. It consumes
already-available daily market history and enriches the existing SWING-001
candidate contract with additive, explainable discovery evidence.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

BENCHMARK_SYMBOL = "SPY"
HORIZON_SESSIONS = {"1m": 21, "3m": 63, "6m": 126}
MIN_BENCHMARK_FOR_MULTIPLE_PCT = 1.0
MIN_OUTPERFORMANCE_FOR_2X_EVIDENCE_PCT = 5.0
MIN_PEER_COUNT = 2

# Centralized/testable relative-outperformance thresholds, in percentage points.
OUTPERFORMANCE_THRESHOLDS = {
    "WEAK_MAX": -5.0,
    "MARKET_PERFORMER_MAX": 5.0,
    "STRONG_MAX": 12.0,
    "LEADER_MAX": 25.0,
}
CLASS_SCORES = {
    "WEAK": 0.0,
    "MARKET_PERFORMER": 35.0,
    "STRONG": 60.0,
    "LEADER": 80.0,
    "EXCEPTIONAL_LEADER": 100.0,
}
COMPOSITE_WEIGHTS = {
    "relative": 0.60,
    "sector": 0.15,
    "industry": 0.15,
    "theme": 0.05,
    "source_confluence": 0.05,
}


def _float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result


def _as_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _history_path(history_dir: str | Path, symbol: str) -> Path:
    return Path(history_dir) / f"{symbol.upper()}.csv"


def load_daily_closes(history_dir: str | Path, symbol: str) -> list[tuple[date, float]]:
    """Load normalized daily closes without performing any network fetch."""
    path = _history_path(history_dir, symbol)
    if not path.is_file():
        return []
    rows: dict[date, float] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            parsed_date = None
            for key in ("date", "Date", "datetime", "Datetime", "timestamp", "Timestamp"):
                parsed_date = _as_date(raw.get(key))
                if parsed_date:
                    break
            close = None
            for key in ("Adj Close", "adj_close", "adjusted_close", "Close", "close"):
                close = _float(raw.get(key))
                if close is not None:
                    break
            if parsed_date and close is not None and close > 0:
                rows[parsed_date] = close
    return sorted(rows.items())


def has_trapper_2x_spy_evidence(
    stock_return_pct: Any,
    benchmark_return_pct: Any,
    relative_outperformance_pct: Any,
    relative_multiple: Any,
) -> bool:
    """Return whether a horizon satisfies the shared Trapper-style 2x-SPY evidence rule."""
    stock_return = _float(stock_return_pct)
    benchmark_return = _float(benchmark_return_pct)
    outperformance = _float(relative_outperformance_pct)
    multiple = _float(relative_multiple)
    return bool(
        stock_return is not None
        and benchmark_return is not None
        and outperformance is not None
        and multiple is not None
        and multiple >= 2.0
        and stock_return > 0
        and benchmark_return >= MIN_BENCHMARK_FOR_MULTIPLE_PCT
        and outperformance >= MIN_OUTPERFORMANCE_FOR_2X_EVIDENCE_PCT
    )


def classify_relative_outperformance(
    stock_return_pct: float,
    benchmark_return_pct: float,
    relative_outperformance_pct: float,
    relative_multiple: float | None,
) -> str:
    """Classify leadership; the Trapper 2x rule is supporting evidence, not a gate."""
    if relative_outperformance_pct < OUTPERFORMANCE_THRESHOLDS["WEAK_MAX"]:
        classification = "WEAK"
    elif relative_outperformance_pct <= OUTPERFORMANCE_THRESHOLDS["MARKET_PERFORMER_MAX"]:
        classification = "MARKET_PERFORMER"
    elif relative_outperformance_pct <= OUTPERFORMANCE_THRESHOLDS["STRONG_MAX"]:
        classification = "STRONG"
    elif relative_outperformance_pct <= OUTPERFORMANCE_THRESHOLDS["LEADER_MAX"]:
        classification = "LEADER"
    else:
        classification = "EXCEPTIONAL_LEADER"

    if has_trapper_2x_spy_evidence(
        stock_return_pct,
        benchmark_return_pct,
        relative_outperformance_pct,
        relative_multiple,
    ) and CLASS_SCORES[classification] < CLASS_SCORES["LEADER"]:
        classification = "LEADER"
    return classification


def _period_result(
    stock_rows: list[tuple[date, float]],
    benchmark_rows: list[tuple[date, float]],
    *,
    horizon: str,
    sessions: int | None,
    observed_on: date | None,
) -> dict[str, Any]:
    stock = dict(stock_rows)
    benchmark = dict(benchmark_rows)
    common_dates = sorted(set(stock).intersection(benchmark))
    if len(common_dates) < 2:
        return {"horizon": horizon, "evidence_status": "MISSING", "warning": "INSUFFICIENT_COMMON_HISTORY"}
    end = common_dates[-1]
    if sessions is None:
        ytd_dates = [day for day in common_dates if day.year == end.year]
        if len(ytd_dates) < 2:
            return {"horizon": horizon, "evidence_status": "MISSING", "warning": "INSUFFICIENT_YTD_HISTORY"}
        start = ytd_dates[0]
    else:
        if len(common_dates) <= sessions:
            return {"horizon": horizon, "evidence_status": "MISSING", "warning": "INSUFFICIENT_HORIZON_HISTORY"}
        start = common_dates[-(sessions + 1)]

    stock_return = ((stock[end] / stock[start]) - 1.0) * 100.0
    benchmark_return = ((benchmark[end] / benchmark[start]) - 1.0) * 100.0
    outperformance = stock_return - benchmark_return
    multiple = None
    multiple_warning = None
    if benchmark_return >= MIN_BENCHMARK_FOR_MULTIPLE_PCT:
        multiple = stock_return / benchmark_return
    else:
        multiple_warning = "BENCHMARK_RETURN_NONPOSITIVE_OR_NEAR_ZERO_MULTIPLE_NOT_MEANINGFUL"
    classification = classify_relative_outperformance(stock_return, benchmark_return, outperformance, multiple)
    result = {
        "horizon": horizon,
        "evidence_status": "AVAILABLE",
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "stock_data_timestamp": end.isoformat(),
        "benchmark_data_timestamp": end.isoformat(),
        "stock_return_pct": round(stock_return, 6),
        "benchmark_return_pct": round(benchmark_return, 6),
        "relative_outperformance_pct": round(outperformance, 6),
        "relative_multiple": round(multiple, 6) if multiple is not None else None,
        "trapper_2x_spy_evidence": has_trapper_2x_spy_evidence(stock_return, benchmark_return, outperformance, multiple),
        "leadership_classification": classification,
    }
    if observed_on is not None:
        result["freshness_days"] = max((observed_on - end).days, 0)
    if multiple_warning:
        result["warning"] = multiple_warning
    return result


def calculate_relative_leadership(
    history_dir: str | Path,
    symbol: str,
    *,
    benchmark_symbol: str = BENCHMARK_SYMBOL,
    observed_on: date | None = None,
) -> dict[str, Any]:
    """Calculate multi-horizon stock leadership against the benchmark."""
    stock_rows = load_daily_closes(history_dir, symbol)
    benchmark_rows = load_daily_closes(history_dir, benchmark_symbol)
    warnings: list[str] = []
    if not stock_rows:
        warnings.append("STOCK_HISTORY_MISSING")
    if not benchmark_rows:
        warnings.append("BENCHMARK_HISTORY_MISSING")
    if warnings:
        return {
            "benchmark_symbol": benchmark_symbol,
            "evidence_status": "MISSING",
            "horizons": {},
            "evaluated_horizons": 0,
            "leader_horizons": 0,
            "leadership_persistence": None,
            "leadership_score": None,
            "leadership_classification": None,
            "warnings": warnings,
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
            "horizons": horizons,
            "evaluated_horizons": 0,
            "leader_horizons": 0,
            "leadership_persistence": None,
            "leadership_score": None,
            "leadership_classification": None,
            "warnings": sorted(set(warnings)),
        }

    scores = [CLASS_SCORES[row["leadership_classification"]] for row in available]
    leader_count = sum(row["leadership_classification"] in {"LEADER", "EXCEPTIONAL_LEADER"} for row in available)
    score = round(sum(scores) / len(scores), 6)
    classification = classify_composite(score)
    return {
        "benchmark_symbol": benchmark_symbol,
        "evidence_status": "AVAILABLE",
        "horizons": horizons,
        "evaluated_horizons": len(available),
        "leader_horizons": leader_count,
        "leadership_persistence": round(leader_count / len(available), 6),
        "leadership_score": score,
        "leadership_classification": classification,
        "warnings": sorted(set(warnings)),
    }


def classify_composite(score: float) -> str:
    if score < 25.0:
        return "WEAK"
    if score < 50.0:
        return "MARKET_PERFORMER"
    if score < 70.0:
        return "STRONG"
    if score < 88.0:
        return "LEADER"
    return "EXCEPTIONAL_LEADER"


def _peer_classification(score: float) -> str:
    if score < 40.0:
        return "WEAK"
    if score < 60.0:
        return "MARKET_PERFORMER"
    if score < 80.0:
        return "STRONG"
    return "LEADING"


def _peer_assessment(
    group_name: str | None,
    groups: Mapping[str, list[float]],
    *,
    dimension: str,
) -> dict[str, Any]:
    if not group_name:
        return {"evidence_status": "MISSING", "classification": None, "warning": f"{dimension.upper()}_MISSING"}
    scores = groups.get(group_name, [])
    if len(scores) < MIN_PEER_COUNT:
        return {
            "evidence_status": "MISSING",
            "name": group_name,
            "classification": None,
            "evaluated_peer_count": len(scores),
            "method": "DISCOVERY_CANDIDATE_PEER_AVERAGE",
            "warning": f"{dimension.upper()}_PEER_EVIDENCE_INSUFFICIENT",
        }
    score = round(sum(scores) / len(scores), 6)
    return {
        "evidence_status": "AVAILABLE",
        "name": group_name,
        "classification": _peer_classification(score),
        "leadership_score": score,
        "evaluated_peer_count": len(scores),
        "method": "DISCOVERY_CANDIDATE_PEER_AVERAGE",
    }


def _theme_assessment(row: Mapping[str, Any], observation: Mapping[str, Any]) -> dict[str, Any]:
    themes = list(row.get("themes") or observation.get("themes") or [])
    explicit = observation.get("theme_momentum") or row.get("theme_momentum")
    if not isinstance(explicit, Mapping):
        return {
            "evidence_status": "MISSING",
            "themes": themes,
            "classification": None,
            "warning": "THEME_MOMENTUM_EVIDENCE_MISSING",
        }
    classification = str(explicit.get("classification") or explicit.get("status") or "").upper() or None
    score_map = {"DECLINING": 20.0, "WEAK": 20.0, "STABLE": 50.0, "NEUTRAL": 50.0, "RISING": 75.0, "STRONG": 80.0, "HOT": 100.0, "LEADING": 100.0}
    score = score_map.get(classification)
    return {
        "evidence_status": "AVAILABLE" if score is not None else "MISSING",
        "themes": themes,
        "classification": classification,
        "leadership_score": score,
        "source": "EXISTING_THEME_MOMENTUM_EVIDENCE",
        **({"warning": "THEME_MOMENTUM_CLASSIFICATION_UNRECOGNIZED"} if score is None else {}),
    }


def _source_confluence_score(row: Mapping[str, Any]) -> float | None:
    confluence = row.get("source_confluence")
    if not isinstance(confluence, Mapping):
        return None
    return {"NONE": 0.0, "SINGLE_SOURCE": 40.0, "CONFIRMED": 75.0, "STRONG": 100.0}.get(str(confluence.get("level") or "").upper())


def _composite(
    relative: Mapping[str, Any],
    sector: Mapping[str, Any],
    industry: Mapping[str, Any],
    theme: Mapping[str, Any],
    source_score: float | None,
) -> tuple[float | None, str | None]:
    relative_score = _float(relative.get("leadership_score"))
    if relative_score is None:
        return None, None
    components: list[tuple[float, float]] = [(relative_score, COMPOSITE_WEIGHTS["relative"])]
    for assessment, weight_name in ((sector, "sector"), (industry, "industry"), (theme, "theme")):
        value = _float(assessment.get("leadership_score"))
        if value is not None:
            components.append((value, COMPOSITE_WEIGHTS[weight_name]))
    if source_score is not None:
        components.append((source_score, COMPOSITE_WEIGHTS["source_confluence"]))
    weight_total = sum(weight for _, weight in components)
    score = round(sum(value * weight for value, weight in components) / weight_total, 6)
    return score, classify_composite(score)


def enrich_swing_discovery_bucket(
    bucket: Mapping[str, Any],
    weekly_report: Mapping[str, Any],
    observations: Iterable[Mapping[str, Any]],
    *,
    history_dir: str | Path,
) -> dict[str, Any]:
    """Add leadership evidence without changing the SWING-001 top-level contract."""
    if str(bucket.get("schema_version")) != "1.0" or str(bucket.get("strategy_id")) != "SWING-001":
        raise ValueError("unexpected SWING-001 discovery contract")
    weekly_by_symbol = {str(row.get("underlying_symbol") or "").upper(): row for row in weekly_report.get("candidates", [])}
    observation_by_symbol = {str(row.get("underlying_symbol") or "").upper(): row for row in observations}
    observed_on = _as_date(weekly_report.get("generated_at"))

    relative_by_symbol: dict[str, dict[str, Any]] = {}
    sectors: dict[str, list[float]] = defaultdict(list)
    industries: dict[str, list[float]] = defaultdict(list)
    metadata: dict[str, tuple[str | None, str | None]] = {}
    for base in bucket.get("candidates", []):
        symbol = str(base.get("underlying_symbol") or "").upper()
        weekly = weekly_by_symbol.get(symbol, {})
        observation = observation_by_symbol.get(symbol, {})
        sector = str(weekly.get("sector") or observation.get("sector") or "").strip() or None
        industry = str(observation.get("industry") or observation.get("sub_industry") or "").strip() or None
        metadata[symbol] = (sector, industry)
        relative = calculate_relative_leadership(history_dir, symbol, observed_on=observed_on)
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
        available_horizons = [value for value in relative.get("horizons", {}).values() if value.get("evidence_status") == "AVAILABLE"]
        if any((_float(item.get("relative_outperformance_pct")) or 0.0) > 0 for item in available_horizons):
            reasons.add("OUTPERFORMING_SPY")
        if any(bool(item.get("trapper_2x_spy_evidence")) for item in available_horizons):
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
        candidate.update({
            "relative_leadership": relative,
            "sector_leadership": sector,
            "industry_leadership": industry,
            "theme_leadership": theme,
            "discovery_leadership_score": score,
            "discovery_leadership_classification": classification,
            "discovery_reasons": sorted(reasons),
            "discovery_warnings": sorted(warnings),
        })
        enriched.append(candidate)

    enriched.sort(key=lambda row: (row.get("discovery_leadership_score") is None, -(row.get("discovery_leadership_score") or 0.0), str(row.get("underlying_symbol") or "")))
    return {"schema_version": "1.0", "strategy_id": "SWING-001", "candidates": enriched}
