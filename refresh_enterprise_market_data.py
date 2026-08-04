#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
    PROVIDER_ORDER,
    SCHEMA_VERSION,
    MarketDataUnavailable,
    atomic_write_text,
    build_default_provider,
    utc_now,
)

DEFAULT_CACHE_DIR = "/var/lib/enterprise-market-data-cache"
DEFAULT_HISTORY_PERIOD = "1mo"
DEFAULT_HISTORY_INTERVAL = "1d"


def _attempts(provider: Any) -> list[dict[str, Any]]:
    return [attempt.to_dict() for attempt in provider.attempts]


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

            try:
                quote = provider.get_quote(symbol)
                record["quote"] = {
                    "price": quote["price"],
                    "quote_timestamp": quote["quote_timestamp"],
                    "trading_date": quote["trading_date"],
                    "provider": quote["provider"],
                    "source_type": quote["source_type"],
                    "stale": quote["stale"],
                    "confidence": quote["confidence"],
                    "cache_used": quote.get("cache_used", False),
                    "warnings": list(quote.get("warnings", [])),
                    "attempts": _attempts(provider),
                }
            except MarketDataUnavailable as exc:
                record["errors"].append(f"quote: {exc}")

            try:
                history = provider.get_history(symbol, period=period, interval=interval)
                record["history"] = {
                    "period": history["period"],
                    "interval": history["interval"],
                    "provider": history["provider"],
                    "generated_at": history["generated_at"],
                    "latest_bar_date": history["latest_bar_date"],
                    "stale": history["stale"],
                    "corporate_action_adjusted": history["corporate_action_adjusted"],
                    "bar_count": len(history["bars"]),
                    "cache_used": history.get("cache_used", False),
                    "warnings": list(history.get("warnings", [])),
                    "attempts": _attempts(provider),
                }
            except MarketDataUnavailable as exc:
                record["errors"].append(f"history: {exc}")

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
        "provider_attempt_order": list(PROVIDER_ORDER),
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
        "provider_attempt_order": list(PROVIDER_ORDER),
        "symbols": [
            {
                "symbol": record["symbol"],
                "required": record["required"],
                "status": record["status"],
                "quote_provider": (record["quote"] or {}).get("provider"),
                "history_provider": (record["history"] or {}).get("provider"),
                "quote_timestamp": (record["quote"] or {}).get("quote_timestamp"),
                "latest_bar_date": (record["history"] or {}).get("latest_bar_date"),
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

    atomic_write_text(
        provider.results_dir / "enterprise_market_data_status.json",
        json.dumps(result, indent=2, sort_keys=True) + "\n",
    )
    atomic_write_text(
        provider.results_dir / "enterprise_market_data_provider_health.json",
        json.dumps(provider_health, indent=2, sort_keys=True) + "\n",
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
    args = parser.parse_args()

    handoff_reader = partial(read_codex_market_data_handoff, handoff_dir=args.handoff_dir)
    provider = build_default_provider(Path(args.results_dir), Path(args.cache_dir), handoff_reader)
    result = refresh_strategy_market_data(
        provider,
        args.strategy_id,
        args.required_symbol,
        args.optional_symbol,
        period=args.history_period,
        interval=args.history_interval,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 2 if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
