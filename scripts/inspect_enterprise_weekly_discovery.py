#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    weekly = _load(root / "results" / "enterprise_weekly_market_discovery.json")
    swing = _load(root / "results" / "enterprise_swing_discovery_bucket.json")
    dividend = _load(root / "results" / "enterprise_dividend_discovery_bucket.json")
    print("Generated:", weekly.get("generated_at"))
    print("Active nominations:", len(weekly.get("candidates", [])))
    print("Research evidence only:", len(weekly.get("research_evidence_pool", [])))
    print("Expired candidates:", len(weekly.get("expired_candidates", [])))
    print("Swing candidates:", len(swing.get("candidates", [])))
    print("Dividend candidates:", len(dividend.get("candidates", [])))
    print("Paper trade mode:", weekly.get("paper_trade_mode"))
    print("Live trading enabled:", weekly.get("live_trading_enabled"))
    print("Broker execution enabled:", weekly.get("broker_execution_enabled"))
    print("Order placement enabled:", weekly.get("order_placement_enabled"))
    print("Capital movement enabled:", weekly.get("capital_movement_enabled"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
