from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.dividend_bot.daily_dividend_csv_exports import (
    EXECUTIVE_SUMMARY_FILE,
    PORTFOLIO_FILE,
    WATCHLIST_FILE,
    generate_daily_dividend_csv_exports,
)


def sample_state(as_of_date: str) -> dict:
    return {
        "as_of_date": as_of_date,
        "pairs": {
            "AMDW / AMDL": {
                "a_shares": 1.5,
                "b_shares": 2.0,
                "last_prices": {"A": 25.0, "B": 10.0},
                "last_signal": {"A": "BUY", "B": "SELL"},
                "a_in_sgov": False,
                "b_in_sgov": False,
                "a_earnings_lock": False,
                "b_earnings_lock": True,
                "sgov_balance": 17.5,
                "total_dividends_received": 2.25,
            }
        },
    }


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_generates_three_csv_files_from_fresh_state(tmp_path: Path):
    (tmp_path / "paper_portfolio_state.json").write_text(
        json.dumps(sample_state("2026-08-05")), encoding="utf-8"
    )
    paths = generate_daily_dividend_csv_exports(
        root_dir=tmp_path,
        now=datetime(2026, 8, 5, 20, 0, tzinfo=timezone.utc),
    )
    assert [path.name for path in paths] == [
        EXECUTIVE_SUMMARY_FILE,
        PORTFOLIO_FILE,
        WATCHLIST_FILE,
    ]
    assert all(path.is_file() for path in paths)


def test_executive_summary_is_fresh_and_balanced(tmp_path: Path):
    (tmp_path / "paper_portfolio_state.json").write_text(
        json.dumps(sample_state("2026-08-05")), encoding="utf-8"
    )
    executive, _, _ = generate_daily_dividend_csv_exports(
        root_dir=tmp_path,
        now=datetime(2026, 8, 5, 20, 0, tzinfo=timezone.utc),
    )
    row = read_rows(executive)[0]
    assert row["as_of_date"] == "2026-08-05"
    assert row["data_stale"] == "False"
    assert float(row["portfolio_value"]) == pytest.approx(75.0)
    assert float(row["etf_exposure"]) == pytest.approx(57.5)
    assert float(row["sgov_exposure"]) == pytest.approx(17.5)


def test_portfolio_contains_current_prices_and_market_values(tmp_path: Path):
    (tmp_path / "paper_portfolio_state.json").write_text(
        json.dumps(sample_state("2026-08-05")), encoding="utf-8"
    )
    _, portfolio, _ = generate_daily_dividend_csv_exports(
        root_dir=tmp_path,
        now=datetime(2026, 8, 5, 20, 0, tzinfo=timezone.utc),
    )
    row = read_rows(portfolio)[0]
    assert float(row["a_current_price"]) == 25.0
    assert float(row["a_market_value"]) == 37.5
    assert float(row["b_current_price"]) == 10.0
    assert float(row["b_market_value"]) == 20.0


def test_watchlist_derives_actions_without_trading(tmp_path: Path):
    (tmp_path / "paper_portfolio_state.json").write_text(
        json.dumps(sample_state("2026-08-05")), encoding="utf-8"
    )
    _, _, watchlist = generate_daily_dividend_csv_exports(
        root_dir=tmp_path,
        now=datetime(2026, 8, 5, 20, 0, tzinfo=timezone.utc),
    )
    rows = read_rows(watchlist)
    assert [row["watch_action"] for row in rows] == ["HOLD_MONITOR", "WAIT_POST_EARNINGS_BUY"]


def test_stale_state_is_rejected(tmp_path: Path):
    (tmp_path / "paper_portfolio_state.json").write_text(
        json.dumps(sample_state("2026-07-01")), encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="stale"):
        generate_daily_dividend_csv_exports(
            root_dir=tmp_path,
            now=datetime(2026, 8, 5, 20, 0, tzinfo=timezone.utc),
            max_state_age_days=5,
        )


def test_missing_state_is_rejected(tmp_path: Path):
    with pytest.raises(RuntimeError, match="missing"):
        generate_daily_dividend_csv_exports(root_dir=tmp_path)


def test_safety_constants_are_locked():
    from src.dividend_bot import daily_dividend_csv_exports as module

    assert module.PAPER_TRADE_MODE is True
    assert module.LIVE_TRADING_ENABLED is False
    assert module.BROKER_EXECUTION_ENABLED is False
    assert module.ORDER_PLACEMENT_ENABLED is False
    assert module.CAPITAL_MOVEMENT_ENABLED is False
