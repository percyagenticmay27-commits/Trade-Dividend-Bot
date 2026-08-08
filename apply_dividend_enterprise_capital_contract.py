"""Apply the Enterprise DIVIDEND-001 paper allocation to existing paper_state.json.

Administrative PAPER ONLY normalization. No broker access, no order placement, no
market-data fetch, and no trade-log mutation.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from src.dividend_bot.dividend_enterprise_capital_contract import (
    read_enterprise_dividend_allocation,
    scale_paper_state_to_allocation,
)

STATE_PATH = Path("paper_state.json")
CASH_STATE_PATH = Path("state/paper_cash_account.json")


def _atomic_write(path: Path, payload: dict) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent or Path('.')))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main() -> int:
    allocation = read_enterprise_dividend_allocation(CASH_STATE_PATH)
    if allocation is None:
        raise SystemExit("DIVIDEND-001 Enterprise allocation is not available; paper state was not changed.")
    if not STATE_PATH.is_file():
        raise SystemExit("paper_state.json is missing; paper state was not changed.")
    payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("paper_state.json root must be an object; paper state was not changed.")
    normalized, factor = scale_paper_state_to_allocation(payload, allocation)
    _atomic_write(STATE_PATH, normalized)
    print("PAPER ONLY - NO REAL TRADES EXECUTED")
    print(f"Enterprise allocation: ${allocation:,.2f}")
    print(f"Administrative scale factor applied: {factor:.6f}")
    print(f"Paper state: {STATE_PATH}")
    print("Trade log unchanged: yes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
