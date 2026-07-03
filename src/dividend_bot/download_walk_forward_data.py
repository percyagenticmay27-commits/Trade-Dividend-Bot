"""Download isolated local datasets for the Milestone 12 periods."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

from download_historical_data import normalize_history
from pairs_config import SYMBOLS


DATA_ROOT = Path("walk_forward_data")
SUMMARY_PATH = DATA_ROOT / "download_summary.csv"
PERIODS = {
    "Period A": ("2025-01-01", "2025-07-01"),
    "Period B": ("2025-07-01", "2026-01-01"),
    "Period C": ("2026-01-01", "2026-06-18"),
}


def main() -> int:
    rows = []
    for period, (start_date, exclusive_end) in PERIODS.items():
        output_dir = DATA_ROOT / period.lower().replace(" ", "_") / "daily"
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"\nDownloading {period}: {start_date} through {exclusive_end} (exclusive end)")

        for symbol in SYMBOLS:
            print(f"  {symbol}")
            try:
                history = yf.Ticker(symbol).history(
                    start=start_date,
                    end=exclusive_end,
                    auto_adjust=False,
                    actions=True,
                )
                history = normalize_history(history)
                history.to_csv(output_dir / f"{symbol}.csv")
                rows.append(
                    {
                        "Period": period,
                        "Symbol": symbol,
                        "Status": "PASS" if not history.empty else "FAIL",
                        "Rows": len(history),
                        "First_Date": history.index.min() if not history.empty else "",
                        "Last_Date": history.index.max() if not history.empty else "",
                        "Dividend_Count": int(
                            (history["Dividends"].fillna(0) != 0).sum()
                        ) if not history.empty else 0,
                        "Error": "" if not history.empty else "No rows downloaded",
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "Period": period,
                        "Symbol": symbol,
                        "Status": "ERROR",
                        "Rows": 0,
                        "First_Date": "",
                        "Last_Date": "",
                        "Dividend_Count": 0,
                        "Error": str(exc),
                    }
                )

    summary = pd.DataFrame(rows)
    summary.to_csv(SUMMARY_PATH, index=False)
    failures = summary[summary["Status"] != "PASS"]
    print(f"\nSummary saved to: {SUMMARY_PATH}")
    if not failures.empty:
        print("\nUnavailable period/symbol combinations:")
        print(failures.to_string(index=False))
    return 0 if failures.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
