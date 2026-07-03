"""Validate the configured ETF universe with yfinance price and dividend data."""

import csv

from pairs_config import END_DATE, START_DATE, SYMBOLS

REPORT_NAME = "universe_validation_report.csv"
FIELDNAMES = [
    "symbol",
    "status",
    "rows",
    "first_date",
    "last_date",
    "dividend_records",
    "error",
]


def load_yfinance():
    """Import yfinance at runtime so missing dependencies still produce a report."""
    try:
        import yfinance as yf
    except ModuleNotFoundError as exc:
        return None, str(exc)

    return yf, ""


def validate_symbol(symbol: str, yf) -> dict[str, object]:
    """Fetch one symbol and return a row for the validation report."""
    ticker = yf.Ticker(symbol)

    history = ticker.history(
        start=START_DATE,
        end=END_DATE,
        auto_adjust=False,
    )
    dividends = ticker.dividends

    has_price_data = len(history) > 0

    if has_price_data:
        first_date = history.index.min().strftime("%Y-%m-%d")
        last_date = history.index.max().strftime("%Y-%m-%d")
        rows = len(history)
    else:
        first_date = None
        last_date = None
        rows = 0

    return {
        "symbol": symbol,
        "status": "PASS" if has_price_data else "FAIL",
        "rows": rows,
        "first_date": first_date,
        "last_date": last_date,
        "dividend_records": len(dividends),
        "error": "",
    }


def write_report(results: list[dict[str, object]]) -> None:
    """Write validation results to CSV."""
    with open(REPORT_NAME, "w", newline="", encoding="utf-8") as report_file:
        writer = csv.DictWriter(report_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(results)


def print_results(results: list[dict[str, object]]) -> None:
    """Print a compact table without requiring pandas."""
    for row in results:
        print(
            "{symbol:<6} {status:<5} rows={rows:<4} first={first_date} "
            "last={last_date} dividends={dividend_records} error={error}".format(**row)
        )


def validate_universe() -> list[dict[str, object]]:
    """Validate all configured symbols and return the report dataframe."""
    results = []

    print("\nStarting Universe Validation...\n")

    yf, dependency_error = load_yfinance()
    if yf is None:
        for symbol in SYMBOLS:
            results.append(
                {
                    "symbol": symbol,
                    "status": "ERROR",
                    "rows": 0,
                    "first_date": None,
                    "last_date": None,
                    "dividend_records": 0,
                    "error": dependency_error,
                }
            )
        return results

    for symbol in SYMBOLS:
        print(f"Checking {symbol}...")

        try:
            results.append(validate_symbol(symbol, yf))
        except Exception as exc:
            results.append(
                {
                    "symbol": symbol,
                    "status": "ERROR",
                    "rows": 0,
                    "first_date": None,
                    "last_date": None,
                    "dividend_records": 0,
                    "error": str(exc),
                }
            )

    return results


def main() -> int:
    results = validate_universe()
    write_report(results)

    print("\n====================================")
    print("VALIDATION COMPLETE")
    print("====================================")
    print_results(results)
    print(f"\nReport saved to: {REPORT_NAME}")

    passed = sum(1 for row in results if row["status"] == "PASS")
    failed = sum(1 for row in results if row["status"] != "PASS")

    print("\n====================================")
    print("SUMMARY")
    print("====================================")
    print(f"PASS: {passed}")
    print(f"FAIL: {failed}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
