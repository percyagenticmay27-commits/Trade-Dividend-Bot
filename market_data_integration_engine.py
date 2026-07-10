"""Shared read-only market-data refresh engine for the Dividend Bot.

The engine discovers symbols from portfolio and watchlist artifacts, refreshes each
symbol once through the central MarketDataService, and writes one normalized JSON
and CSV snapshot for all downstream analysis stages.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from market_data_provider import MarketDataService
from yahoo_finance_provider import MarketDataProviderError

MODULE_NAME = "market_data_integration_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
READ_ONLY_MARKET_DATA = True

DEFAULT_OUTPUT_FILES = {
    "json": "market_data_snapshot.json",
    "csv": "market_data_snapshot.csv",
}

DEFAULT_SYMBOL_FILES = [
    "portfolio_lifecycle_report.json",
    "portfolio_construction_report.json",
    "capital_allocation_report.json",
    "portfolio_decision_report.json",
    "opportunity_pairing_report.json",
    "dividend_rankings.json",
    "watchlist.json",
    "portfolio.json",
]

SYMBOL_KEYS = {
    "symbol", "ticker", "income_symbol", "growth_symbol", "primary_symbol",
    "secondary_symbol", "asset", "security",
}


@dataclass(frozen=True)
class MarketDataIntegrationReport:
    module_name: str
    module_version: str
    schema_version: str
    generated_at_utc: str
    paper_trade_mode: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    read_only_market_data: bool
    status: str
    symbol_count: int
    successful_symbol_count: int
    failed_symbol_count: int
    symbols: list[str]
    records: list[dict[str, Any]]
    warnings: list[str]
    errors: list[str]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_symbol(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    symbol = value.strip().upper()
    if not symbol or len(symbol) > 20:
        return None
    return symbol


def _collect_symbols(value: Any, result: set[str]) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in SYMBOL_KEYS:
                symbol = _normalize_symbol(item)
                if symbol:
                    result.add(symbol)
            _collect_symbols(item, result)
    elif isinstance(value, list):
        for item in value:
            _collect_symbols(item, result)


def discover_market_symbols(
    root_path: str = ".",
    explicit_symbols: Optional[Iterable[str]] = None,
    symbol_files: Optional[Iterable[str]] = None,
) -> list[str]:
    symbols: set[str] = set()
    for value in explicit_symbols or []:
        symbol = _normalize_symbol(value)
        if symbol:
            symbols.add(symbol)

    root = Path(root_path)
    for filename in symbol_files or DEFAULT_SYMBOL_FILES:
        path = root / filename
        if not path.exists() or path.suffix.lower() != ".json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        _collect_symbols(payload, symbols)
    return sorted(symbols)


def _safe_number(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return 0.0


def _latest_history_close(history: Mapping[str, Any]) -> float:
    rows = history.get("history") or history.get("prices") or history.get("records") or []
    if not isinstance(rows, list) or not rows:
        return 0.0
    last = rows[-1]
    if not isinstance(last, Mapping):
        return 0.0
    return _safe_number(last.get("close", last.get("Close", 0.0)))


def _dividend_summary(dividends: Mapping[str, Any]) -> tuple[int, float]:
    rows = dividends.get("dividends") or dividends.get("history") or dividends.get("records") or []
    if not isinstance(rows, list):
        return 0, 0.0
    total = 0.0
    count = 0
    for row in rows:
        if isinstance(row, Mapping):
            value = row.get("dividend", row.get("amount", row.get("value", 0.0)))
        else:
            value = row
        amount = _safe_number(value)
        if amount:
            total += amount
        count += 1
    return count, round(total, 6)


def refresh_market_data_snapshot(
    symbols: Iterable[str],
    service: MarketDataService,
    force_refresh: bool = False,
    history_period: str = "1y",
    history_interval: str = "1d",
    dividend_period: str = "5y",
) -> dict[str, Any]:
    normalized = sorted({symbol for raw in symbols if (symbol := _normalize_symbol(raw))})
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []

    for symbol in normalized:
        try:
            quote = service.get_quote(symbol, force_refresh=force_refresh)
            history = service.get_history(
                symbol,
                period=history_period,
                interval=history_interval,
                force_refresh=force_refresh,
            )
            dividends = service.get_dividends(
                symbol,
                period=dividend_period,
                force_refresh=force_refresh,
            )
            dividend_count, dividend_total = _dividend_summary(dividends)
            price = _safe_number(
                quote.get("price", quote.get("regular_market_price", quote.get("current_price", 0.0)))
            )
            if price == 0.0:
                price = _latest_history_close(history)
            records.append({
                "symbol": symbol,
                "price": price,
                "previous_close": _safe_number(quote.get("previous_close", 0.0)),
                "market_cap": _safe_number(quote.get("market_cap", 0.0)),
                "dividend_yield": _safe_number(quote.get("dividend_yield", 0.0)),
                "beta": _safe_number(quote.get("beta", 0.0)),
                "volume": _safe_number(quote.get("volume", 0.0)),
                "fifty_two_week_high": _safe_number(quote.get("fifty_two_week_high", 0.0)),
                "fifty_two_week_low": _safe_number(quote.get("fifty_two_week_low", 0.0)),
                "sector": str(quote.get("sector", "UNKNOWN")),
                "industry": str(quote.get("industry", "UNKNOWN")),
                "dividend_record_count": dividend_count,
                "dividend_total": dividend_total,
                "quote_source": str(quote.get("data_source", "UNKNOWN")),
                "history_source": str(history.get("data_source", "UNKNOWN")),
                "dividend_source": str(dividends.get("data_source", "UNKNOWN")),
                "is_stale": bool(
                    quote.get("is_stale") or history.get("is_stale") or dividends.get("is_stale")
                ),
                "quote": dict(quote),
                "history": dict(history),
                "dividends": dict(dividends),
            })
        except (MarketDataProviderError, OSError, RuntimeError, TypeError, ValueError) as exc:
            errors.append(f"{symbol}: {exc}")

    if not normalized:
        warnings.append("No portfolio or watchlist symbols were discovered; provider access was skipped.")
    stale_count = sum(1 for row in records if row["is_stale"])
    if stale_count:
        warnings.append(f"{stale_count} symbol records used stale cached data.")

    status = "ERROR" if normalized and not records else (
        "PARTIAL" if errors or not normalized else "COMPLETE"
    )
    payload = asdict(MarketDataIntegrationReport(
        MODULE_NAME,
        MODULE_VERSION,
        SCHEMA_VERSION,
        _now(),
        True,
        False,
        False,
        True,
        status,
        len(normalized),
        len(records),
        len(errors),
        normalized,
        records,
        warnings,
        errors,
    ))
    validate_market_data_snapshot(payload)
    return payload


def validate_market_data_snapshot(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    required = set(MarketDataIntegrationReport.__dataclass_fields__)
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    for field, expected in {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "read_only_market_data": True,
    }.items():
        if payload[field] is not expected:
            raise ValueError(f"{field} must be {expected}")
    if payload["status"] not in {"COMPLETE", "PARTIAL", "ERROR"}:
        raise ValueError("unsupported status")
    for field in ["symbol_count", "successful_symbol_count", "failed_symbol_count"]:
        if not isinstance(payload[field], int) or isinstance(payload[field], bool) or payload[field] < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    if payload["successful_symbol_count"] + payload["failed_symbol_count"] != payload["symbol_count"]:
        raise ValueError("successful and failed counts must total symbol_count")
    for field in ["symbols", "records", "warnings", "errors"]:
        if not isinstance(payload[field], list):
            raise ValueError(f"{field} must be a list")
    return True


def write_market_data_snapshot(
    root_path: str = ".",
    symbols: Optional[Iterable[str]] = None,
    service: Optional[MarketDataService] = None,
    force_refresh: bool = False,
    output_files: Optional[Mapping[str, str]] = None,
    symbol_files: Optional[Iterable[str]] = None,
) -> dict[str, Any]:
    root = Path(root_path)
    root.mkdir(parents=True, exist_ok=True)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    discovered = discover_market_symbols(root_path, symbols, symbol_files)
    active_service = service or MarketDataService(root_path=root_path)
    payload = refresh_market_data_snapshot(discovered, active_service, force_refresh=force_refresh)

    (root / files["json"]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fieldnames = [
        "symbol", "price", "previous_close", "market_cap", "dividend_yield",
        "beta", "volume", "fifty_two_week_high", "fifty_two_week_low", "sector",
        "industry", "dividend_record_count", "dividend_total", "quote_source",
        "history_source", "dividend_source", "is_stale",
    ]
    with (root / files["csv"]).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in payload["records"]:
            writer.writerow({name: row.get(name, "") for name in fieldnames})
    return payload


if __name__ == "__main__":
    report = write_market_data_snapshot()
    print(f"Market Data Integration: {report['status']} ({report['successful_symbol_count']}/{report['symbol_count']})")
