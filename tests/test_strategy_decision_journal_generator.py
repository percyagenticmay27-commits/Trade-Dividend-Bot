from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.strategy_decision_journal_generator import (
    generate_all_strategy_decision_journals,
    generate_strategy_decision_journal,
)


def _dividend_entry(timestamp: str = "2026-08-01T18:00:00Z") -> dict:
    return {
        "decision_id": "DIV-1",
        "decision_timestamp": timestamp,
        "strategy_id": "DIVIDEND-001",
        "strategy_kind": "DIVIDEND",
        "decision_type": "SELECT_PAIR",
        "status": "APPROVED",
        "summary": "Selected NVIDIA income ecosystem pair.",
        "final_rationale": "NVDY and NVDX ranked above same-ecosystem alternatives.",
        "ecosystem_id": "NVIDIA-INCOME",
        "ecosystem_name": "NVIDIA Income Ecosystem",
        "ecosystem_mode": "PAIR",
        "income_leg": "NVDY",
        "leverage_leg": "NVDX",
        "income_alternatives": ["NVDW"],
        "leverage_alternatives": ["NVDU"],
        "income_leg_reason": "Higher qualified income score than NVDW.",
        "leverage_leg_reason": "Higher leverage score than NVDU.",
        "pair_compatibility_reason": "The two legs satisfy the ecosystem balance rules.",
        "committee_evidence": [],
        "images": [],
    }


def _swing_entry(timestamp: str = "2026-08-01T19:00:00Z") -> dict:
    return {
        "decision_id": "SW-1",
        "decision_timestamp": timestamp,
        "strategy_id": "SWING-001",
        "strategy_kind": "SWING",
        "decision_type": "ADD_TO_WATCHLIST",
        "status": "APPROVED",
        "summary": "AMD ranked as a qualified Swing opportunity.",
        "final_rationale": "Swing committee evidence supported monitoring AMD.",
        "symbol": "AMD",
        "committee_rank": 2,
        "opportunity_quality": 86,
        "entry_score": 71,
        "committee_evidence": [],
        "images": [],
    }


def test_safe_empty_journals_are_written(tmp_path: Path) -> None:
    summary = generate_all_strategy_decision_journals(results_dir=tmp_path)
    assert summary["generation_complete"] is True
    assert summary["decision_count"] == 0
    for path in summary["paths"].values():
        assert Path(path).is_file()


def test_empty_journal_reports_not_reported(tmp_path: Path) -> None:
    generate_all_strategy_decision_journals(results_dir=tmp_path)
    payload = json.loads((tmp_path / "dividend_strategy_decision_journal.json").read_text())
    assert payload["evidence_status"] == "NOT_REPORTED"
    assert payload["decisions"] == []


def test_dividend_source_builds_ecosystem_pair(tmp_path: Path) -> None:
    source = tmp_path / "dividend.json"
    source.write_text(json.dumps({"decisions": [_dividend_entry()]}), encoding="utf-8")
    summary = generate_strategy_decision_journal(
        results_dir=tmp_path,
        strategy_id="DIVIDEND-001",
        strategy_kind="DIVIDEND",
        strategy_name="Dividend Income Strategy",
        output_name="dividend_strategy_decision_journal.json",
        source_paths=[source],
    )
    payload = json.loads(Path(summary["path"]).read_text())
    assert payload["decisions"][0]["ecosystem"]["income_leg"] == "NVDY"
    assert payload["decisions"][0]["ecosystem"]["leverage_leg"] == "NVDX"


def test_swing_source_builds_opportunity(tmp_path: Path) -> None:
    source = tmp_path / "swing.json"
    source.write_text(json.dumps([_swing_entry()]), encoding="utf-8")
    summary = generate_strategy_decision_journal(
        results_dir=tmp_path,
        strategy_id="SWING-001",
        strategy_kind="SWING",
        strategy_name="Swing Trading Strategy",
        output_name="swing_strategy_decision_journal.json",
        source_paths=[source],
    )
    payload = json.loads(Path(summary["path"]).read_text())
    assert payload["decisions"][0]["symbol"] == "AMD"


def test_cross_strategy_rows_are_filtered(tmp_path: Path) -> None:
    wrong = _swing_entry()
    source = tmp_path / "mixed.json"
    source.write_text(json.dumps({"records": [wrong]}), encoding="utf-8")
    summary = generate_strategy_decision_journal(
        results_dir=tmp_path,
        strategy_id="DIVIDEND-001",
        strategy_kind="DIVIDEND",
        strategy_name="Dividend Income Strategy",
        output_name="dividend_strategy_decision_journal.json",
        source_paths=[source],
    )
    assert summary["decision_count"] == 0


def test_decisions_are_newest_first(tmp_path: Path) -> None:
    source = tmp_path / "swing.json"
    source.write_text(
        json.dumps({"entries": [_swing_entry("2026-07-01T00:00:00Z"), _swing_entry()]}),
        encoding="utf-8",
    )
    summary = generate_strategy_decision_journal(
        results_dir=tmp_path,
        strategy_id="SWING-001",
        strategy_kind="SWING",
        strategy_name="Swing Trading Strategy",
        output_name="swing_strategy_decision_journal.json",
        source_paths=[source],
    )
    payload = json.loads(Path(summary["path"]).read_text())
    assert payload["decisions"][0]["decision_timestamp"] == "2026-08-01T19:00:00Z"


def test_malformed_source_warns_and_still_writes(tmp_path: Path) -> None:
    source = tmp_path / "bad.json"
    source.write_text("{bad", encoding="utf-8")
    summary = generate_strategy_decision_journal(
        results_dir=tmp_path,
        strategy_id="SWING-001",
        strategy_kind="SWING",
        strategy_name="Swing Trading Strategy",
        output_name="swing_strategy_decision_journal.json",
        source_paths=[source],
    )
    assert summary["decision_count"] == 0
    assert any("could not be read" in warning for warning in summary["warnings"])
    assert Path(summary["path"]).is_file()


def test_safety_metadata_is_locked(tmp_path: Path) -> None:
    summary = generate_all_strategy_decision_journals(results_dir=tmp_path)
    assert summary["paper_trade_mode"] is True
    assert summary["live_trading_enabled"] is False
    assert summary["broker_execution_enabled"] is False
    assert summary["read_only"] is True
