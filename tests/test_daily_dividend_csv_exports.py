from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.dividend_bot.daily_dividend_csv_exports import (
    EXECUTIVE_SUMMARY_FILE,
    PERFORMANCE_FILE,
    PORTFOLIO_FILE,
    WATCHLIST_FILE,
    generate_daily_dividend_csv_exports,
)
from src.dividend_bot.daily_markdown_report_csv import REPORT_EXPORTS


def sample_state(as_of_date: str, *, generated_at: str | None = None, price: float = 25.0) -> dict:
    state = {
        "as_of_date": as_of_date,
        "pairs": {
            "AMDW / AMDL": {
                "a_shares": 1.5,
                "b_shares": 2.0,
                "last_prices": {"A": price, "B": 10.0},
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
    if generated_at is not None:
        state["generated_at"] = generated_at
    return state


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_required_reports(tmp_path: Path) -> None:
    samples = {
        "daily_paper_report.md": "# Daily Paper Report\n- Status: COMPLETE\n- Portfolio Value: 75.00\n",
        "daily_change_summary.md": "# Daily Change Summary\n- Change: +5.00\n",
        "strategy_health_report.md": "# Strategy Health\n- Health: GOOD\n",
        "live_readiness_report.md": "# Live Readiness\n- Status: PAPER_ONLY\n",
    }
    for name, content in samples.items():
        (tmp_path / name).write_text(content, encoding="utf-8")


def write_state(tmp_path: Path, as_of: str = "2026-08-05") -> None:
    (tmp_path / "paper_portfolio_state.json").write_text(
        json.dumps(sample_state(as_of)), encoding="utf-8"
    )
    write_required_reports(tmp_path)


def generate(tmp_path: Path, *, as_of_now: datetime | None = None) -> list[Path]:
    return generate_daily_dividend_csv_exports(
        root_dir=tmp_path,
        now=as_of_now or datetime(2026, 8, 5, 20, 0, tzinfo=timezone.utc),
    )


def test_generates_eight_csv_files_from_fresh_state(tmp_path: Path):
    write_state(tmp_path)
    paths = generate(tmp_path)
    expected = [
        EXECUTIVE_SUMMARY_FILE,
        PORTFOLIO_FILE,
        WATCHLIST_FILE,
        PERFORMANCE_FILE,
        *[output for _, output in REPORT_EXPORTS],
    ]
    assert [path.name for path in paths] == expected
    assert all(path.is_file() for path in paths)


def test_markdown_reports_are_structured_csvs(tmp_path: Path):
    write_state(tmp_path)
    paths = generate(tmp_path)
    daily_report = next(path for path in paths if path.name == "daily_paper_report.csv")
    rows = read_rows(daily_report)
    assert rows[0]["row_type"] == "heading"
    assert rows[0]["section"] == "Daily Paper Report"
    status = next(row for row in rows if row["label"] == "Status")
    assert status["value"] == "COMPLETE"
    assert status["paper_trade_mode"] == "True"


def test_missing_required_markdown_report_blocks_package(tmp_path: Path):
    write_state(tmp_path)
    (tmp_path / "live_readiness_report.md").unlink()
    with pytest.raises(RuntimeError, match="live_readiness_report.md"):
        generate(tmp_path)


def test_executive_summary_is_fresh_and_balanced(tmp_path: Path):
    write_state(tmp_path)
    row = read_rows(generate(tmp_path)[0])[0]
    assert row["as_of_date"] == "2026-08-05"
    assert row["data_stale"] == "False"
    assert float(row["portfolio_value"]) == pytest.approx(75.0)
    assert float(row["etf_exposure"]) == pytest.approx(57.5)
    assert float(row["sgov_exposure"]) == pytest.approx(17.5)


def test_portfolio_contains_current_prices_and_market_values(tmp_path: Path):
    write_state(tmp_path)
    row = read_rows(generate(tmp_path)[1])[0]
    assert float(row["a_current_price"]) == 25.0
    assert float(row["a_market_value"]) == 37.5
    assert float(row["b_current_price"]) == 10.0
    assert float(row["b_market_value"]) == 20.0


def test_watchlist_derives_actions_without_trading(tmp_path: Path):
    write_state(tmp_path)
    assert [row["watch_action"] for row in read_rows(generate(tmp_path)[2])] == [
        "HOLD_MONITOR",
        "WAIT_POST_EARNINGS_BUY",
    ]


def test_performance_uses_prior_and_inception_snapshots(tmp_path: Path):
    write_state(tmp_path)
    (tmp_path / "portfolio_snapshot.csv").write_text(
        "Date,Portfolio_Value,ETF_Exposure,SGOV_Exposure,Cash_Flow,Dividends_Received,Open_Buckets,SGOV_Buckets\n"
        "2026-08-01,60,40,20,0,0,1,0\n"
        "2026-08-04,70,52,18,0,0,1,0\n",
        encoding="utf-8",
    )
    row = read_rows(generate(tmp_path)[3])[0]
    assert row["strategy"] == "DIVIDEND"
    assert row["data_stale"] == "False"
    assert float(row["current_portfolio_value"]) == pytest.approx(75.0)
    assert row["prior_snapshot_date"] == "2026-08-04"
    assert float(row["daily_value_change"]) == pytest.approx(5.0)
    assert float(row["daily_return_percent"]) == pytest.approx(7.14285714)
    assert row["inception_snapshot_date"] == "2026-08-01"
    assert float(row["total_value_change"]) == pytest.approx(15.0)
    assert float(row["total_return_percent"]) == pytest.approx(25.0)
    assert float(row["total_dividends_received"]) == pytest.approx(2.25)


def test_performance_is_safe_without_snapshot_history(tmp_path: Path):
    write_state(tmp_path)
    row = read_rows(generate(tmp_path)[3])[0]
    assert row["snapshot_history_available"] == "False"
    assert float(row["daily_value_change"]) == 0.0
    assert float(row["total_return_percent"]) == 0.0


def test_stale_state_is_rejected(tmp_path: Path):
    write_state(tmp_path, "2026-07-01")
    with pytest.raises(RuntimeError, match="stale"):
        generate_daily_dividend_csv_exports(
            root_dir=tmp_path,
            now=datetime(2026, 8, 5, 20, 0, tzinfo=timezone.utc),
            max_state_age_days=5,
        )


def test_missing_state_is_rejected(tmp_path: Path):
    write_required_reports(tmp_path)
    with pytest.raises(RuntimeError, match="missing"):
        generate_daily_dividend_csv_exports(root_dir=tmp_path)


def test_discovers_current_production_paper_state(tmp_path: Path):
    write_required_reports(tmp_path)
    (tmp_path / "paper_state.json").write_text(
        json.dumps(sample_state("2026-08-05", generated_at="2026-08-05T20:00:00+00:00")),
        encoding="utf-8",
    )
    row = read_rows(generate(tmp_path, as_of_now=datetime(2026, 8, 5, 21, 0, tzinfo=timezone.utc))[0])[0]
    assert row["state_source"].endswith("paper_state.json")


def test_discovers_reports_copy_when_root_state_is_absent(tmp_path: Path):
    write_required_reports(tmp_path)
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "paper_state.json").write_text(
        json.dumps(sample_state("2026-08-05", generated_at="2026-08-05T20:00:00+00:00")),
        encoding="utf-8",
    )
    assert read_rows(generate(tmp_path, as_of_now=datetime(2026, 8, 5, 21, 0, tzinfo=timezone.utc))[0])[0][
        "state_source"
    ].endswith("reports/paper_state.json")


def test_selects_newest_valid_candidate_not_filename_priority(tmp_path: Path):
    write_required_reports(tmp_path)
    (tmp_path / "paper_portfolio_state.json").write_text(
        json.dumps(sample_state("2026-08-05", generated_at="2026-08-05T18:00:00+00:00", price=20.0)),
        encoding="utf-8",
    )
    (tmp_path / "paper_state.json").write_text(
        json.dumps(sample_state("2026-08-05", generated_at="2026-08-05T20:00:00+00:00", price=30.0)),
        encoding="utf-8",
    )
    assert float(read_rows(generate(tmp_path, as_of_now=datetime(2026, 8, 5, 21, 0, tzinfo=timezone.utc))[1])[0][
        "a_current_price"
    ]) == 30.0


def test_rejects_stale_candidate_and_uses_fresh_candidate(tmp_path: Path):
    write_required_reports(tmp_path)
    (tmp_path / "paper_portfolio_state.json").write_text(
        json.dumps(sample_state("2026-07-01", generated_at="2026-08-05T22:00:00+00:00", price=99.0)),
        encoding="utf-8",
    )
    (tmp_path / "paper_state.json").write_text(
        json.dumps(sample_state("2026-08-05", generated_at="2026-08-05T20:00:00+00:00", price=25.0)),
        encoding="utf-8",
    )
    paths = generate_daily_dividend_csv_exports(
        root_dir=tmp_path,
        now=datetime(2026, 8, 5, 21, 0, tzinfo=timezone.utc),
        max_state_age_days=5,
    )
    assert float(read_rows(paths[1])[0]["a_current_price"]) == 25.0


def test_safety_constants_are_locked():
    from src.dividend_bot import daily_dividend_csv_exports as module
    from src.dividend_bot import daily_markdown_report_csv as markdown_module

    assert module.PAPER_TRADE_MODE is True
    assert module.LIVE_TRADING_ENABLED is False
    assert module.BROKER_EXECUTION_ENABLED is False
    assert module.ORDER_PLACEMENT_ENABLED is False
    assert module.CAPITAL_MOVEMENT_ENABLED is False
    assert markdown_module.PAPER_TRADE_MODE is True
    assert markdown_module.LIVE_TRADING_ENABLED is False
    assert markdown_module.BROKER_EXECUTION_ENABLED is False
