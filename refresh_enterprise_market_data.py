#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
from functools import partial
from pathlib import Path
from typing import Any, Iterable

from src.dividend_bot.codex_robinhood_market_data_bridge import read_codex_market_data_handoff
from src.dividend_bot.enterprise_market_data_provider import (
    BROKER_EXECUTION_ENABLED,
    CAPITAL_MOVEMENT_ENABLED,
    LIVE_TRADING_ENABLED,
    MODULE_NAME,
    MODULE_VERSION,
    ORDER_PLACEMENT_ENABLED,
    PAPER_TRADE_MODE,
    SCHEMA_VERSION,
    CodexRobinhoodSource,
    EnterpriseMarketDataProvider,
    LocalCacheSource,
    MarketDataUnavailable,
    StooqSource,
    YFinanceSource,
    atomic_write_text,
    utc_now,
)

DEFAULT_CACHE_DIR = "/var/lib/enterprise-market-data-cache"
DEFAULT_HISTORY_PERIOD = "1mo"
DEFAULT_HISTORY_INTERVAL = "1d"
HISTORY_EXPORT_DIRECTORY = "enterprise_market_data_history"
HISTORY_CSV_FIELDS = (
    "date",
    "open",
    "high",
    "low",
    "close",
    "adjusted_close",
    "volume",
)
MARKET_DATA_PROVIDER_ORDER = ("YFINANCE", "STOOQ", "LOCAL_CACHE", "ROBINHOOD_MCP")
HISTORICAL_CLOSE_SOURCE_TYPE = "HISTORICAL_CLOSE_FALLBACK"
HISTORICAL_CLOSE_CONFIDENCE = 0.75


def build_cost_aware_provider(
    results_dir: Path,
    cache_dir: Path,
    handoff_reader: Any | None,
) -> EnterpriseMarketDataProvider:
    """Use public sources and fresh cache before quota-controlled Robinhood MCP."""
    sources: list[Any] = [YFinanceSource(), StooqSource(), LocalCacheSource(cache_dir)]
    if handoff_reader is not None:
        sources.append(CodexRobinhoodSource(handoff_reader))
    return EnterpriseMarketDataProvider(sources=sources, results_dir=results_dir, cache_dir=cache_dir)


def _attempts(provider: Any) -> list[dict[str, Any]]:
    return [attempt.to_dict() for attempt in provider.attempts]


