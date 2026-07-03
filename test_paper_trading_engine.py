"""Validation tests for the PAPER ONLY daily trading simulator."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from paper_portfolio_config import PAPER_PAIRS, TOTAL_PAPER_CAPITAL
from paper_trading_engine import PAPER_LABEL, PaperTradingEngine


class FakeMarketDataProvider:
    def __init__(self, end_date: str, falling_last_day: bool = False) -> None:
        self.end_date = end_date
        self.falling_last_day = falling_last_day
        self.calls = 0

    def fetch(self, symbols: set[str]) -> dict[str, pd.DataFrame]:
        self.calls += 1
        dates = pd.bdate_range(end=self.end_date, periods=80)
        frames = {}
        for offset, symbol in enumerate(sorted(symbols)):
            close = pd.Series(
                [100.0 + offset + index * 0.25 for index in range(len(dates))],
                index=dates,
            )
            if self.falling_last_day:
                close.iloc[-1] = close.iloc[-2] * 0.50
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


def validate_first_run(root: Path) -> tuple[PaperTradingEngine, dict, int]:
    provider = FakeMarketDataProvider("2026-06-18")
    engine = PaperTradingEngine(
        provider=provider,
        state_path=root / ".paper_test_state.json",
        log_path=root / ".paper_test_log.csv",
        report_path=root / ".paper_test_report.md",
        comparison_path=root / ".paper_test_comparison.md",
        earnings_dir=root / "earnings_data",
    )
    state = engine.run()

    assert provider.calls == 1
    assert engine.state_path.exists()
    assert engine.log_path.exists()
    assert engine.report_path.exists()
    assert state["paper_only"] is True
    assert state["starting_capital"] == TOTAL_PAPER_CAPITAL == 500.0
    assert len(state["pairs"]) == 10
    assert abs(sum(pair["capital_bucket"] for pair in state["pairs"].values()) - 500.0) < 1e-9
    for pair, config in PAPER_PAIRS.items():
        assert state["pairs"][pair]["capital_bucket"] == config["allocation"]
        assert state["pairs"][pair]["architecture"] == config["architecture"]

    with engine.log_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 20
    assert all(PAPER_LABEL in row["Reason"] for row in rows)
    assert PAPER_LABEL in engine.report_path.read_text(encoding="utf-8")
    assert "No real trades were submitted" in engine.report_path.read_text(encoding="utf-8")
    return engine, state, len(rows)


def validate_append_and_idempotency(root: Path, original_log_rows: int) -> None:
    same_day = PaperTradingEngine(
        provider=FakeMarketDataProvider("2026-06-18"),
        state_path=root / ".paper_test_state.json",
        log_path=root / ".paper_test_log.csv",
        report_path=root / ".paper_test_report.md",
        comparison_path=root / ".paper_test_comparison.md",
        earnings_dir=root / "earnings_data",
    )
    same_day.run()
    with same_day.log_path.open(newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == original_log_rows

    next_day = PaperTradingEngine(
        provider=FakeMarketDataProvider("2026-06-19", falling_last_day=True),
        state_path=root / ".paper_test_state.json",
        log_path=root / ".paper_test_log.csv",
        report_path=root / ".paper_test_report.md",
        comparison_path=root / ".paper_test_comparison.md",
        earnings_dir=root / "earnings_data",
    )
    state = next_day.run()
    with next_day.log_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) > original_log_rows
    assert any(row["Action"] == "PAPER_SELL_TO_SGOV" for row in rows)
    assert state["last_processed_date"] == "2026-06-19"
    assert json.loads(next_day.state_path.read_text(encoding="utf-8"))["paper_only"] is True


def validate_no_broker_dependency() -> None:
    source = Path("paper_trading_engine.py").read_text(encoding="utf-8").lower()
    assert "robinhood" not in source
    assert "place_order" not in source
    assert "submit_order" not in source


def main() -> int:
    root = Path.cwd()
    test_files = {
        root / ".paper_test_state.json",
        root / ".paper_test_log.csv",
        root / ".paper_test_report.md",
        root / ".paper_test_comparison.md",
    }
    for path in test_files:
        path.unlink(missing_ok=True)
    try:
        # Keep test artifacts as direct workspace files; sandboxed temp directories
        # on Windows can deny their own child-file writes.
        _, _, log_rows = validate_first_run(root)
        validate_append_and_idempotency(root, log_rows)
        validate_no_broker_dependency()
    finally:
        for path in test_files:
            path.unlink(missing_ok=True)
    print("PAPER ONLY engine validation: PASS")
    print("Starting capital: $500.00")
    print("Approved allocations and architecture: PASS")
    print("State, append-only log, report, and same-day idempotency: PASS")
    print("Broker/order API dependency check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
