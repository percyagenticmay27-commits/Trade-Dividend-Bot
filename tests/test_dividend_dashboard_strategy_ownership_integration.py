from __future__ import annotations

import csv
import json
from pathlib import Path

from src.dividend_bot.dividend_dashboard_evidence import build_dividend_dashboard_evidence


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_current_holding_owner_reaches_dashboard_evidence(tmp_path: Path) -> None:
    _write_json(tmp_path / "paper_state.json", {
        "pairs": {
            "AAA / BBB": {
                "a_shares": 2.0,
                "b_shares": 0.0,
                "last_prices": {"A": 10.0, "B": 20.0},
                "sgov_balance": 0.0,
                "total_dividends_received": 0.0,
                "a_strategy_owner": "STRATEGY_A",
                "strategy_owner": "STRATEGY_A",
                "strategy_ownership_source": "QUALIFIED_ENTRY_GATE",
            }
        }
    })
    payload = build_dividend_dashboard_evidence(tmp_path)
    holding = next(row for row in payload["holdings"] if row["symbol"] == "AAA")
    assert holding["strategy_owner"] == "STRATEGY_A"
    assert holding["entry_method"] == "STRATEGY_A"
    assert holding["strategy_ownership_source"] == "QUALIFIED_ENTRY_GATE"


def test_completed_owner_controlled_exit_reaches_lifecycle_evidence(tmp_path: Path) -> None:
    _write_json(tmp_path / "paper_state.json", {
        "pairs": {
            "CCC / DDD": {
                "a_shares": 0.0,
                "b_shares": 0.0,
                "last_prices": {"A": 9.0, "B": 20.0},
                "sgov_balance": 100.0,
                "total_dividends_received": 0.0,
                "strategy_owner": None,
                "strategy_ownership_source": "CLOSED_TO_SGOV",
                "last_exit_strategy_owner": "STRATEGY_B",
                "last_exit_strategy_reasons": ["PRICE_BELOW_EMA20"],
            }
        }
    })
    with (tmp_path / "paper_trade_log.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "Date", "Pair", "Sleeve", "Action", "Ticker", "Shares", "Price", "Paper_Value", "Reason"
        ])
        writer.writeheader()
        writer.writerow({
            "Date": "2026-08-01", "Pair": "CCC / DDD", "Sleeve": "A",
            "Action": "PAPER_BUY_OPEN", "Ticker": "CCC", "Shares": "10",
            "Price": "10", "Paper_Value": "100", "Reason": "Qualified entry",
        })
        writer.writerow({
            "Date": "2026-08-05", "Pair": "CCC / DDD", "Sleeve": "A",
            "Action": "PAPER_SELL_TO_SGOV", "Ticker": "CCC", "Shares": "10",
            "Price": "9", "Paper_Value": "90", "Reason": "Strategy-owner exit: PRICE_BELOW_EMA20",
        })

    payload = build_dividend_dashboard_evidence(tmp_path)
    life = next(row for row in payload["performance_detail"]["position_lifecycle"] if row["symbol"] == "CCC")
    assert life["lifecycle_status"] == "PARKED_IN_SGOV"
    assert life["entry_method"] == "STRATEGY_B"
    assert life["exit_method"] == "STRATEGY_B"
    assert life["last_exit_strategy_owner"] == "STRATEGY_B"
    assert life["last_exit_strategy_reasons"] == ["PRICE_BELOW_EMA20"]
    assert life["last_exit_reason"] == "PRICE_BELOW_EMA20"
    assert life["strategy_exit_evidence_source"] == "paper_state.json"
