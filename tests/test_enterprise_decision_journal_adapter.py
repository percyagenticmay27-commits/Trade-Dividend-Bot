from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.dividend_bot.enterprise_decision_journal_adapter import (
    BROKER_EXECUTION_ENABLED,
    LIVE_TRADING_ENABLED,
    PAPER_TRADE_MODE,
    READ_ONLY,
    EnterpriseDecisionJournalAdapterError,
    build_decision_journal_tab,
    load_selected_strategy_journal,
)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _journal(strategy_id: str, kind: str, decision_id: str) -> dict:
    decision = {
        "decision_id": decision_id,
        "decision_timestamp": "2026-08-01T22:00:00Z",
        "strategy_id": strategy_id,
        "strategy_kind": kind,
        "decision_type": "RECORDED",
        "status": "APPROVED",
        "summary": "Recorded strategy decision.",
        "final_rationale": "Evidence-backed decision.",
        "committee_evidence": [],
        "images": [],
    }
    if kind == "SWING":
        decision.update({"symbol": "AMD", "committee_rank": 1})
    else:
        decision.update({
            "ecosystem_name": "NVIDIA Income Ecosystem",
            "income_leg": "NVDY",
            "leverage_leg": "NVDX",
        })
    return {
        "strategy_id": strategy_id,
        "strategy_name": "Selected Strategy",
        "strategy_kind": kind,
        "journal_scope": "SELECTED_STRATEGY_ONLY",
        "sort_order": "NEWEST_FIRST",
        "decision_count": 1,
        "decisions": [decision],
        "evidence_status": "AVAILABLE",
    }


def test_loads_only_selected_dividend_journal(tmp_path: Path) -> None:
    _write(tmp_path / "dividend_strategy_decision_journal.json", _journal("DIVIDEND-001", "DIVIDEND", "D1"))
    _write(tmp_path / "swing_strategy_decision_journal.json", _journal("SWING-001", "SWING", "S1"))
    journal, warnings = load_selected_strategy_journal(
        results_dir=tmp_path,
        strategy_id="DIVIDEND-001",
        strategy_name="Dividend Income Strategy",
    )
    assert warnings == []
    assert journal["strategy_id"] == "DIVIDEND-001"
    assert journal["decisions"][0]["decision_id"] == "D1"
    assert "S1" not in json.dumps(journal)


def test_missing_artifact_returns_safe_empty_journal(tmp_path: Path) -> None:
    journal, warnings = load_selected_strategy_journal(
        results_dir=tmp_path,
        strategy_id="SWING-001",
        strategy_name="Swing Trading Strategy",
    )
    assert journal["decision_count"] == 0
    assert journal["journal_scope"] == "SELECTED_STRATEGY_ONLY"
    assert warnings


def test_cross_strategy_artifact_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path / "dividend_strategy_decision_journal.json", _journal("SWING-001", "SWING", "S1"))
    with pytest.raises(EnterpriseDecisionJournalAdapterError, match="Cross-strategy journal rejected"):
        load_selected_strategy_journal(
            results_dir=tmp_path,
            strategy_id="DIVIDEND-001",
            strategy_name="Dividend Income Strategy",
        )


def test_tab_contains_selected_strategy_html(tmp_path: Path) -> None:
    _write(tmp_path / "swing_strategy_decision_journal.json", _journal("SWING-001", "SWING", "S1"))
    tab = build_decision_journal_tab(
        results_dir=tmp_path,
        strategy_id="SWING-001",
        strategy_name="Swing Trading Strategy",
    )
    assert tab["tab_label"] == "Decision Journal"
    assert tab["decision_count"] == 1
    assert "AMD" in tab["html"]
    assert "DIVIDEND-001" not in tab["html"]


def test_unsupported_strategy_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(EnterpriseDecisionJournalAdapterError, match="Unsupported selected strategy_id"):
        load_selected_strategy_journal(
            results_dir=tmp_path,
            strategy_id="OPTIONS-001",
            strategy_name="Options Strategy",
        )


def test_safety_metadata_is_locked() -> None:
    assert PAPER_TRADE_MODE is True
    assert LIVE_TRADING_ENABLED is False
    assert BROKER_EXECUTION_ENABLED is False
    assert READ_ONLY is True
