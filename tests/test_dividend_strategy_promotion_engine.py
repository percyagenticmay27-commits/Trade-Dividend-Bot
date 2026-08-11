from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.dividend_bot.dividend_strategy_promotion_engine import (
    PENDING,
    PROMOTED,
    activate_unvetoed_promotions,
    challenger_qualification,
    create_promotion_requests,
    ensure_pair_assignments,
    load_assignments,
    load_requests,
)


def _row(strategy: str, *, total_return: float, drawdown: float, observations: int = 90, trades: int = 3):
    return {
        "pair": "AMDW / AMDL",
        "strategy_id": strategy,
        "evaluation_start": "2026-05-01",
        "evaluation_end": "2026-07-29",
        "total_return_percent": total_return,
        "max_drawdown_percent": drawdown,
        "observation_count": observations,
        "completed_trade_count": trades,
    }


def test_strategy_a_is_default_primary_for_every_pair(tmp_path: Path) -> None:
    path = tmp_path / "assignments.json"
    assignments = ensure_pair_assignments(["AMDW / AMDL", "AVGW / AVGX"], path=path)
    assert assignments["AMDW / AMDL"]["primary_strategy"] == "STRATEGY_A"
    assert assignments["AVGW / AVGX"]["primary_strategy"] == "STRATEGY_A"
    assert assignments["AMDW / AMDL"]["shadow_strategies"] == ["STRATEGY_B"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["paper_trade_mode"] is True
    assert payload["broker_execution_enabled"] is False


def test_challenger_requires_all_approved_qualification_rules() -> None:
    qualified = challenger_qualification(
        _row("STRATEGY_A", total_return=4.0, drawdown=-8.0),
        _row("STRATEGY_B", total_return=7.0, drawdown=-7.0),
    )
    assert qualified["qualified"] is True
    assert all(qualified["checks"].values())

    worse_drawdown = challenger_qualification(
        _row("STRATEGY_A", total_return=4.0, drawdown=-8.0),
        _row("STRATEGY_B", total_return=9.0, drawdown=-12.0),
    )
    assert worse_drawdown["qualified"] is False
    assert worse_drawdown["checks"]["challenger_drawdown_no_worse"] is False

    insufficient = challenger_qualification(
        _row("STRATEGY_A", total_return=4.0, drawdown=-8.0),
        _row("STRATEGY_B", total_return=9.0, drawdown=-7.0, observations=20),
    )
    assert insufficient["qualified"] is False


def test_qualified_challenger_creates_one_pair_specific_review_request(tmp_path: Path) -> None:
    assignments = tmp_path / "assignments.json"
    requests = tmp_path / "requests.json"
    journal = tmp_path / "journal.jsonl"
    now = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
    ensure_pair_assignments(["AMDW / AMDL"], path=assignments, now=now)
    rows = [
        _row("STRATEGY_A", total_return=4.0, drawdown=-8.0),
        _row("STRATEGY_B", total_return=7.0, drawdown=-7.0),
    ]
    created = create_promotion_requests(
        rows,
        assignments_path=assignments,
        requests_path=requests,
        journal_path=journal,
        now=now,
    )
    assert len(created) == 1
    assert created[0]["status"] == PENDING
    assert created[0]["pair"] == "AMDW / AMDL"
    assert created[0]["current_primary_strategy"] == "STRATEGY_A"
    assert created[0]["proposed_primary_strategy"] == "STRATEGY_B"
    assert created[0]["veto_deadline"] == "2026-08-08T12:00:00Z"
    assert "STRATEGY_PROMOTION_REQUESTED" in journal.read_text(encoding="utf-8")

    repeated = create_promotion_requests(
        rows,
        assignments_path=assignments,
        requests_path=requests,
        journal_path=journal,
        now=now,
    )
    assert len(repeated) == 1
    assert journal.read_text(encoding="utf-8").count("STRATEGY_PROMOTION_REQUESTED") == 1


def test_no_request_when_challenger_fails_any_rule(tmp_path: Path) -> None:
    assignments = tmp_path / "assignments.json"
    requests = tmp_path / "requests.json"
    journal = tmp_path / "journal.jsonl"
    ensure_pair_assignments(["AMDW / AMDL"], path=assignments)
    created = create_promotion_requests(
        [
            _row("STRATEGY_A", total_return=4.0, drawdown=-8.0),
            _row("STRATEGY_B", total_return=9.0, drawdown=-12.0),
        ],
        assignments_path=assignments,
        requests_path=requests,
        journal_path=journal,
    )
    assert created == []
    assert not journal.exists()


def test_unvetoed_request_promotes_only_that_pair_after_deadline(tmp_path: Path) -> None:
    assignments = tmp_path / "assignments.json"
    requests = tmp_path / "requests.json"
    journal = tmp_path / "journal.jsonl"
    requested_at = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
    ensure_pair_assignments(["AMDW / AMDL", "AVGW / AVGX"], path=assignments, now=requested_at)
    create_promotion_requests(
        [
            _row("STRATEGY_A", total_return=4.0, drawdown=-8.0),
            _row("STRATEGY_B", total_return=7.0, drawdown=-7.0),
        ],
        assignments_path=assignments,
        requests_path=requests,
        journal_path=journal,
        now=requested_at,
    )
    assert activate_unvetoed_promotions(
        assignments_path=assignments,
        requests_path=requests,
        journal_path=journal,
        now=datetime(2026, 8, 8, 11, 59, tzinfo=timezone.utc),
    ) == []

    activated = activate_unvetoed_promotions(
        assignments_path=assignments,
        requests_path=requests,
        journal_path=journal,
        now=datetime(2026, 8, 8, 12, 1, tzinfo=timezone.utc),
    )
    assert len(activated) == 1
    current = load_assignments(assignments)
    assert current["AMDW / AMDL"]["primary_strategy"] == "STRATEGY_B"
    assert current["AVGW / AVGX"]["primary_strategy"] == "STRATEGY_A"
    assert load_requests(requests)[0]["status"] == PROMOTED
    assert activated[0]["capital_movement_enabled"] is False


def test_vetoed_request_is_never_activated(tmp_path: Path) -> None:
    assignments = tmp_path / "assignments.json"
    requests = tmp_path / "requests.json"
    journal = tmp_path / "journal.jsonl"
    ensure_pair_assignments(["AMDW / AMDL"], path=assignments)
    requests.write_text(
        json.dumps(
            {
                "requests": [
                    {
                        "request_id": "VETOED-1",
                        "pair": "AMDW / AMDL",
                        "current_primary_strategy": "STRATEGY_A",
                        "proposed_primary_strategy": "STRATEGY_B",
                        "status": "VETOED",
                        "veto_deadline": "2026-08-01T00:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    activated = activate_unvetoed_promotions(
        assignments_path=assignments,
        requests_path=requests,
        journal_path=journal,
        now=datetime(2026, 8, 20, tzinfo=timezone.utc),
    )
    assert activated == []
    assert load_assignments(assignments)["AMDW / AMDL"]["primary_strategy"] == "STRATEGY_A"
