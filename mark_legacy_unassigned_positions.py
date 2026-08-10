"""Explicitly tag open pre-ownership paper positions as LEGACY_UNASSIGNED.

The command never assigns Strategy A or Strategy B, never places orders, and never
moves capital. It writes a backup before changing paper_state.json.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.dividend_legacy_strategy_management import mark_legacy_unassigned_open_positions

STATE_PATH = Path("paper_state.json")
BACKUP_PATH = Path("paper_state.pre_legacy_unassigned_migration.json")
AUDIT_PATH = Path("results/legacy_unassigned_position_migration.json")


def main() -> int:
    if not STATE_PATH.is_file():
        print(f"State not found: {STATE_PATH}")
        return 1

    original_text = STATE_PATH.read_text(encoding="utf-8")
    state = json.loads(original_text)
    migrated, changes = mark_legacy_unassigned_open_positions(state)

    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    audit = {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "state_mutated": bool(changes),
        "changed_position_count": len(changes),
        "changes": changes,
    }
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if not changes:
        print("Legacy unassigned migration: no eligible open positions")
        print(f"Audit: {AUDIT_PATH}")
        return 0

    if not BACKUP_PATH.exists():
        BACKUP_PATH.write_text(original_text, encoding="utf-8")
    STATE_PATH.write_text(json.dumps(migrated, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Legacy unassigned positions marked: {len(changes)}")
    print(f"Backup: {BACKUP_PATH}")
    print(f"State: {STATE_PATH}")
    print(f"Audit: {AUDIT_PATH}")
    print("Management policy: REQUIRE_STRATEGY_A_AND_B_SELL_CONSENSUS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