def _write_history_exports(
    results_dir: Path,
    strategy_id: str,
    symbol: str,
    history: dict[str, Any],
) -> tuple[Path, Path]:
    """Atomically publish full normalized bars as provider-neutral JSON and CSV."""
    export_dir = results_dir / HISTORY_EXPORT_DIRECTORY
    json_path = export_dir / f"{symbol}.history.json"
    csv_path = export_dir / f"{symbol}.csv"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "strategy_id": strategy_id,
        "symbol": symbol,
        "period": history["period"],
        "interval": history["interval"],
        "provider": history["provider"],
        "generated_at": history["generated_at"],
        "latest_bar_date": history["latest_bar_date"],
        "stale": history["stale"],
        "corporate_action_adjusted": history["corporate_action_adjusted"],
        "split_history": list(history.get("split_history", [])),
        "dividend_history": list(history.get("dividend_history", [])),
        "cache_used": history.get("cache_used", False),
        "warnings": list(history.get("warnings", [])),
        "bars": list(history["bars"]),
    }
    atomic_write_text(json_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=HISTORY_CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for bar in history["bars"]:
        writer.writerow({field: bar.get(field, "") for field in HISTORY_CSV_FIELDS})
    atomic_write_text(csv_path, buffer.getvalue())
    return json_path, csv_path


def _historical_close_quote(
    symbol: str,
    history: dict[str, Any],
    quote_error: str,
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build an explicit valuation fallback from the latest validated history bar."""
    bars = list(history.get("bars", []))
    if not bars:
        raise MarketDataUnavailable("fresh history contained no bars for valuation fallback")
    latest_bar = bars[-1]
    price = latest_bar.get("adjusted_close")
    if price is None:
        price = latest_bar.get("close")
    if price is None:
        raise MarketDataUnavailable("latest fresh history bar contained no close value")
    warning = (
        "live quote unavailable; using latest validated historical close for valuation: "
        f"{quote_error}"
    )
    return {
        "price": float(price),
        "quote_timestamp": history["generated_at"],
        "trading_date": history["latest_bar_date"],
        "provider": history["provider"],
        "source_type": HISTORICAL_CLOSE_SOURCE_TYPE,
        "stale": False,
        "confidence": HISTORICAL_CLOSE_CONFIDENCE,
        "cache_used": history.get("cache_used", False),
        "valuation_fallback": True,
        "warnings": [warning],
        "attempts": attempts,
    }


def refresh_strategy_market_data(
    provider: Any,
    strategy_id: str,
    required_symbols: Iterable[str],
    optional_symbols: Iterable[str],
    *,
    period: str = DEFAULT_HISTORY_PERIOD,
    interval: str = DEFAULT_HISTORY_INTERVAL,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []

    for required, symbols in ((True, required_symbols), (False, optional_symbols)):
        for raw_symbol in symbols:
            symbol = raw_symbol.strip().upper()
            record: dict[str, Any] = {
                "strategy_id": strategy_id,
                "symbol": symbol,
                "required": required,
                "status": "FRESH",
                "quote": None,
                "history": None,
                "warnings": [],
                "errors": [],
            }
            quote_error: str | None = None
            quote_attempts: list[dict[str, Any]] = []
            history_payload: dict[str, Any] | None = None

            try:
                quote = provider.get_quote(symbol)
                quote_attempts = _attempts(provider)
                record["quote"] = {
                    "price": quote["price"],
                    "quote_timestamp": quote["quote_timestamp"],
                    "trading_date": quote["trading_date"],
                    "provider": quote["provider"],
                    "source_type": quote["source_type"],
                    "stale": quote["stale"],
                    "confidence": quote["confidence"],
                    "cache_used": quote.get("cache_used", False),
                    "valuation_fallback": False,
                    "warnings": list(quote.get("warnings", [])),
                    "attempts": quote_attempts,
                }
            except MarketDataUnavailable as exc:
                quote_error = str(exc)
                quote_attempts = _attempts(provider)

            try:
                history_payload = provider.get_history(symbol, period=period, interval=interval)
                history_attempts = _attempts(provider)
                json_path, csv_path = _write_history_exports(
                    provider.results_dir, strategy_id, symbol, history_payload
                )
                record["history"] = {
                    "period": history_payload["period"],
                    "interval": history_payload["interval"],
                    "provider": history_payload["provider"],
                    "generated_at": history_payload["generated_at"],
                    "latest_bar_date": history_payload["latest_bar_date"],
                    "stale": history_payload["stale"],
                    "corporate_action_adjusted": history_payload["corporate_action_adjusted"],
                    "bar_count": len(history_payload["bars"]),
                    "bars_json_path": str(json_path),
                    "bars_csv_path": str(csv_path),
                    "cache_used": history_payload.get("cache_used", False),
                    "warnings": list(history_payload.get("warnings", [])),
                    "attempts": history_attempts,
                }
            except MarketDataUnavailable as exc:
                record["errors"].append(f"history: {exc}")

            if record["quote"] is None and history_payload is not None and quote_error is not None:
                try:
                    record["quote"] = _historical_close_quote(
                        symbol, history_payload, quote_error, quote_attempts
                    )
                    fallback_warning = record["quote"]["warnings"][0]
                    record["warnings"].append(fallback_warning)
                    record["status"] = "WARNING"
                    warnings.append(f"{symbol}: {fallback_warning}")
                except MarketDataUnavailable as exc:
                    record["errors"].append(f"quote: {quote_error}; fallback: {exc}")
            elif record["quote"] is None and quote_error is not None:
                record["errors"].append(f"quote: {quote_error}")

            if record["errors"]:
                record["status"] = "BLOCKED" if required else "WARNING"
                message = f"{symbol}: " + " | ".join(record["errors"])
                (errors if required else warnings).append(message)

            records.append(record)

    overall_status = "BLOCKED" if errors else ("WARNING" if warnings else "READY")
    generated_at = utc_now().isoformat()
    result = {
        "module": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "strategy_id": strategy_id,
        "status": overall_status,
        "provider_attempt_order": list(MARKET_DATA_PROVIDER_ORDER),
        "history_export_directory": str(provider.results_dir / HISTORY_EXPORT_DIRECTORY),
        "records": records,
        "warnings": warnings,
        "errors": errors,
        "paper_trade_mode": PAPER_TRADE_MODE,
        "live_trading_enabled": LIVE_TRADING_ENABLED,
        "broker_execution_enabled": BROKER_EXECUTION_ENABLED,
        "order_placement_enabled": ORDER_PLACEMENT_ENABLED,
        "capital_movement_enabled": CAPITAL_MOVEMENT_ENABLED,
    }

    provider_health = {
        "generated_at": generated_at,
        "strategy_id": strategy_id,
        "healthy": overall_status != "BLOCKED",
        "status": overall_status,
        "provider_attempt_order": list(MARKET_DATA_PROVIDER_ORDER),
        "symbols": [
            {
                "symbol": record["symbol"],
                "required": record["required"],
                "status": record["status"],
                "quote_provider": (record["quote"] or {}).get("provider"),
                "quote_source_type": (record["quote"] or {}).get("source_type"),
                "valuation_fallback": (record["quote"] or {}).get("valuation_fallback", False),
                "history_provider": (record["history"] or {}).get("provider"),
                "quote_timestamp": (record["quote"] or {}).get("quote_timestamp"),
                "latest_bar_date": (record["history"] or {}).get("latest_bar_date"),
                "bars_json_path": (record["history"] or {}).get("bars_json_path"),
                "bars_csv_path": (record["history"] or {}).get("bars_csv_path"),
                "quote_cache_used": (record["quote"] or {}).get("cache_used", False),
                "history_cache_used": (record["history"] or {}).get("cache_used", False),
                "quote_attempts": (record["quote"] or {}).get("attempts", []),
                "history_attempts": (record["history"] or {}).get("attempts", []),
                "warnings": record["warnings"],
                "errors": record["errors"],
            }
            for record in records
        ],
        "secrets_written": False,
        "safety": {
            "paper_only": True,
            "read_only": True,
            "broker_execution_enabled": False,
            "order_placement_enabled": False,
            "capital_movement_enabled": False,
        },
    }
    contract = {
        "schema_version": SCHEMA_VERSION,
        "provider_precedence": list(MARKET_DATA_PROVIDER_ORDER),
        "policy": "PUBLIC_FIRST_COST_AWARE_ROBINHOOD_FALLBACK",
        "quote_fields": [
            "symbol", "price", "quote_timestamp", "trading_date", "provider",
            "source_type", "stale", "confidence", "warnings", "valuation_fallback",
        ],
        "valuation_fallback": {
            "enabled": True,
            "source_type": HISTORICAL_CLOSE_SOURCE_TYPE,
            "rule": "When live quote is unavailable and normalized history is fresh, use the latest adjusted_close or close as the valuation price and publish WARNING instead of BLOCKED.",
            "confidence": HISTORICAL_CLOSE_CONFIDENCE,
            "blocks_when_history_missing": True,
        },
        "history_fields": [
            "symbol", "interval", "period", "provider", "generated_at",
            "latest_bar_date", "stale", "corporate_action_adjusted", "bars",
        ],
        "history_exports": {
            "directory": HISTORY_EXPORT_DIRECTORY,
            "json_pattern": "{symbol}.history.json",
            "csv_pattern": "{symbol}.csv",
            "csv_fields": list(HISTORY_CSV_FIELDS),
            "atomic_writes": True,
        },
        "operations": [
            "get_quote", "get_history", "get_latest_close", "get_previous_close",
            "get_volume", "get_split_history", "get_dividend_history",
        ],
    }

    atomic_write_text(
        provider.results_dir / "enterprise_market_data_status.json",
        json.dumps(result, indent=2, sort_keys=True) + "\n",
    )
    atomic_write_text(
        provider.results_dir / "enterprise_market_data_provider_health.json",
        json.dumps(provider_health, indent=2, sort_keys=True) + "\n",
    )
    atomic_write_text(
        provider.results_dir / "enterprise_market_data_contract.json",
        json.dumps(contract, indent=2, sort_keys=True) + "\n",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy-id", required=True)
    parser.add_argument("--required-symbol", action="append", default=[])
    parser.add_argument("--optional-symbol", action="append", default=[])
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--handoff-dir", default="/run/enterprise-market-data-handoff")
    parser.add_argument("--history-period", default=DEFAULT_HISTORY_PERIOD)
    parser.add_argument("--history-interval", default=DEFAULT_HISTORY_INTERVAL)
    parser.add_argument("--disable-robinhood", action="store_true")
    parser.add_argument("--always-zero", action="store_true")
    args = parser.parse_args()

    handoff_reader = None
    if not args.disable_robinhood:
        handoff_reader = partial(read_codex_market_data_handoff, handoff_dir=args.handoff_dir)
    provider = build_cost_aware_provider(Path(args.results_dir), Path(args.cache_dir), handoff_reader)
    result = refresh_strategy_market_data(
        provider,
        args.strategy_id,
        args.required_symbol,
        args.optional_symbol,
        period=args.history_period,
        interval=args.history_interval,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.always_zero:
        return 0
    return 2 if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
