"""Build and validate the Milestone 10 hybrid portfolio."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from earnings_backtest import run_standard_pair_with_earnings
from pairs_config import STANDARD_PAIRS
from portfolio_engine import ReentryMode
from run_all_independent_sleeves import PAIR_CONFIGS, run_independent_pair


EARNINGS_RESULTS_PATH = Path("earnings_backtest_results.csv")
INDEPENDENT_RESULTS_PATH = Path("independent_sleeve_results.csv")
OUTPUT_PATH = Path("hybrid_portfolio_results.csv")
SUMMARY_PATH = Path("hybrid_portfolio_summary.md")

PAIR_CAPITAL = 50.0
PORTFOLIO_CAPITAL = 500.0
BENCHMARK_FINAL = 545.851548

INDEPENDENT_PAIRS = {
    "GOOW / GGLL",
    "COIW / CONL",
    "MST / XXRP",
}

OUTPUT_COLUMNS = [
    "Report_Level",
    "Pair",
    "Architecture",
    "Initial_Capital",
    "Final_Value",
    "Profit_Loss",
    "Return_Pct",
    "Max_Drawdown",
    "Average_Drawdown",
    "Trades",
    "SGOV_Entries",
    "Days_In_SGOV",
    "Dividends_Received",
    "Earnings_Exits",
    "Dividends_Reinvested_A",
    "Dividends_Reinvested_B",
]


def portfolio_max_drawdown(equity: pd.Series) -> float:
    drawdowns = equity / equity.cummax() - 1
    return float(drawdowns.min() * 100)


def pair_config(left: str, right: str):
    for config in PAIR_CONFIGS:
        if config[0] == left and config[1] == right:
            return config
    raise ValueError(f"Pair config not found for {left}/{right}")


def run_current_pair(left: str, right: str):
    """Run one current Underlying/proportional standard pair."""
    return run_standard_pair_with_earnings(
        left,
        right,
        "Underlying",
        ReentryMode.PROPORTIONAL,
        return_equity_curve=True,
    )


def run_independent_config(left: str, right: str):
    """Run one approved independent-sleeve pair configuration."""
    config = pair_config(left, right)
    row, diagnostics = run_independent_pair(*config)
    return row, diagnostics["equity_curve"]


def normalize_pair_row(
    row: dict[str, object],
    architecture: str,
) -> dict[str, object]:
    """Normalize pair result fields for the hybrid output."""
    return {
        "Report_Level": "Pair",
        "Pair": row["Pair"],
        "Architecture": architecture,
        "Initial_Capital": row["Initial_Capital"],
        "Final_Value": row["Final_Value"],
        "Profit_Loss": row["Profit_Loss"],
        "Return_Pct": row["Return_Pct"],
        "Max_Drawdown": row["Max_Drawdown"],
        "Average_Drawdown": row["Max_Drawdown"],
        "Trades": row["Trades"],
        "SGOV_Entries": row["SGOV_Entries"],
        "Days_In_SGOV": row["Days_In_SGOV"],
        "Dividends_Received": row["Dividends_Received"],
        "Earnings_Exits": row["Earnings_Exits"],
        "Dividends_Reinvested_A": row["Dividends_Reinvested_A"],
        "Dividends_Reinvested_B": row["Dividends_Reinvested_B"],
    }


def portfolio_row(
    architecture: str,
    pair_rows: list[dict[str, object]],
    curves: list[pd.Series],
) -> dict[str, object]:
    """Aggregate ten pair rows and synchronized daily curves."""
    pair_frame = pd.DataFrame(pair_rows)
    equity = pd.concat(curves, axis=1).sum(axis=1)
    final_value = float(pair_frame["Final_Value"].sum())
    profit_loss = final_value - PORTFOLIO_CAPITAL

    assert abs(float(equity.iloc[0]) - PORTFOLIO_CAPITAL) < 0.000001
    assert abs(float(equity.iloc[-1]) - final_value) < 0.000010

    return {
        "Report_Level": "Portfolio",
        "Pair": "ALL PAIRS",
        "Architecture": architecture,
        "Initial_Capital": PORTFOLIO_CAPITAL,
        "Final_Value": round(final_value, 6),
        "Profit_Loss": round(profit_loss, 6),
        "Return_Pct": round(profit_loss / PORTFOLIO_CAPITAL * 100, 6),
        "Max_Drawdown": round(portfolio_max_drawdown(equity), 6),
        "Average_Drawdown": round(
            float(pair_frame["Max_Drawdown"].mean()),
            6,
        ),
        "Trades": int(pair_frame["Trades"].sum()),
        "SGOV_Entries": int(pair_frame["SGOV_Entries"].sum()),
        "Days_In_SGOV": int(pair_frame["Days_In_SGOV"].sum()),
        "Dividends_Received": round(
            float(pair_frame["Dividends_Received"].sum()),
            6,
        ),
        "Earnings_Exits": int(pair_frame["Earnings_Exits"].sum()),
        "Dividends_Reinvested_A": round(
            float(pair_frame["Dividends_Reinvested_A"].sum()),
            6,
        ),
        "Dividends_Reinvested_B": round(
            float(pair_frame["Dividends_Reinvested_B"].sum()),
            6,
        ),
    }


def build_hybrid_results(return_curves: bool = False):
    """Run current benchmark components and select hybrid components."""
    current_rows = {}
    current_curves = {}

    for left, right in STANDARD_PAIRS:
        pair = f"{left} / {right}"
        row, curve = run_current_pair(left, right)
        current_rows[pair] = row
        current_curves[pair] = curve

    mst_row, mst_curve = run_independent_config("MST", "XXRP")
    current_rows["MST / XXRP"] = mst_row
    current_curves["MST / XXRP"] = mst_curve

    independent_rows = {}
    independent_curves = {}
    for left, right in [("GOOW", "GGLL"), ("COIW", "CONL")]:
        pair = f"{left} / {right}"
        row, curve = run_independent_config(left, right)
        independent_rows[pair] = row
        independent_curves[pair] = curve
    independent_rows["MST / XXRP"] = mst_row
    independent_curves["MST / XXRP"] = mst_curve

    hybrid_pairs = []
    hybrid_curves = []
    hybrid_curve_map = {}
    current_pairs = []
    benchmark_curves = []

    ordered_pairs = [f"{left} / {right}" for left, right in STANDARD_PAIRS]
    ordered_pairs.append("MST / XXRP")

    for pair in ordered_pairs:
        current_pairs.append(current_rows[pair])
        benchmark_curves.append(current_curves[pair])

        if pair in INDEPENDENT_PAIRS:
            selected = independent_rows[pair]
            selected_curve = independent_curves[pair]
            architecture = "independent_sleeves"
        else:
            selected = current_rows[pair]
            selected_curve = current_curves[pair]
            architecture = "pair_underlying_proportional"

        hybrid_pairs.append(normalize_pair_row(selected, architecture))
        hybrid_curves.append(selected_curve)
        hybrid_curve_map[pair] = selected_curve

    benchmark_normalized = [
        normalize_pair_row(row, "current_best_component")
        for row in current_pairs
    ]
    hybrid_portfolio = portfolio_row(
        "hybrid",
        hybrid_pairs,
        hybrid_curves,
    )
    benchmark_portfolio = portfolio_row(
        "current_best",
        benchmark_normalized,
        benchmark_curves,
    )

    report_rows = hybrid_pairs + [hybrid_portfolio, benchmark_portfolio]
    output = (
        pd.DataFrame(report_rows)[OUTPUT_COLUMNS],
        current_rows,
        independent_rows,
    )
    if return_curves:
        return (*output, hybrid_curve_map)
    return output


def validate_source_rows(
    report: pd.DataFrame,
    current_rows: dict[str, dict[str, object]],
    independent_rows: dict[str, dict[str, object]],
) -> None:
    """Reconcile selected pair rows to validated source result files."""
    if not EARNINGS_RESULTS_PATH.exists() or not INDEPENDENT_RESULTS_PATH.exists():
        raise FileNotFoundError("Required source result files are missing")

    earnings = pd.read_csv(EARNINGS_RESULTS_PATH)
    independent = pd.read_csv(INDEPENDENT_RESULTS_PATH)
    pair_rows = report[report["Report_Level"] == "Pair"]

    assert len(pair_rows) == 10
    assert pair_rows["Initial_Capital"].eq(PAIR_CAPITAL).all()

    for row in pair_rows.itertuples(index=False):
        if row.Architecture == "pair_underlying_proportional":
            source = earnings[
                (earnings["Pair"] == row.Pair)
                & (earnings["Model"] == "Underlying")
                & (earnings["Reentry_Mode"] == "proportional")
            ]
        else:
            source = independent[
                (independent["Pair"] == row.Pair)
                & (independent["Mode"] == "independent_sleeves")
            ]
        assert len(source) == 1
        assert abs(row.Final_Value - source.iloc[0]["Final_Value"]) < 0.000001
        assert abs(row.Max_Drawdown - source.iloc[0]["Max_Drawdown"]) < 0.000001

        received = row.Dividends_Received
        reinvested = row.Dividends_Reinvested_A + row.Dividends_Reinvested_B
        assert received + 0.000003 >= reinvested

    mst = pair_rows[pair_rows["Pair"] == "MST / XXRP"].iloc[0]
    assert abs(
        mst["Final_Value"] - current_rows["MST / XXRP"]["Final_Value"]
    ) < 0.000001


def validate_report(
    report: pd.DataFrame,
    current_rows: dict[str, dict[str, object]],
    independent_rows: dict[str, dict[str, object]],
) -> None:
    """Validate hybrid portfolio totals and source architecture matching."""
    assert list(report.columns) == OUTPUT_COLUMNS
    assert len(report) == 12
    assert not report.isna().any().any()

    pair_rows = report[report["Report_Level"] == "Pair"]
    portfolios = report[report["Report_Level"] == "Portfolio"]
    assert len(portfolios) == 2
    assert pair_rows["Initial_Capital"].sum() == PORTFOLIO_CAPITAL

    hybrid = portfolios[portfolios["Architecture"] == "hybrid"].iloc[0]
    benchmark = portfolios[
        portfolios["Architecture"] == "current_best"
    ].iloc[0]

    assert hybrid["Initial_Capital"] == PORTFOLIO_CAPITAL
    assert abs(hybrid["Final_Value"] - pair_rows["Final_Value"].sum()) < 0.000001
    assert abs(benchmark["Final_Value"] - BENCHMARK_FINAL) < 0.000001
    assert hybrid["Earnings_Exits"] == int(pair_rows["Earnings_Exits"].sum())
    assert hybrid["SGOV_Entries"] == int(pair_rows["SGOV_Entries"].sum())

    validate_source_rows(report, current_rows, independent_rows)


def markdown_table(frame: pd.DataFrame) -> str:
    display = frame.copy()
    for column in display.select_dtypes(include="number").columns:
        display[column] = display[column].map(lambda value: f"{value:.4f}")
    headers = list(display.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in display.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def build_summary(report: pd.DataFrame) -> str:
    """Build hybrid portfolio and pair comparison summary."""
    pair_rows = report[report["Report_Level"] == "Pair"].copy()
    portfolios = report[report["Report_Level"] == "Portfolio"].set_index(
        "Architecture"
    )
    hybrid = portfolios.loc["hybrid"]
    benchmark = portfolios.loc["current_best"]

    difference = hybrid["Final_Value"] - benchmark["Final_Value"]
    difference_pct = difference / benchmark["Final_Value"] * 100
    best = pair_rows.loc[pair_rows["Final_Value"].idxmax()]
    worst = pair_rows.loc[pair_rows["Final_Value"].idxmin()]

    comparison = pair_rows[
        [
            "Pair",
            "Architecture",
            "Final_Value",
            "Return_Pct",
            "Max_Drawdown",
            "Dividends_Received",
            "Earnings_Exits",
            "SGOV_Entries",
            "Days_In_SGOV",
        ]
    ]

    lines = [
        "# Hybrid Portfolio Summary",
        "",
        f"- Total starting capital: ${hybrid['Initial_Capital']:.2f}",
        f"- Hybrid ending capital: ${hybrid['Final_Value']:.6f}",
        f"- Hybrid profit/loss: ${hybrid['Profit_Loss']:+.6f}",
        f"- Hybrid return: {hybrid['Return_Pct']:+.6f}%",
        f"- Hybrid portfolio max drawdown: {hybrid['Max_Drawdown']:.6f}%",
        f"- Hybrid average pair drawdown: {hybrid['Average_Drawdown']:.6f}%",
        f"- Dividends received: ${hybrid['Dividends_Received']:.6f}",
        f"- Earnings exits: {int(hybrid['Earnings_Exits'])}",
        f"- SGOV entries: {int(hybrid['SGOV_Entries'])}",
        f"- SGOV pair-days: {int(hybrid['Days_In_SGOV'])}",
        (
            f"- Best pair: {best['Pair']} "
            f"(${best['Final_Value']:.6f})"
        ),
        (
            f"- Worst pair: {worst['Pair']} "
            f"(${worst['Final_Value']:.6f})"
        ),
        "",
        "## Comparison vs Current Best",
        "",
        f"- Current best ending capital: ${benchmark['Final_Value']:.6f}",
        f"- Difference dollars: ${difference:+.6f}",
        f"- Difference percent: {difference_pct:+.6f}%",
        f"- Current portfolio max drawdown: {benchmark['Max_Drawdown']:.6f}%",
        (
            "- Max drawdown change: "
            f"{hybrid['Max_Drawdown'] - benchmark['Max_Drawdown']:+.6f} "
            "percentage points"
        ),
        "",
        "## Hybrid Pair Components",
        "",
        markdown_table(comparison),
        "",
        "## Validation",
        "",
        "- Portfolio starts with 10 x $50 = $500.",
        "- Hybrid ending capital equals the sum of its 10 selected pair values.",
        "- Pair-managed rows match Underlying/proportional earnings results.",
        "- Independent rows match the validated independent-sleeve results.",
        "- MST/XXRP remains unchanged and independent.",
        "- Dividend and earnings totals reconcile to selected pair rows.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    report, current_rows, independent_rows = build_hybrid_results()
    validate_report(report, current_rows, independent_rows)
    summary = build_summary(report)

    report.to_csv(OUTPUT_PATH, index=False)
    SUMMARY_PATH.write_text(summary, encoding="utf-8")

    print(
        report[
            [
                "Report_Level",
                "Pair",
                "Architecture",
                "Final_Value",
                "Return_Pct",
                "Max_Drawdown",
            ]
        ].to_string(index=False)
    )
    print("\nValidation: PASS")
    print(f"Results saved to: {OUTPUT_PATH}")
    print(f"Summary saved to: {SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
