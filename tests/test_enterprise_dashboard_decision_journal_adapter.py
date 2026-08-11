from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from src.dividend_bot.enterprise_dashboard_decision_journal_adapter import (
    attach_strategy_decision_journals,
    load_strategy_decision_journals,
)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _journal(strategy_id: str, decisions: list[dict] | None = None) -> dict:
    rows = decisions or []
    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy_id,
        "strategy_kind": "DIVIDEND" if strategy_id == "DIVIDEND-001" else "SWING",
        "decision_count": len(rows),
        "decisions": rows,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "read_only": True,
    }


def test_attaches_only_matching_strategy_journal(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write(
        results / "dividend_strategy_decision_journal.json",
        _journal(
            "DIVIDEND-001",
            [{"strategy_id": "DIVIDEND-001", "decision_id": "D-1"}],
        ),
    )
    _write(
        results / "swing_strategy_decision_journal.json",
        _journal("SWING-001"),
    )
    rows = [
        {"strategy_id": "DIVIDEND-001", "allocated_capital": 5000.0},
        {"strategy_id": "SWING-001", "allocated_capital": 4500.0},
    ]
    before = deepcopy(rows)

    enriched, warnings = attach_strategy_decision_journals(
        rows, results_dir=results
    )

    assert warnings == []
    assert rows == before
    assert enriched[0]["decision_journal"]["strategy_id"] == "DIVIDEND-001"
    assert enriched[0]["decision_count"] == 1
    assert enriched[0]["decision_journal_status"] == "AVAILABLE"
    assert enriched[1]["decision_journal"]["strategy_id"] == "SWING-001"
    assert enriched[1]["decision_journal_status"] == "EMPTY"


def test_missing_journal_preserves_kpi_row_with_safe_status(tmp_path: Path) -> None:
    rows = [{"strategy_id": "SWING-001", "opportunity_quality": 91}]

    enriched, warnings = attach_strategy_decision_journals(
        rows, results_dir=tmp_path / "results"
    )

    assert warnings == []
    assert enriched[0]["opportunity_quality"] == 91
    assert enriched[0]["decision_journal"] is None
    assert enriched[0]["decision_journal_status"] == "NOT_REPORTED"
    assert enriched[0]["decision_count"] == 0


def test_safe_embedded_journal_survives_when_standalone_is_missing(
    tmp_path: Path,
) -> None:
    embedded = _journal(
        "DIVIDEND-001",
        [{"strategy_id": "DIVIDEND-001", "decision_id": "D-EMBEDDED"}],
    )
    rows = [{
        "strategy_id": "DIVIDEND-001",
        "decision_journal": embedded,
        "decision_journal_status": "AVAILABLE",
        "decision_count": 1,
    }]

    enriched, warnings = attach_strategy_decision_journals(
        rows, results_dir=tmp_path / "results"
    )

    assert warnings == []
    assert enriched[0]["decision_journal"] == embedded
    assert enriched[0]["decision_journal_status"] == "AVAILABLE"
    assert enriched[0]["decision_count"] == 1
    assert enriched[0]["decision_journal_path"] == "EMBEDDED_HOST_EVIDENCE"


def test_unsafe_embedded_journal_is_rejected(tmp_path: Path) -> None:
    embedded = _journal("DIVIDEND-001")
    embedded["live_trading_enabled"] = True
    rows = [{
        "strategy_id": "DIVIDEND-001",
        "decision_journal": embedded,
        "decision_journal_status": "AVAILABLE",
    }]

    enriched, warnings = attach_strategy_decision_journals(
        rows, results_dir=tmp_path / "results"
    )

    assert enriched[0]["decision_journal"] is None
    assert enriched[0]["decision_journal_status"] == "NOT_REPORTED"
    assert enriched[0]["decision_count"] == 0
    assert any("Unsafe strategy Decision Journal rejected" in item for item in warnings)


def test_standalone_journal_overrides_embedded_host_evidence(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"
    standalone = _journal(
        "DIVIDEND-001",
        [{"strategy_id": "DIVIDEND-001", "decision_id": "D-STANDALONE"}],
    )
    _write(results / "dividend_strategy_decision_journal.json", standalone)
    embedded = _journal(
        "DIVIDEND-001",
        [{"strategy_id": "DIVIDEND-001", "decision_id": "D-EMBEDDED"}],
    )

    enriched, warnings = attach_strategy_decision_journals(
        [{"strategy_id": "DIVIDEND-001", "decision_journal": embedded}],
        results_dir=results,
    )

    assert warnings == []
    assert enriched[0]["decision_journal"] == standalone
    assert enriched[0]["decision_journal_path"].endswith(
        "dividend_strategy_decision_journal.json"
    )


def test_cross_strategy_entry_is_rejected(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write(
        results / "dividend_strategy_decision_journal.json",
        _journal(
            "DIVIDEND-001",
            [{"strategy_id": "SWING-001", "decision_id": "BAD"}],
        ),
    )

    journals, _, warnings = load_strategy_decision_journals(results)

    assert journals == {}
    assert len(warnings) == 1
    assert "Cross-strategy" in warnings[0]


def test_unsafe_journal_is_rejected(tmp_path: Path) -> None:
    results = tmp_path / "results"
    payload = _journal("SWING-001")
    payload["live_trading_enabled"] = True
    _write(results / "swing_strategy_decision_journal.json", payload)

    journals, _, warnings = load_strategy_decision_journals(results)

    assert journals == {}
    assert any("Unsafe strategy Decision Journal rejected" in item for item in warnings)


def test_malformed_journal_warns_without_crashing(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir(parents=True)
    (results / "swing_strategy_decision_journal.json").write_text(
        "{bad", encoding="utf-8"
    )

    journals, _, warnings = load_strategy_decision_journals(results)

    assert journals == {}
    assert any("Invalid strategy Decision Journal" in item for item in warnings)
