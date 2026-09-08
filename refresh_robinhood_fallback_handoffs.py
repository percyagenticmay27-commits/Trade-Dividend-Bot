#!/usr/bin/env python3
"""Create Robinhood MCP handoffs only for unresolved market-data operations."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from root_codex_market_data_handoff import atomic_write_handoff
from src.dividend_bot.codex_robinhood_market_data_bridge import run_codex_market_data


def unresolved_operations(status: dict) -> list[tuple[str, str]]:
    operations: list[tuple[str, str]] = []
    for record in status.get("records", []):
        symbol = str(record.get("symbol", "")).strip().upper()
        if not symbol:
            continue
        if not record.get("quote"):
            operations.append(("get_quote", symbol))
        if not record.get("history"):
            operations.append(("get_history", symbol))
    return operations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-file", default="results/enterprise_market_data_status.json")
    parser.add_argument("--output-dir", default="/run/enterprise-market-data-handoff")
    parser.add_argument("--period", default="1mo")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--codex-path", default="/usr/local/bin/codex")
    parser.add_argument("--timeout-seconds", type=int, default=45)
    args = parser.parse_args()

    if os.geteuid() != 0:
        raise PermissionError("conditional Robinhood fallback must run as root")

    status_path = Path(args.status_file)
    if not status_path.is_file():
        return 0
    status = json.loads(status_path.read_text(encoding="utf-8"))
    operations = unresolved_operations(status)
    if not operations:
        return 0

    output_dir = Path(args.output_dir)
    failures: list[str] = []
    for operation, symbol in operations:
        try:
            payload = run_codex_market_data(
                operation,
                symbol,
                args.period if operation == "get_history" else "",
                args.interval if operation == "get_history" else "",
                timeout_seconds=args.timeout_seconds,
                codex_path=args.codex_path,
            )
            suffix = "quote" if operation == "get_quote" else "history"
            atomic_write_handoff(output_dir / f"{symbol}.{suffix}.json", payload)
        except Exception as exc:
            failures.append(f"{operation}:{symbol}:{type(exc).__name__}:{exc}")

    if failures:
        print(json.dumps({"robinhood_fallback_failures": failures}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
