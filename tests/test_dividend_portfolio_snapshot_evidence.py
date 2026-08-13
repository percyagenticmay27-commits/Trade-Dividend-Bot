from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.dividend_portfolio_snapshot_evidence import (
    build_portfolio_snapshot_evidence,
    write_portfolio_snapshot_evidence,
)


def test_snapshot_preserves_current_holdings_and_reserve() -> None:
    report = build_portfolio_snapshot_evidence(
        {
            "portfolio_value": 70.0,
            "active_position_count": 2,
            "reserve_position_count": 1,
            "holdings": [
                {"symbol": "AVGW", "market_value": 20.0, "source": "paper_state.json"},
                {"symbol": "AVGX", "market_value": 20.0, "source": "paper_state.json"},
                {"symbol": "SGOV", "market_value": 30.0, "source": "paper_state.json"},
            ],
        },
        generated_at_utc="2026-08-12T00:00:00Z",
    )

    assert report["evidence_status"] == "AVAILABLE"
    assert report["record_count"] == 3
    assert report["portfolio_value"] == 70.0
    assert {item["symbol"] for item in report["records"]} == {"AVGW", "AVGX", "SGOV"}
    assert report["source"] == "paper_state.json"


def test_empty_snapshot_is_authoritative_empty_not_missing() -> None:
    report = build_portfolio_snapshot_evidence(
        {"holdings": [], "portfolio_value": None},
        generated_at_utc="2026-08-12T00:00:00Z",
    )

    assert report["evidence_status"] == "AVAILABLE_EMPTY"
    assert report["record_count"] == 0
    assert report["records"] == []
    assert report["empty_state_reason"]


def test_writer_derives_snapshot_without_mutating_paper_state(tmp_path: Path) -> None:
    state = tmp_path / "paper_state.json"
    state.write_text(
        json.dumps(
            {
                "pairs": {
                    "AVGW / AVGX": {
                        "a_shares": 2,
                        "b_shares": 1,
                        "last_prices": {"A": 10, "B": 20},
                        "sgov_balance": 30,
                        "total_dividends_received": 0,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    before = state.read_bytes()

    path = write_portfolio_snapshot_evidence(tmp_path)

    assert state.read_bytes() == before
    assert path == tmp_path / "results/portfolio_snapshot.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["record_count"] == 3
    assert report["portfolio_value"] == 70.0
    assert not list((tmp_path / "results").glob("*.tmp"))
