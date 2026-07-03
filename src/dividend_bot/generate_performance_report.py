"""Generate pair, portfolio, ranking, and milestone comparison reports."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


BASELINE_PATH = Path("baseline_backtest_results.csv")
DIVIDEND_PATH = Path("dividend_backtest_results.csv")
EARNINGS_PATH = Path("earnings_backtest_results.csv")
IMPACT_PATH = Path("earnings_impact_summary.csv")
REPORT_PATH = Path("performance_report.csv")
SUMMARY_PATH = Path("performance_summary.md")

MODELS = ["Underlying", "ETF"]
REENTRY_MODES = ["proportional", "fixed_70_30"]
PAIR_COUNT = 10
PAIR_CAPITAL = 50.0
PORTFOLIO_CAPITAL = PAIR_COUNT * PAIR_CAPITAL

REPORT_COLUMNS = [
    "Report_Level",
    "Pair",
    "Model",
    "Reentry_Mode",
    "Initial_Capital",
    "Final_Value",
    "Profit_Loss",
    "Return_Pct",
    "Max_Drawdown",
    "Trades",
    "SGOV_Entries",
    "Days_In_SGOV",
    "Dividends_Received",
    "Earnings_Exits",
]


def load_inputs() -> dict[str, pd.DataFrame]:
    """Load all required milestone result files."""
    paths = {
        "Baseline": BASELINE_PATH,
        "Dividend": DIVIDEND_PATH,
        "Earnings": EARNINGS_PATH,
        "Impact": IMPACT_PATH,
    }
    frames = {}
    for name, path in paths.items():
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")
        frames[name] = pd.read_csv(path)
    return frames


def select_portfolio_rows(
    results: pd.DataFrame,
    model: str,
    reentry_mode: str,
) -> pd.DataFrame:
    """Select nine standard rows plus the independent special pair."""
    standard = results[
        (results["Model"] == model)
        & (results["Reentry_Mode"] == reentry_mode)
    ]
    special = results[
        (results["Model"] == "Independent")
        & (results["Reentry_Mode"] == reentry_mode)
    ]
    selected = pd.concat([standard, special], ignore_index=True)
    if len(selected) != PAIR_COUNT:
        raise AssertionError(
            f"Expected {PAIR_COUNT} rows for {model}/{reentry_mode}, "
            f"found {len(selected)}"
        )
    return selected


def portfolio_row(
    results: pd.DataFrame,
    model: str,
    reentry_mode: str,
) -> dict[str, object]:
    """Aggregate one deployable ten-pair portfolio configuration."""
    selected = select_portfolio_rows(results, model, reentry_mode)
    ending = float(selected["Final_Value"].sum())
    profit_loss = ending - PORTFOLIO_CAPITAL

    dividends = (
        float(selected["Dividends_Received"].sum())
        if "Dividends_Received" in selected.columns
        else 0.0
    )
    earnings_exits = (
        int(selected["Earnings_Exits"].sum())
        if "Earnings_Exits" in selected.columns
        else 0
    )

    return {
        "Report_Level": "Portfolio",
        "Pair": "ALL PAIRS",
        "Model": model,
        "Reentry_Mode": reentry_mode,
        "Initial_Capital": PORTFOLIO_CAPITAL,
        "Final_Value": round(ending, 6),
        "Profit_Loss": round(profit_loss, 6),
        "Return_Pct": round(profit_loss / PORTFOLIO_CAPITAL * 100, 6),
        "Max_Drawdown": round(float(selected["Max_Drawdown"].mean()), 6),
        "Trades": int(selected["Trades"].sum()),
        "SGOV_Entries": int(selected["SGOV_Entries"].sum()),
        "Days_In_SGOV": int(selected["Days_In_SGOV"].sum()),
        "Dividends_Received": round(dividends, 6),
        "Earnings_Exits": earnings_exits,
    }


def build_portfolio_summary(results: pd.DataFrame) -> pd.DataFrame:
    """Build four portfolio configuration rows."""
    rows = []
    for model in MODELS:
        for reentry_mode in REENTRY_MODES:
            rows.append(portfolio_row(results, model, reentry_mode))
    return pd.DataFrame(rows)[REPORT_COLUMNS]


def build_pair_report(earnings: pd.DataFrame) -> pd.DataFrame:
    """Convert earnings result rows to the shared performance schema."""
    pair_report = earnings.copy()
    pair_report.insert(0, "Report_Level", "Pair")
    return pair_report[REPORT_COLUMNS]


def build_performance_report(earnings: pd.DataFrame) -> pd.DataFrame:
    """Combine pair-level and portfolio-level earnings performance."""
    pair_report = build_pair_report(earnings)
    portfolio_report = build_portfolio_summary(earnings)
    return pd.concat([pair_report, portfolio_report], ignore_index=True)


def stage_comparison(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Build baseline/dividend/earnings portfolio totals."""
    rows = []
    for stage in ["Baseline", "Dividend", "Earnings"]:
        stage_rows = build_portfolio_summary(frames[stage]).copy()
        stage_rows.insert(0, "Stage", stage)
        rows.append(stage_rows)
    return pd.concat(rows, ignore_index=True)


