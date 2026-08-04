#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from pathlib import Path
from src.dividend_bot.codex_robinhood_market_data_bridge import run_codex_market_data
from src.dividend_bot.enterprise_market_data_provider import build_default_provider

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy-id", required=True)
    parser.add_argument("--required-symbol", action="append", default=[])
    parser.add_argument("--optional-symbol", action="append", default=[])
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--cache-dir", default="runtime/enterprise_market_data_cache")
    args = parser.parse_args()
    provider = build_default_provider(Path(args.results_dir), Path(args.cache_dir), run_codex_market_data)
    result = provider.refresh_strategy(args.strategy_id, args.required_symbol, args.optional_symbol)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 2 if result["status"] == "BLOCKED" else 0

if __name__ == "__main__":
    raise SystemExit(main())
