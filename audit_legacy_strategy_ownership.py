"""Generate a read-only audit of pre-ownership Dividend paper positions."""
from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.dividend_legacy_strategy_ownership_audit import (
    build_legacy_strategy_ownership_audit,
    read_csv_rows,
)

STATE_PATH = Path("paper_state.json")
LOG_PATH = Path("paper_trade_log.csv")
MARKET_PATH = Path("market_data_snapshot.json")
OUTPUT_PATH = Path("results/legacy_strategy_ownership_audit.json")


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def main() -> int:
    report = build_legacy_strategy_ownership_audit(
        state=_read_json(STATE_PATH),
        log_rows=read_csv_rows(LOG_PATH),
        market_snapshot=_read_json(MARKET_PATH),
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Legacy ownership audit: {OUTPUT_PATH}")
    print(f"Audited unowned open positions: {report['audited_position_count']}")
    print(f"Eligible for explicit backfill: {report['eligible_for_explicit_backfill_count']}")
    print("State mutated: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
