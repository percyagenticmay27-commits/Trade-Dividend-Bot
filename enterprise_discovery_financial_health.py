"""Authoritative shared Financial Health evidence for Enterprise discovery candidates.

This module produces the seven normalized 0-100 component scores required by the
Swing Bot Financial Health adapter. It is fail closed: a complete block is emitted
only when every required component is supported by fresh provider evidence.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Mapping

REQUIRED_COMPONENTS = (
    "revenue_growth",
    "eps_growth",
    "operating_cash_flow",
    "gross_margin_trend",
    "debt_health",
    "analyst_revisions",
    "sector_strength",
)

SECTOR_BENCHMARKS = {
    "BASIC MATERIALS": "XLB",
    "COMMUNICATION SERVICES": "XLC",
    "CONSUMER CYCLICAL": "XLY",
    "CONSUMER DEFENSIVE": "XLP",
    "ENERGY": "XLE",
    "FINANCIAL SERVICES": "XLF",
    "HEALTHCARE": "XLV",
    "INDUSTRIALS": "XLI",
    "REAL ESTATE": "XLRE",
    "TECHNOLOGY": "XLK",
    "UTILITIES": "XLU",
}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def _linear(value: float, low: float, high: float) -> float:
    if high == low:
        raise ValueError("high and low must differ")
    return _clamp((value - low) * 100.0 / (high - low))


def _history_return_percent(payload: Mapping[str, Any], sessions: int = 21) -> float | None:
    rows = payload.get("rows") or []
    closes: list[float] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        close = _number(row.get("close"))
        if close is not None and close > 0:
            closes.append(close)
    if len(closes) <= sessions:
        return None
    start = closes[-(sessions + 1)]
    end = closes[-1]
    return ((end / start) - 1.0) * 100.0 if start > 0 else None


def _build_components(
    fundamentals: Mapping[str, Any],
    sector_history: Mapping[str, Any],
    benchmark_history: Mapping[str, Any],
) -> tuple[dict[str, float] | None, dict[str, Any]]:
    revenue_growth = _number(fundamentals.get("revenue_growth"))
    eps_growth = _number(fundamentals.get("eps_growth"))
    operating_cash_flow = _number(fundamentals.get("operating_cash_flow"))
    total_revenue = _number(fundamentals.get("total_revenue"))
    gross_margin_current = _number(fundamentals.get("gross_margin_current"))
    gross_margin_prior = _number(fundamentals.get("gross_margin_prior"))
    debt_to_equity = _number(fundamentals.get("debt_to_equity"))
    analyst_upgrades = _number(fundamentals.get("analyst_upgrades_90d"))
    analyst_downgrades = _number(fundamentals.get("analyst_downgrades_90d"))
    analyst_evidence_available = fundamentals.get("analyst_revisions_available") is True
    sector_return = _history_return_percent(sector_history)
    benchmark_return = _history_return_percent(benchmark_history)

    raw = {
        "revenue_growth": revenue_growth,
        "eps_growth": eps_growth,
        "operating_cash_flow": operating_cash_flow,
        "total_revenue": total_revenue,
        "gross_margin_current": gross_margin_current,
        "gross_margin_prior": gross_margin_prior,
        "debt_to_equity": debt_to_equity,
        "analyst_upgrades_90d": analyst_upgrades,
        "analyst_downgrades_90d": analyst_downgrades,
        "sector_return_21d_percent": sector_return,
        "benchmark_return_21d_percent": benchmark_return,
    }

    required_raw = (
        revenue_growth,
        eps_growth,
        operating_cash_flow,
        total_revenue,
        gross_margin_current,
        gross_margin_prior,
        debt_to_equity,
        sector_return,
        benchmark_return,
    )
    if any(value is None for value in required_raw) or not analyst_evidence_available:
        return None, raw
    if total_revenue == 0:
        return None, raw

    revenue_score = _linear(revenue_growth, -0.20, 0.30)
    eps_score = _linear(eps_growth, -0.20, 0.30)
    ocf_margin = operating_cash_flow / total_revenue
    ocf_score = _linear(ocf_margin, 0.0, 0.30)
    gross_margin_change = gross_margin_current - gross_margin_prior
    gross_margin_score = _linear(gross_margin_change, -0.05, 0.05)
    debt_score = _linear(debt_to_equity, 300.0, 0.0)

    upgrades = max(0.0, analyst_upgrades or 0.0)
    downgrades = max(0.0, analyst_downgrades or 0.0)
    revision_count = upgrades + downgrades
    analyst_score = 50.0 if revision_count == 0 else _clamp(50.0 + 50.0 * ((upgrades - downgrades) / revision_count))

    sector_relative = sector_return - benchmark_return
    sector_score = _linear(sector_relative, -10.0, 10.0)

    raw["operating_cash_flow_margin"] = round(ocf_margin, 6)
    raw["gross_margin_change"] = round(gross_margin_change, 6)
    raw["sector_relative_strength_21d_percent"] = round(sector_relative, 6)
    return {
        "revenue_growth": revenue_score,
        "eps_growth": eps_score,
        "operating_cash_flow": ocf_score,
        "gross_margin_trend": gross_margin_score,
        "debt_health": debt_score,
        "analyst_revisions": analyst_score,
        "sector_strength": sector_score,
    }, raw


def build_financial_health_block(
    symbol: str,
    fundamentals: Mapping[str, Any],
    sector_history: Mapping[str, Any],
    benchmark_history: Mapping[str, Any],
    *,
    sector_benchmark: str,
) -> dict[str, Any] | None:
    """Return a complete fresh block, otherwise None without placeholder values."""
    if fundamentals.get("is_stale") or sector_history.get("is_stale") or benchmark_history.get("is_stale"):
        return None
    components, raw = _build_components(fundamentals, sector_history, benchmark_history)
    if components is None or set(components) != set(REQUIRED_COMPONENTS):
        return None
    timestamp = str(fundamentals.get("retrieved_at_utc") or "").strip()
    provider = str(fundamentals.get("provider") or "").strip()
    if not timestamp or not provider:
        return None
    return {
        "components": components,
        "evidence_timestamp": timestamp,
        "provenance": (
            f"{provider}: company fundamentals, quarterly financial statements, "
            f"analyst upgrades/downgrades; sector benchmark {sector_benchmark} vs SPY"
        ),
        "evidence": {
            "underlying_symbol": str(symbol).upper(),
            "sector": fundamentals.get("sector"),
            "sector_benchmark": sector_benchmark,
            "benchmark_symbol": "SPY",
            **raw,
        },
    }


def attach_candidate_financial_health(
    report: dict[str, Any],
    service: Any,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Refresh Financial Health evidence for every Enterprise candidate not explicitly rejected."""
    eligible = [
        row
        for row in report.get("observations", [])
        if row.get("nomination_eligible", True) is not False
    ]
    if not eligible:
        return report
    try:
        benchmark = service.get_history("SPY", period="3mo", interval="1d", force_refresh=force_refresh)
    except Exception as exc:
        benchmark = {}
        report.setdefault("warnings", []).append(f"Financial Health benchmark SPY unavailable: {exc}")

    sector_cache: dict[str, Mapping[str, Any]] = {}
    for row in eligible:
        symbol = str(row.get("underlying_symbol") or "").strip().upper()
        row.pop("financial_health", None)
        try:
            fundamentals = service.get_financial_health_inputs(symbol, force_refresh=force_refresh)
            sector_name = str(fundamentals.get("sector") or "").strip().upper()
            sector_benchmark = SECTOR_BENCHMARKS.get(sector_name)
            if not sector_benchmark:
                raise ValueError(f"no authoritative sector benchmark mapping for sector {sector_name or 'UNKNOWN'}")
            if sector_benchmark not in sector_cache:
                sector_cache[sector_benchmark] = service.get_history(
                    sector_benchmark,
                    period="3mo",
                    interval="1d",
                    force_refresh=force_refresh,
                )
            block = build_financial_health_block(
                symbol,
                fundamentals,
                sector_cache[sector_benchmark],
                benchmark,
                sector_benchmark=sector_benchmark,
            )
            if block is not None:
                row["financial_health"] = block
            else:
                row.setdefault("evidence_warnings", []).append(
                    f"Financial Health evidence incomplete or stale for {symbol}; block omitted."
                )
        except Exception as exc:
            row.setdefault("evidence_warnings", []).append(
                f"Financial Health evidence unavailable for {symbol}: {exc}"
            )
    report["financial_health_policy"] = "ALL_SEVEN_COMPONENTS_REQUIRED_FAIL_CLOSED"
    return report
