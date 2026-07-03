"""Run the focused COIW/CONL A-only SGOV re-entry experiment."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pandas as pd

from dividend_engine import DividendEngine
from earnings_backtest import RESULT_COLUMNS, run_standard_pair_with_earnings
from generate_performance_report import markdown_table
from portfolio_engine import PairPortfolio, ReentryMode


EARNINGS_RESULTS_PATH = Path("earnings_backtest_results.csv")
OUTPUT_PATH = Path("coiw_reentry_test.csv")
SUMMARY_PATH = Path("coiw_reentry_summary.md")
PAIR = "COIW / CONL"

COMPARISON_ORDER = [
    ("Underlying", ReentryMode.PROPORTIONAL.value),
    ("Underlying", ReentryMode.FIXED_70_30.value),
    ("ETF", ReentryMode.PROPORTIONAL.value),
    ("ETF", ReentryMode.FIXED_70_30.value),
]


def validate_engine_allocation() -> None:
    """Prove principal goes only to A while dividends remain 50/50."""
    portfolio = PairPortfolio(
        "COIW",
        "CONL",
        reentry_mode=ReentryMode.A_ONLY,
    )
    portfolio.initialize("10", "5")
    dividends = DividendEngine()
    eligible_a_shares = portfolio.a_shares

    portfolio.sell_to_sgov("12", "4")
    dividends.apply_pair_dividend(
        portfolio,
        eligible_a_shares=eligible_a_shares,
        dividend_per_share="1",
        a_price="12",
        b_price="4",
    )
    dividends.buy_pair_from_sgov(portfolio, "11", "6")

    a_value = portfolio.a_shares * Decimal("11")
    b_value = portfolio.b_shares * Decimal("6")
    assert a_value == Decimal("55.75")
    assert b_value == Decimal("1.75")
    assert a_value + b_value == Decimal("57.50")
    assert dividends.totals.reinvested_a == Decimal("1.75")
    assert dividends.totals.reinvested_b == Decimal("1.75")


def load_comparison_rows() -> list[dict[str, object]]:
    """Load the four approved COIW comparison rows in requested order."""
    if not EARNINGS_RESULTS_PATH.exists():
        raise FileNotFoundError(
            f"Required earnings results not found: {EARNINGS_RESULTS_PATH}"
        )

    earnings = pd.read_csv(EARNINGS_RESULTS_PATH)
    rows = []
    for model, reentry_mode in COMPARISON_ORDER:
        matching = earnings[
            (earnings["Pair"] == PAIR)
            & (earnings["Model"] == model)
            & (earnings["Reentry_Mode"] == reentry_mode)
        ]
        if len(matching) != 1:
            raise AssertionError(
                f"Expected one comparison row for {model}/{reentry_mode}"
            )
        rows.append(matching.iloc[0].to_dict())
    return rows


def build_results() -> pd.DataFrame:
    """Build four existing rows plus two A-only experiment rows."""
    rows = load_comparison_rows()
    rows.append(
        run_standard_pair_with_earnings(
            "COIW",
            "CONL",
            "Underlying",
            ReentryMode.A_ONLY,
        )
    )
    rows.append(
        run_standard_pair_with_earnings(
            "COIW",
            "CONL",
            "ETF",
            ReentryMode.A_ONLY,
        )
    )
    return pd.DataFrame(rows)[RESULT_COLUMNS]


def validate_results(results: pd.DataFrame) -> None:
    """Validate coverage, dividend behavior, and accounting identities."""
    assert len(results) == 6
    assert not results.isna().any().any()
    assert results["Pair"].eq(PAIR).all()
    assert results["Initial_Capital"].eq(50.0).all()

    a_only = results[results["Reentry_Mode"] == ReentryMode.A_ONLY.value]
    assert len(a_only) == 2
    assert a_only["Dividends_Reinvested_A"].gt(0).all()
    assert a_only["Dividends_Reinvested_B"].gt(0).all()

    assert (
        results["Final_Value"]
        - results["Initial_Capital"]
        - results["Profit_Loss"]
    ).abs().lt(0.000002).all()
    assert (
        results["Profit_Loss"] / results["Initial_Capital"] * 100
        - results["Return_Pct"]
    ).abs().lt(0.000002).all()
    assert results["Trades"].eq(
        results["SGOV_Entries"] + results["SGOV_Exits"]
    ).all()


def build_summary(results: pd.DataFrame) -> str:
    """Build the six-way COIW re-entry comparison."""
    comparison = results[
        [
            "Pair",
            "Model",
            "Reentry_Mode",
            "Final_Value",
            "Profit_Loss",
            "Return_Pct",
            "Max_Drawdown",
            "Dividends_Received",
            "Dividends_Reinvested_A",
            "Dividends_Reinvested_B",
        ]
    ].copy()
    best = comparison.loc[comparison["Final_Value"].idxmax()]
    underlying = comparison[comparison["Model"] == "Underlying"].set_index(
        "Reentry_Mode"
    )
    etf = comparison[comparison["Model"] == "ETF"].set_index("Reentry_Mode")
    underlying_a_only = underlying.loc[ReentryMode.A_ONLY.value, "Final_Value"]
    etf_a_only = etf.loc[ReentryMode.A_ONLY.value, "Final_Value"]

    lines = [
        "# COIW / CONL A-Only Re-entry Test",
        "",
        "## Result",
        "",
        f"- Best Model: {best['Model']}",
        f"- Best Re-entry Mode: {best['Reentry_Mode']}",
        f"- Best Final Value: ${best['Final_Value']:.6f}",
        f"- Best Return: {best['Return_Pct']:.6f}%",
        (
            "- Underlying A-only vs proportional: "
            f"${underlying_a_only - underlying.loc[ReentryMode.PROPORTIONAL.value, 'Final_Value']:+.6f}"
        ),
        (
            "- Underlying A-only vs fixed 70/30: "
            f"${underlying_a_only - underlying.loc[ReentryMode.FIXED_70_30.value, 'Final_Value']:+.6f}"
        ),
        (
            "- ETF A-only vs proportional: "
            f"${etf_a_only - etf.loc[ReentryMode.PROPORTIONAL.value, 'Final_Value']:+.6f}"
        ),
        "- ETF note: no SGOV exit occurred, so re-entry mode was not exercised.",
        "",
        "## Comparison",
        "",
        markdown_table(comparison),
        "",
        "## Validation",
        "",
        "- A-only SGOV principal re-entry allocated 100% to COIW.",
        "- CONL received only its approved 50% dividend reinvestment.",
        "- Profit/loss, return, trade, and SGOV counters reconciled.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    validate_engine_allocation()
    results = build_results()
    validate_results(results)
    summary = build_summary(results)

    results.to_csv(OUTPUT_PATH, index=False)
    SUMMARY_PATH.write_text(summary, encoding="utf-8")

    print(results.to_string(index=False))
    print("\nValidation: PASS")
    print(f"Results saved to: {OUTPUT_PATH}")
    print(f"Summary saved to: {SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
