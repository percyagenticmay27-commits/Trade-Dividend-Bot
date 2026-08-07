from __future__ import annotations

import csv
from pathlib import Path

from market_data_integration_engine import discover_market_symbols, refresh_market_data_snapshot
from src.dividend_bot.market_momentum_evidence import build_market_momentum_report


class FakeService:
    def get_quote(self, symbol: str, force_refresh: bool = False):
        return {
            "symbol": symbol,
            "price": 130.0,
            "previous_close": 129.0,
            "return_on_equity": 0.22,
            "profit_margin": 0.18,
            "operating_margin": 0.20,
            "free_cash_flow": 1000000,
            "revenue_growth": 0.12,
            "earnings_growth": 0.15,
            "earnings_quarterly_growth": 0.10,
            "payout_ratio": 0.55,
            "debt_to_equity": 45.0,
            "current_ratio": 1.8,
            "trailing_pe": 18.0,
            "forward_pe": 16.0,
            "price_to_book": 2.5,
            "fifty_two_week_high": 135.0,
            "fifty_two_week_low": 85.0,
            "data_source": "TEST",
            "is_stale": False,
        }

    def get_history(self, symbol: str, period: str = "1y", interval: str = "1d", force_refresh: bool = False):
        rows = []
        for i in range(230):
            rows.append({
                "date": f"2026-01-{(i % 28) + 1:02d}",
                "close": 80.0 + i * 0.22,
                "volume": 1000.0 + i * 5.0,
            })
        return {"symbol": symbol, "rows": rows, "data_source": "TEST", "is_stale": False}

    def get_dividends(self, symbol: str, period: str = "5y", force_refresh: bool = False):
        return {
            "symbol": symbol,
            "payments": [
                {"date": "2025-03-01", "amount": 1.00},
                {"date": "2025-06-01", "amount": 1.00},
                {"date": "2025-09-01", "amount": 1.00},
                {"date": "2025-12-01", "amount": 1.00},
                {"date": "2026-03-01", "amount": 1.10},
                {"date": "2026-06-01", "amount": 1.10},
                {"date": "2026-09-01", "amount": 1.10},
                {"date": "2026-12-01", "amount": 1.10},
            ],
            "data_source": "TEST",
            "is_stale": False,
        }


def test_snapshot_normalizes_rows_payments_and_derived_dividend_growth() -> None:
    report = refresh_market_data_snapshot(["ABC"], FakeService())
    assert report["status"] == "COMPLETE"
    row = report["records"][0]
    assert row["history_row_count"] == 230
    assert row["dividend_record_count"] == 8
    assert row["dividend_total"] == 8.4
    assert row["derived_dividend_growth"] == 0.10
    assert row["quote"]["dividend_growth"] == 0.10


def test_csv_paper_trade_history_expands_market_symbol_universe(tmp_path: Path) -> None:
    path = tmp_path / "paper_trade_log.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Date", "Ticker"])
        writer.writeheader()
        writer.writerow({"Date": "2026-08-06", "Ticker": "AVGW"})
        writer.writerow({"Date": "2026-08-06", "Ticker": "NVDW"})
    assert discover_market_symbols(tmp_path, symbol_files=["paper_trade_log.csv"]) == ["AVGW", "NVDW"]


def test_real_momentum_uses_history_instead_of_deterministic_fallback() -> None:
    snapshot = refresh_market_data_snapshot(["ABC"], FakeService())
    report = build_market_momentum_report(snapshot)
    assert report["entry_count"] == 1
    row = report["entries"][0]
    assert row["symbol"] == "ABC"
    assert row["momentum_score"] > 0
    assert row["history_row_count"] == 230
    assert row["source"] == "SHARED_MARKET_DATA_SNAPSHOT"
    assert row["trend_direction"] == "UP"
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["order_placement_enabled"] is False
    assert report["capital_movement_enabled"] is False
    assert report["automatic_activation_allowed"] is False
