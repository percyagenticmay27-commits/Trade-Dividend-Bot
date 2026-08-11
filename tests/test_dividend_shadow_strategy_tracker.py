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


def _state(as_of: str, a_price: float, b_price: float, capital_bucket: float = 600.0) -> dict:
    return {
        "as_of_date": as_of,
        "pairs": {
            "AMDW / AMDL": {
                "last_prices": {"A": a_price, "B": b_price},
                "capital_bucket": capital_bucket,
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
    assert all(row["virtual_capital_basis"] == 600.0 for row in report["performance"])
    assert all(row["current_shadow_value"] == 600.0 for row in report["performance"])
    assert all(row["virtual_gain_loss"] == 0.0 for row in report["performance"])
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
    assert rows["STRATEGY_A"]["role"] == "PRODUCTION_BASELINE"
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
    assert row["current_shadow_value"] == 540.0
    assert row["virtual_gain_loss"] == -60.0
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


def test_legacy_100_dollar_state_is_rebased_without_changing_return_history(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "shadow.json"
    report_path = tmp_path / "report.json"
    state_path.write_text(
        json.dumps({
            "schema_version": "1.0",
            "as_of_date": "2026-08-10",
            "starting_value_per_strategy_pair": 100.0,
            "pairs": {
                "AMDW / AMDL": {
                    "STRATEGY_A": {
                        "evaluation_start": "2026-08-10",
                        "evaluation_end": "2026-08-10",
                        "starting_value": 100.0,
                        "cash": 0.0,
                        "a_shares": 3.5,
                        "b_shares": 3.0,
                        "in_market": True,
                        "current_value": 100.0,
                        "peak_value": 100.0,
                        "max_drawdown_percent": 0.0,
                        "observation_count": 1,
                        "completed_trade_count": 0,
                        "last_observation_date": "2026-08-10",
                        "last_action": "SHADOW_BUY",
                    }
                }
            },
        }),
        encoding="utf-8",
    )
    report = update_shadow_strategy_performance(
        paper_state=_state("2026-08-11", 22.0, 11.0),
        entry_score_report=_evidence(),
        pair_config=CONFIG,
        state_path=state_path,
        report_path=report_path,
    )
    row = next(
        item
        for item in report["performance"]
        if item["strategy_id"] == "STRATEGY_A"
    )
    assert row["virtual_capital_basis"] == 600.0
    assert row["current_shadow_value"] == 660.0
    assert row["virtual_gain_loss"] == 60.0
    assert row["total_return_percent"] == 10.0
    assert row["observation_count"] == 2


def test_missing_authoritative_pair_capital_is_reported_and_not_fabricated(
    tmp_path: Path,
) -> None:
    paper = _state("2026-08-11", 20.0, 10.0)
    del paper["pairs"]["AMDW / AMDL"]["capital_bucket"]
    report = update_shadow_strategy_performance(
        paper_state=paper,
        entry_score_report=_evidence(a_buy=True, b_buy=True),
        pair_config=CONFIG,
        state_path=tmp_path / "shadow.json",
        report_path=tmp_path / "report.json",
    )
    assert report["performance"] == []
    assert report["warnings"] == [
        "AMDW / AMDL: pair paper state has no valid capital_bucket; "
        "shadow comparison skipped"
    ]


def test_registered_strategy_c_is_tracked_without_tracker_code_changes(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps({
            "strategies": [
                {
                    "strategy_id": "STRATEGY_A",
                    "display_name": "Strategy A",
                    "strategy_role": "PRODUCTION_BASELINE",
                    "lifecycle_status": "ACTIVE",
                    "version": "1.0",
                    "description": "Default.",
                    "signal_key": "strategy_a",
                    "buy_signal_field": "buy_trigger",
                    "sell_signal_field": "sell_trigger",
                    "eligible_pairs": ["*"],
                    "promotion_eligible": True,
                },
                {
                    "strategy_id": "STRATEGY_B",
                    "display_name": "Strategy B",
                    "strategy_role": "TEST_CANDIDATE",
                    "lifecycle_status": "ACTIVE",
                    "version": "1.0",
                    "description": "Test.",
                    "signal_key": "strategy_b",
                    "buy_signal_field": "buy_eligible",
                    "sell_signal_field": "sell_trigger",
                    "eligible_pairs": ["*"],
                    "promotion_eligible": True,
                },
                {
                    "strategy_id": "STRATEGY_C",
                    "display_name": "Strategy C",
                    "strategy_role": "TEST_CANDIDATE",
                    "lifecycle_status": "ACTIVE",
                    "version": "1.0",
                    "description": "Explicit fixture strategy.",
                    "signal_key": "strategy_c",
                    "buy_signal_field": "buy_ready",
                    "sell_signal_field": "sell_ready",
                    "eligible_pairs": ["AMDW / AMDL"],
                    "promotion_eligible": True,
                },
            ]
        }),
        encoding="utf-8",
    )
    report = update_shadow_strategy_performance(
        paper_state=_state("2026-08-11", 20.0, 10.0),
        entry_score_report={
            "entries": [{
                "symbol": "AMD",
                "strategy_signals": {
                    "strategy_a": {"buy_trigger": False, "sell_trigger": False},
                    "strategy_b": {"buy_eligible": False, "sell_trigger": False},
                    "strategy_c": {"buy_ready": True, "sell_ready": False},
                },
            }]
        },
        pair_config=CONFIG,
        state_path=tmp_path / "shadow.json",
        report_path=tmp_path / "report.json",
        registry_path=registry,
    )
    rows = {row["strategy_id"]: row for row in report["performance"]}
    assert set(rows) == {"STRATEGY_A", "STRATEGY_B", "STRATEGY_C"}
    assert rows["STRATEGY_C"]["last_action"] == "SHADOW_BUY"
    assert rows["STRATEGY_C"]["virtual_capital_basis"] == 600.0
    assert rows["STRATEGY_C"]["display_name"] == "Strategy C"
