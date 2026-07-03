"""Download and cache Yahoo Finance earnings dates for strategy underlyings."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

from pairs_config import EARNINGS_UNDERLYINGS


OUTPUT_DIR = Path("earnings_data")
SUMMARY_PATH = Path("earnings_download_summary.csv")
EARNINGS_LIMIT = 40


def download_symbol_earnings(symbol: str) -> pd.DataFrame:
    """Download and normalize one symbol's historical earnings dates."""
    raw = yf.Ticker(symbol).get_earnings_dates(limit=EARNINGS_LIMIT)
    if raw is None or raw.empty:
        raise ValueError("No earnings dates returned")

    dates = pd.to_datetime(raw.index, utc=True).tz_convert(None).normalize()
    output = pd.DataFrame({"earnings_date": dates})
    output = output.drop_duplicates().sort_values("earnings_date")
    return output.reset_index(drop=True)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_rows = []

    print("\nStarting Earnings Date Download...\n")

    for symbol in EARNINGS_UNDERLYINGS:
        print(f"Downloading {symbol} earnings dates...")
        output_path = OUTPUT_DIR / f"{symbol}.csv"
        try:
            earnings = download_symbol_earnings(symbol)
            earnings.to_csv(output_path, index=False)
            summary_rows.append(
                {
                    "symbol": symbol,
                    "status": "PASS",
                    "earnings_dates": len(earnings),
                    "first_date": earnings["earnings_date"].min().strftime(
                        "%Y-%m-%d"
                    ),
                    "last_date": earnings["earnings_date"].max().strftime(
                        "%Y-%m-%d"
                    ),
                    "csv_path": str(output_path),
                    "error": "",
                }
            )
        except Exception as exc:
            summary_rows.append(
                {
                    "symbol": symbol,
                    "status": "ERROR",
                    "earnings_dates": 0,
                    "first_date": "",
                    "last_date": "",
                    "csv_path": str(output_path),
                    "error": str(exc),
                }
            )

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(SUMMARY_PATH, index=False)
    passed = int((summary["status"] == "PASS").sum())
    failed = int((summary["status"] != "PASS").sum())

    print("\n====================================")
    print("EARNINGS DOWNLOAD COMPLETE")
    print("====================================")
    print(summary.to_string(index=False))
    print(f"\nPASS: {passed}")
    print(f"FAIL: {failed}")
    print(f"Summary saved to: {SUMMARY_PATH}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