def drawdown_improvements(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Rank earnings drawdown changes against the dividend backtest."""
    keys = ["Pair", "Model", "Reentry_Mode"]
    merged = frames["Earnings"][keys + ["Max_Drawdown"]].merge(
        frames["Dividend"][keys + ["Max_Drawdown"]],
        on=keys,
        suffixes=("_Earnings", "_Dividend"),
    )
    merged["Drawdown_Improvement"] = (
        merged["Max_Drawdown_Earnings"]
        - merged["Max_Drawdown_Dividend"]
    )
    return merged.sort_values("Drawdown_Improvement", ascending=False).head(10)


def markdown_table(frame: pd.DataFrame) -> str:
    """Render a dataframe as a compact Markdown table without extra packages."""
    display = frame.copy()
    for column in display.select_dtypes(include="number").columns:
        display[column] = display[column].map(lambda value: f"{value:.4f}")

    headers = [str(column) for column in display.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in display.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def build_summary(
    report: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
) -> str:
    """Build the human-readable performance and ranking report."""
    pair_rows = report[report["Report_Level"] == "Pair"].copy()
    portfolios = report[report["Report_Level"] == "Portfolio"].copy()
    best_portfolio = portfolios.loc[portfolios["Final_Value"].idxmax()]
    best_pair = pair_rows.loc[pair_rows["Final_Value"].idxmax()]
    worst_pair = pair_rows.loc[pair_rows["Final_Value"].idxmin()]

    ranking_columns = [
        "Pair",
        "Model",
        "Reentry_Mode",
        "Final_Value",
        "Return_Pct",
        "Max_Drawdown",
    ]
    top_ten = pair_rows.nlargest(10, "Final_Value")[ranking_columns]
    worst_ten = pair_rows.nsmallest(10, "Final_Value")[ranking_columns]
    drawdown = drawdown_improvements(frames)
    earnings_improvement = frames["Impact"].nlargest(
        10,
        "Difference_Dollars",
    )

    stage = stage_comparison(frames)[
        [
            "Stage",
            "Model",
            "Reentry_Mode",
            "Initial_Capital",
            "Final_Value",
            "Return_Pct",
            "Max_Drawdown",
        ]
    ]

    lines = [
        "# Performance Summary",
        "",
        "## Portfolio Overview",
        "",
        f"- Total Starting Capital: ${best_portfolio['Initial_Capital']:.2f}",
        f"- Total Ending Capital: ${best_portfolio['Final_Value']:.6f}",
        f"- Total Return: {best_portfolio['Return_Pct']:.4f}%",
        (
            "- Best Pair/Model: "
            f"{best_pair['Pair']} / {best_pair['Model']} / "
            f"{best_pair['Reentry_Mode']} "
            f"(${best_pair['Final_Value']:.6f})"
        ),
        (
            "- Worst Pair/Model: "
            f"{worst_pair['Pair']} / {worst_pair['Model']} / "
            f"{worst_pair['Reentry_Mode']} "
            f"(${worst_pair['Final_Value']:.6f})"
        ),
        f"- Best Model: {best_portfolio['Model']}",
        f"- Best Re-entry Method: {best_portfolio['Reentry_Mode']}",
        f"- Average Drawdown: {best_portfolio['Max_Drawdown']:.4f}%",
        (
            "- Total Dividends Received: "
            f"${best_portfolio['Dividends_Received']:.6f}"
        ),
        f"- Total Earnings Exits: {int(best_portfolio['Earnings_Exits'])}",
        "",
        "## Portfolio Configurations",
        "",
        markdown_table(
            portfolios[
                [
                    "Model",
                    "Reentry_Mode",
                    "Initial_Capital",
                    "Final_Value",
                    "Profit_Loss",
                    "Return_Pct",
                    "Max_Drawdown",
                    "Dividends_Received",
                    "Earnings_Exits",
                ]
            ]
        ),
        "",
        "## Milestone Comparison",
        "",
        markdown_table(stage),
        "",
        "## Top 10 Pair/Model Combinations",
        "",
        markdown_table(top_ten),
        "",
        "## Worst 10 Pair/Model Combinations",
        "",
        markdown_table(worst_ten),
        "",
        "## Best Drawdown Improvements",
        "",
        markdown_table(drawdown),
        "",
        "## Best Earnings Improvements",
        "",
        markdown_table(earnings_improvement),
        "",
        "## Validation",
        "",
        "- Pair rows reconcile directly to `earnings_backtest_results.csv`.",
        "- Each portfolio contains nine standard pairs plus MST/XXRP once.",
        "- Portfolio starting capital reconciles to 10 x $50 = $500.",
        "- Portfolio ending capital equals the sum of its 10 pair rows.",
    ]
    return "\n".join(lines) + "\n"


def validate_report(
    report: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
) -> None:
    """Verify pair and portfolio totals against earnings results."""
    pair_rows = report[report["Report_Level"] == "Pair"]
    portfolio_rows = report[report["Report_Level"] == "Portfolio"]

    assert len(pair_rows) == len(frames["Earnings"]) == 38
    assert len(portfolio_rows) == 4
    assert list(report.columns) == REPORT_COLUMNS
    assert not report.isna().any().any()

    source = frames["Earnings"].reset_index(drop=True)
    assert pair_rows["Final_Value"].reset_index(drop=True).equals(
        source["Final_Value"]
    )
    assert pair_rows["Profit_Loss"].reset_index(drop=True).equals(
        source["Profit_Loss"]
    )

    for row in portfolio_rows.itertuples(index=False):
        selected = select_portfolio_rows(
            frames["Earnings"],
            row.Model,
            row.Reentry_Mode,
        )
        assert abs(row.Initial_Capital - PORTFOLIO_CAPITAL) < 0.000001
        assert abs(row.Final_Value - selected["Final_Value"].sum()) < 0.000001
        assert abs(row.Profit_Loss - (row.Final_Value - PORTFOLIO_CAPITAL)) < 0.000001
        assert row.Trades == int(selected["Trades"].sum())
        assert row.Earnings_Exits == int(selected["Earnings_Exits"].sum())


def main() -> int:
    frames = load_inputs()
    report = build_performance_report(frames["Earnings"])
    validate_report(report, frames)

    summary = build_summary(report, frames)
    report.to_csv(REPORT_PATH, index=False)
    SUMMARY_PATH.write_text(summary, encoding="utf-8")

    portfolio_rows = report[report["Report_Level"] == "Portfolio"]
    print(portfolio_rows.to_string(index=False))
    print("\nValidation: PASS")
    print(f"Performance report saved to: {REPORT_PATH}")
    print(f"Performance summary saved to: {SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
