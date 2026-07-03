"""Download daily OHLCV and dividend data for the configured symbol universe."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

from pairs_config import END_DATE, START_DATE, SYMBOLS


DATA_DIR = Path("historical_data") / "daily"
SUMMARY_REPORT = Path("downloader_summary_report.csv")


def normalize_history(history: pd.DataFrame) -> pd.DataFrame:
    """Return a clean daily OHLCV/dividend dataframe ready for CSV output."""
    if history.empty:
        return history

    output = history.copy()
    output.index = pd.to_datetime(output.index).strftime("%Y-%m-%d")
    output.index.name = "date"

    expected_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Adj Close",
        "Volume",
        "Dividends",
    ]

    for column in expected_columns:
        if column not in output.columns:
            output[column] = 0

    return output[expected_columns]


def download_symbol(symbol: str) -> dict[str, object]:
    """Download one symbol, save its CSV, and return one summary row."""
    ticker = yf.Ticker(symbol)
    history = ticker.history(
        start=START_DATE,
        end=END_DATE,
        auto_adjust=False,
        actions=True,
    )
    history = normalize_history(history)

    symbol_path = DATA_DIR / f"{symbol}.csv"
    history.to_csv(symbol_path)

    if history.empty:
        return {
            "symbol": symbol,
            "status": "FAIL",
            "rows_downloaded": 0,
            "first_date": "",
            "last_date": "",
            "dividend_count": 0,
            "csv_path": str(symbol_path),
            "error": "No rows downloaded",
        }

    dividend_count = int((history["Dividends"].fillna(0) != 0).sum())

    return {
        "symbol": symbol,
        "status": "PASS",
        "rows_downloaded": len(history),
        "first_date": history.index.min(),
        "last_date": history.index.max(),
        "dividend_count": dividend_count,
        "csv_path": str(symbol_path),
        "error": "",
    }


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    summary_rows = []

    print("\nStarting Historical Data Download...\n")

    for symbol in SYMBOLS:
        print(f"Downloading {symbol}...")
        try:
            summary_rows.append(download_symbol(symbol))
        except Exception as exc:
            summary_rows.append(
                {
                    "symbol": symbol,
                    "status": "ERROR",
                    "rows_downloaded": 0,
                    "first_date": "",
                    "last_date": "",
                    "dividend_count": 0,
                    "csv_path": str(DATA_DIR / f"{symbol}.csv"),
                    "error": str(exc),
                }
            )

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(SUMMARY_REPORT, index=False)

    passed = int((summary["status"] == "PASS").sum())
    failed = int((summary["status"] != "PASS").sum())

    print("\n====================================")
    print("DOWNLOAD COMPLETE")
    print("====================================")
    print(summary)
    print(f"\nSummary report saved to: {SUMMARY_REPORT}")
    print(f"Daily symbol CSVs saved to: {DATA_DIR}")

    print("\n====================================")
    print("SUMMARY")
    print("====================================")
    print(f"PASS: {passed}")
    print(f"FAIL: {failed}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
