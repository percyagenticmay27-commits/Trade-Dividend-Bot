"""Read-only market refresh for Dividend suitability evidence."""
from __future__ import annotations

from datetime import date, datetime, timezone
from math import isfinite
from statistics import mean
from typing import Any, Mapping


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _history(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for raw in payload.get("rows", []) if isinstance(payload.get("rows"), list) else []:
        if not isinstance(raw, Mapping):
            continue
        try:
            observed = date.fromisoformat(str(raw.get("date") or "")[:10])
        except ValueError:
            continue
        close = _number(raw.get("adj_close")) or _number(raw.get("close"))
        volume = _number(raw.get("volume"))
        if close and close > 0:
            rows.append({"date": observed, "close": close, "volume": volume})
    return sorted(rows, key=lambda row: row["date"])


def build_vehicle_evidence(symbol: str, mapping_type: str, profile: Mapping[str, Any],
                           history: Mapping[str, Any], quote: Mapping[str, Any]) -> dict[str, Any]:
    rows = _history(history)
    first, latest = (rows[0], rows[-1]) if rows else (None, None)
    total_return = (
        round(((latest["close"] / first["close"]) - 1) * 100, 6)
        if first and latest and len(rows) >= 20 and (latest["date"] - first["date"]).days >= 300 else None
    )
    recent = [row["close"] * row["volume"] for row in rows[-20:]
              if row.get("volume") is not None and row["volume"] > 0]
    dollar_volume = round(mean(recent), 2) if len(recent) >= 5 else None
    output = {
        "income_symbol": symbol,
        "reviewed": True,
        "evidence_as_of": latest["date"].isoformat() if latest else profile.get("reviewed_at"),
        "latest_dollar_volume": dollar_volume,
        "total_return_1y_percent": total_return,
        "market_history_source": history.get("data_source") or history.get("provider"),
        "is_stale": bool(history.get("is_stale") or quote.get("is_stale")),
        "sources": list(profile.get("sources") or []),
    }
    if mapping_type == "INCOME_ETF":
        inception = date.fromisoformat(str(profile["fund_inception_date"]))
        as_of = latest["date"] if latest else date.fromisoformat(str(profile["reviewed_at"]))
        output.update({
            "expense_ratio_percent": profile.get("expense_ratio_percent"),
            "latest_distribution_roc_percent": profile.get("latest_distribution_roc_percent"),
            "fund_age_days": max(0, (as_of - inception).days),
        })
    else:
        dividend_rate = _number(quote.get("dividend_rate"))
        price = _number(quote.get("price"))
        raw_yield = _number(quote.get("trailing_annual_dividend_yield"))
        if raw_yield is None:
            raw_yield = _number(quote.get("dividend_yield"))
        if dividend_rate is not None and price is not None and dividend_rate >= 0 and price > 0:
            yield_percent = dividend_rate / price * 100
        elif raw_yield is not None:
            # Yahoo has returned this field as both a decimal ratio and a
            # percentage across provider versions. Values above 0.20 are
            # already percentage points; smaller values are decimal ratios.
            yield_percent = raw_yield if raw_yield > 0.20 else raw_yield * 100
        else:
            yield_percent = None
        if yield_percent is not None and not 0 <= yield_percent <= 25:
            yield_percent = None
        output.update({
            "forward_dividend_yield_percent": (
                round(yield_percent, 6) if yield_percent is not None else None
            ),
            "dividend_cut_last_12m": profile.get("dividend_cut_last_12m"),
        })
    return output


def collect_suitability_evidence(mapping_report: Mapping[str, Any], profiles: Mapping[str, Any],
                                 service: Any) -> dict[str, Any]:
    profile_rows = profiles.get("profiles")
    if not isinstance(profile_rows, list):
        raise ValueError("suitability profiles must be a list")
    indexed = {str(row.get("income_symbol") or "").upper(): row for row in profile_rows
               if isinstance(row, Mapping)}
    vehicles, warnings = [], []
    for mapping in mapping_report.get("candidates", []):
        symbol = str(mapping.get("income_symbol") or "").upper()
        if not symbol:
            # RESEARCH_REQUIRED mappings intentionally have no approved vehicle.
            continue
        profile = indexed.get(symbol)
        if not profile or profile.get("reviewed") is not True:
            warnings.append(f"Reviewed suitability profile unavailable for {symbol}")
            continue
        try:
            history = service.get_history(symbol, period="1y", interval="1d")
            quote = service.get_quote(symbol)
            vehicles.append(build_vehicle_evidence(
                symbol, str(mapping.get("mapping_type") or ""), profile, history, quote,
            ))
        except Exception as exc:
            warnings.append(f"Suitability market evidence unavailable for {symbol}: {exc}")
    return {
        "schema_version": "1.0",
        "strategy_id": "DIVIDEND-001",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "vehicles": vehicles,
        "warnings": warnings,
        "read_only_market_data": True,
        "inference_allowed": False,
    }
