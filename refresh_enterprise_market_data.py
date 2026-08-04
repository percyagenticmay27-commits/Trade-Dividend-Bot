#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from functools import partial
from pathlib import Path

from src.dividend_bot.codex_robinhood_market_data_bridge import read_codex_market_data_handoff
from src.dividend_bot.enterprise_market_data_provider import build_default_provider

DEFAULT_CACHE_DIR = "/var/lib/enterprise-market-data-cache"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy-id", required=True)
    parser.add_argument("--required-symbol", action="append", default=[])
    parser.add_argument("--optional-symbol", action="append", default=[])
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--handoff-dir", default="/run/enterprise-market-data-handoff")
    args = parser.parse_args()

    handoff_reader = partial(read_codex_market_data_handoff, handoff_dir=args.handoff_dir)
    provider = build_default_provider(Path(args.results_dir), Path(args.cache_dir), handoff_reader)
    result = provider.refresh_strategy(args.strategy_id, args.required_symbol, args.optional_symbol)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 2 if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
