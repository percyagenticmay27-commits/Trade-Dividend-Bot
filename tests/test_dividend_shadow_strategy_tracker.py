from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.dividend_shadow_strategy_tracker import (
    update_shadow_strategy_performance,
)


CONFIG = {
    "AMDW / AMDL": {
        "a": "AMDW",
        "b": "AMDL",
        "a_signal": "AMD",
        "b_signal": "AMD",
    }
}


def _state(as_of: str, a_price: float, b_price: float) -> dict:
    return {
        "as_of_date": as_of,
        "pairs": {
            "AMDW / AMDL": {
                "last_prices": {"A": a_price, "B": b_price},
                "a_shares": 999,
                "b_shares": 999,
                "sgov_balance": 0,
            }
        },
    }


def _evidence(*, a_buy=False, a_sell=False, b_buy=False, b_sell=False) -> dict:
    return {
        "entries": [
            {
                "symbol": "AMD",
                "strategy_signals": {
                    "strategy_a": {"buy_trigger": a_buy, "sell_trigger": a_sell},
                    "strategy_b": {"buy_eligible": b_buy, "sell_trigger": b_sell},
                },
            }
        ]
    }


def test_shadow_strategies_use_isolated_virtual_capital_only(tmp_path: Path) -> None:
    paper = _state("2026-08-11", 20.0, 10.0)
    original = json.dumps(paper, sort_keys=True)
    report = update_shadow_strategy_performance(
        paper_state=paper,
        entry_score_report=_evidence(a_buy=True, b_buy=True),
        pair_config=CONFIG,
        state_path=tmp_path / "shadow.json",
        report_path=tmp_path / "report.json",
    )
    assert json.dumps(paper, sort_keys=True) == original
    assert len(report["performance"]) == 2
    assert {row["last_action"] for row in report["performance"]} == {"SHADOW_BUY"}
    assert all(row["current_shadow_value"] == 100.0 for row in report["performance"])
    assert all(row["shadow_only"] is True for row in report["performance"])
    assert all(row["broker_execution_enabled"] is False for row in report["performance"])


def test_primary_and_shadow_can_produce_different_results(tmp_path: Path) -> None:
    state_path = tmp_path / "shadow.json"
    report_path = tmp_path / "report.json"
    update_shadow_strategy_performance(
        paper_state=_state("2026-08-11", 20.0, 10.0),
        entry_score_report=_evidence(a_buy=True, b_buy=False),
        pair_config=CONFIG,
        state_path=state_path,
        report_path=report_path,
    )
    report = update_shadow_strategy_performance(
        paper_state=_state("2026-08-12", 22.0, 11.0),
        entry_score_report=_evidence(),
        pair_config=CONFIG,
        state_path=state_path,
        report_path=report_path,
    )
    rows = {row["strategy_id"]: row for row in report["performance"]}
    assert rows["STRATEGY_A"]["total_return_percent"] == 10.0
    assert rows["STRATEGY_B"]["total_return_percent"] == 0.0
    assert rows["STRATEGY_A"]["role"] == "STRATEGY_A_BASELINE"
    assert rows["STRATEGY_B"]["role"] == "TEST_CANDIDATE"


def test_same_date_rerun_does_not_duplicate_observation_or_trade(tmp_path: Path) -> None:
    state_path = tmp_path / "shadow.json"
    report_path = tmp_path / "report.json"
    kwargs = {
        "paper_state": _state("2026-08-11", 20.0, 10.0),
        "entry_score_report": _evidence(a_buy=True, b_buy=True),
        "pair_config": CONFIG,
        "state_path": state_path,
        "report_path": report_path,
    }
    update_shadow_strategy_performance(**kwargs)
    report = update_shadow_strategy_performance(**kwargs)
    assert all(row["observation_count"] == 1 for row in report["performance"])
    assert all(row["last_action"] == "SHADOW_BUY" for row in report["performance"])


def test_shadow_sell_closes_virtual_trade_without_touching_paper_ledger(tmp_path: Path) -> None:
    state_path = tmp_path / "shadow.json"
    report_path = tmp_path / "report.json"
    update_shadow_strategy_performance(
        paper_state=_state("2026-08-11", 20.0, 10.0),
        entry_score_report=_evidence(a_buy=True),
        pair_config=CONFIG,
        state_path=state_path,
        report_path=report_path,
    )
    report = update_shadow_strategy_performance(
        paper_state=_state("2026-08-12", 18.0, 9.0),
        entry_score_report=_evidence(a_sell=True),
        pair_config=CONFIG,
        state_path=state_path,
        report_path=report_path,
    )
    row = next(item for item in report["performance"] if item["strategy_id"] == "STRATEGY_A")
    assert row["last_action"] == "SHADOW_SELL"
    assert row["completed_trade_count"] == 1
    assert row["current_shadow_value"] == 90.0
    assert row["max_drawdown_percent"] == 10.0
    assert not (tmp_path / "paper_trade_log.csv").exists()


def test_missing_signal_evidence_holds_and_does_not_fabricate_trade(tmp_path: Path) -> None:
    report = update_shadow_strategy_performance(
        paper_state=_state("2026-08-11", 20.0, 10.0),
        entry_score_report={"entries": []},
        pair_config=CONFIG,
        state_path=tmp_path / "shadow.json",
        report_path=tmp_path / "report.json",
    )
    assert all(row["last_action"] == "SHADOW_HOLD" for row in report["performance"])
    assert all(row["completed_trade_count"] == 0 for row in report["performance"])
    assert all(row["total_return_percent"] == 0.0 for row in report["performance"])
