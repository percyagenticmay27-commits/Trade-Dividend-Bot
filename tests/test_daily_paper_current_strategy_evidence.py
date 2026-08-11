from __future__ import annotations

import json
from pathlib import Path

import pytest

import run_daily_dividend_cycle
import run_daily_paper_cycle
from src.dividend_bot import dividend_daily_evidence_refresh


def test_current_strategy_evidence_preflight_writes_valid_current_report(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_cycle(*, root_path: str):
        root = Path(root_path)
        (root / "entry_score_report.json").write_text(
            json.dumps({
                "generated_at_utc": "2026-08-10T21:00:00Z",
                "entries": [{
                    "symbol": "AMD",
                    "strategy_signals": {
                        "strategy_a": {"sell_trigger": False},
                        "strategy_b": {"sell_trigger": False},
                    },
                }],
            }),
            encoding="utf-8",
        )
        return {"run_status": "COMPLETE", "errors": []}

    monkeypatch.setattr(
        run_daily_dividend_cycle,
        "run_daily_dividend_cycle",
        fake_cycle,
    )

    result = run_daily_paper_cycle.refresh_current_strategy_evidence(tmp_path)

    assert result["run_status"] == "COMPLETE"
    payload = json.loads((tmp_path / "entry_score_report.json").read_text())
    assert payload["generated_at_utc"] == "2026-08-10T21:00:00Z"
    assert payload["entries"][0]["symbol"] == "AMD"


def test_current_strategy_evidence_failure_blocks_stale_paper_authority(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "entry_score_report.json").write_text(
        json.dumps({
            "generated_at_utc": "2026-08-09T21:00:00Z",
            "entries": [{"symbol": "AMD"}],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        run_daily_dividend_cycle,
        "run_daily_dividend_cycle",
        lambda **_: {
            "run_status": "ERROR",
            "errors": ["entry_score stage failed"],
        },
    )

    with pytest.raises(RuntimeError, match="entry_score stage failed"):
        run_daily_paper_cycle.refresh_current_strategy_evidence(tmp_path)


def test_main_orders_current_evidence_before_paper_cycle_and_publication(
    monkeypatch,
) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        run_daily_paper_cycle,
        "refresh_current_strategy_evidence",
        lambda _root: calls.append("current_evidence")
        or {"run_status": "COMPLETE"},
    )
    monkeypatch.setattr(
        run_daily_paper_cycle,
        "run_daily_cycle",
        lambda: calls.append("paper_cycle")
        or {
            "state": {"as_of_date": "2026-08-10"},
            "new_log_rows": [],
            "duplicate_date": False,
        },
    )
    monkeypatch.setattr(
        run_daily_paper_cycle,
        "refresh_shadow_strategy_evidence",
        lambda _state, _root: calls.append("shadow_strategy_evidence")
        or {"performance": []},
    )
    monkeypatch.setattr(
        run_daily_paper_cycle,
        "refresh_strategy_promotion_governance",
        lambda _root: calls.append("strategy_promotion_governance")
        or {"assignments": {}, "requests": [], "activated": []},
    )
    monkeypatch.setattr(
        dividend_daily_evidence_refresh,
        "refresh_dividend_daily_evidence",
        lambda _root: calls.append("enterprise_publication")
        or {
            "status": "COMPLETE",
            "daily_dividend_cycle_status": "COMPLETE",
            "candidate_count": 1,
            "watchlist_count": 1,
            "kpi_evidence_path": "results/dividend_strategy_kpi_evidence.json",
            "warnings": [],
            "errors": [],
        },
    )

    assert run_daily_paper_cycle.main() == 0
    assert calls == [
        "current_evidence",
        "paper_cycle",
        "shadow_strategy_evidence",
        "strategy_promotion_governance",
        "enterprise_publication",
    ]



def test_strategy_promotion_governance_initializes_a_as_pair_primary(tmp_path: Path) -> None:
    result = run_daily_paper_cycle.refresh_strategy_promotion_governance(tmp_path)
    assert result["assignments"]
    assert all(
        row["primary_strategy"] == "STRATEGY_A"
        for row in result["assignments"].values()
    )
    assert result["requests"] == []
    assignment_path = tmp_path / "state/dividend_pair_strategy_assignments.json"
    payload = json.loads(assignment_path.read_text(encoding="utf-8"))
    assert payload["paper_trade_mode"] is True
    assert payload["broker_execution_enabled"] is False



def test_shadow_evidence_is_written_before_promotion_evaluation(tmp_path: Path) -> None:
    state = {
        "as_of_date": "2026-08-11",
        "pairs": {
            "AMDW / AMDL": {
                "last_prices": {"A": 20.0, "B": 10.0},
            }
        },
    }
    (tmp_path / "entry_score_report.json").write_text(
        json.dumps({
            "entries": [{
                "symbol": "AMD",
                "strategy_signals": {
                    "strategy_a": {"buy_trigger": True, "sell_trigger": False},
                    "strategy_b": {"buy_eligible": False, "sell_trigger": False},
                },
            }]
        }),
        encoding="utf-8",
    )
    report = run_daily_paper_cycle.refresh_shadow_strategy_evidence(state, tmp_path)
    assert report["shadow_only"] is True
    assert (tmp_path / "results/dividend_strategy_shadow_performance.json").is_file()
    rows = {
        row["strategy_id"]: row
        for row in report["performance"]
        if row["pair"] == "AMDW / AMDL"
    }
    assert rows["STRATEGY_A"]["last_action"] == "SHADOW_BUY"
    assert rows["STRATEGY_B"]["last_action"] == "SHADOW_HOLD"
