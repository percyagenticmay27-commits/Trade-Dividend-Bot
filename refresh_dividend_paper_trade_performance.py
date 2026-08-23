"""Refresh authoritative read-only DIVIDEND-001 realized performance evidence.

This command rebuilds the Dividend paper-trade performance artifact directly from
``paper_trade_log.csv`` immediately before Enterprise dashboard publication. It is
reporting-only and inherits the paper-only execution locks enforced by the
underlying performance writer.
"""
from __future__ import annotations

from pathlib import Path

from src.dividend_bot.dividend_paper_trade_performance import (
    write_dividend_paper_trade_performance,
)


def main() -> int:
    root = Path(".")
    output = write_dividend_paper_trade_performance(root)
    print(f"Dividend paper performance refreshed: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
