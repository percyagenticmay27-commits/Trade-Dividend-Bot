"""Validate the idempotent PAPER ONLY daily operational workflow."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from paper_trading_engine import PAPER_LABEL
from run_daily_paper_cycle import DailyCyclePaths, run_daily_cycle


class DailyCycleProvider:
    def __init__(self, end_date: str, falling_last_day: bool = False) -> None:
        self.end_date = end_date
        self.falling_last_day = falling_last_day

    def fetch(self, symbols: set[str]) -> dict[str, pd.DataFrame]:
        dates = pd.bdate_range(end=self.end_date, periods=80)
        frames = {}
        for offset, symbol in enumerate(sorted(symbols)):
            values = [100 + offset + index * 0.25 for index in range(len(dates))]
            if self.falling_last_day:
                values[-1] = values[-2] * 0.50
            close = pd.Series(values, index=dates)
            frames[symbol] = pd.DataFrame(
                {
                    "Open": close,
                    "High": close,
                    "Low": close,
                    "Close": close,
                    "Adj Close": close,
                    "Volume": 1000,
                    "Dividends": 0.0,
                },
                index=dates,
            )
        return frames


def csv_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        return len(list(csv.DictReader(handle)))


def main() -> int:
    root = Path.cwd()
    paths = DailyCyclePaths(
        state=root / "daily_cycle_test_state.json",
        log=root / "daily_cycle_test_log.csv",
        report=root / "daily_cycle_test_report.md",
        snapshot=root / "daily_cycle_test_snapshot.csv",
        change_summary=root / "daily_cycle_test_change.md",
        comparison=root / "daily_cycle_test_comparison.md",
        earnings_dir=root / "daily_cycle_test_missing_earnings",
        health_report=root / "daily_cycle_test_health.md",
        health_csv=root / "daily_cycle_test_health.csv",
        pair_health_csv=root / "daily_cycle_test_pairs.csv",
        readiness_report=root / "daily_cycle_test_readiness.md",
        readiness_csv=root / "daily_cycle_test_readiness.csv",
        signal_history=root / "daily_cycle_test_signals.csv",
        weekly_review=root / "daily_cycle_test_weekly.md",
    )
    artifacts = [
        paths.state,
        paths.log,
        paths.report,
        paths.snapshot,
        paths.change_summary,
        paths.comparison,
        paths.health_report,
        paths.health_csv,
        paths.pair_health_csv,
        paths.readiness_report,
        paths.readiness_csv,
        paths.signal_history,
        paths.weekly_review,
    ]
    for path in artifacts:
        path.unlink(missing_ok=True)

    try:
        first = run_daily_cycle(DailyCycleProvider("2026-06-18"), paths)
        assert paths.state.exists()
        assert paths.log.exists()
        assert paths.report.exists()
        assert paths.snapshot.exists()
        assert paths.change_summary.exists()
        assert paths.health_report.exists()
        assert paths.health_csv.exists()
        assert paths.pair_health_csv.exists()
        assert paths.readiness_report.exists()
        assert paths.readiness_csv.exists()
        assert paths.signal_history.exists()
        assert csv_rows(paths.signal_history) == 13
        assert first["snapshot"]["Portfolio_Value"] == 500.0
        assert abs(
            first["snapshot"]["ETF_Exposure"]
            + first["snapshot"]["SGOV_Exposure"]
            - 500.0
        ) < 1e-9
        first_log_rows = csv_rows(paths.log)
        assert first_log_rows == 20
        assert csv_rows(paths.snapshot) == 1
        assert csv_rows(paths.signal_history) == 13

        duplicate = run_daily_cycle(DailyCycleProvider("2026-06-18"), paths)
        assert duplicate["duplicate_date"] is True
        assert len(duplicate["new_log_rows"]) == 0
        assert csv_rows(paths.log) == first_log_rows
        assert csv_rows(paths.snapshot) == 1
        assert "Same Market Date Already Processed: Yes" in paths.change_summary.read_text(encoding="utf-8")

        next_day = run_daily_cycle(
            DailyCycleProvider("2026-06-19", falling_last_day=True),
            paths,
        )
        assert next_day["duplicate_date"] is False
        assert next_day["state"]["last_processed_date"] == "2026-06-19"
        assert csv_rows(paths.snapshot) == 2
        assert csv_rows(paths.signal_history) == 26
        assert csv_rows(paths.log) >= first_log_rows
        persisted = json.loads(paths.state.read_text(encoding="utf-8"))
        assert persisted["paper_only"] is True
        assert PAPER_LABEL in paths.report.read_text(encoding="utf-8")
        assert "Next Trading Day Recommendations" in paths.change_summary.read_text(encoding="utf-8")

        source = Path("run_daily_paper_cycle.py").read_text(encoding="utf-8").lower()
        assert "robinhood" not in source
        assert "submit_order" not in source
        assert "place_order" not in source
    finally:
        for path in artifacts:
            path.unlink(missing_ok=True)

    print("Daily PAPER ONLY cycle validation: PASS")
    print("State, reports, snapshot, and append-only log: PASS")
    print("Same-date idempotency: PASS")
    print("Portfolio reconciliation: PASS")
    print("Broker/order API dependency check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
