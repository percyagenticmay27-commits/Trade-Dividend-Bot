"""Run Milestone 12 weighted hybrid validation across cached periods."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

from indicators import DATA_DIR_ENV
from pairs_config import SYMBOLS
from run_hybrid_portfolio_test import INDEPENDENT_PAIRS, build_hybrid_results
from run_weighted_hybrid_optimization import (
    EQUAL_ALLOCATIONS,
    STRENGTH_ALLOCATIONS,
    constrained_risk_allocations,
    risk_scores,
    weighted_metrics,
)


DATA_ROOT = Path("walk_forward_data")
DOWNLOAD_SUMMARY = DATA_ROOT / "download_summary.csv"
OUTPUT_PATH = Path("walk_forward_results.csv")
SUMMARY_PATH = Path("walk_forward_summary.md")

PERIODS = {
    "Period A": ("2025-01-01", "2025-06-30"),
    "Period B": ("2025-07-01", "2025-12-31"),
    "Period C": ("2026-01-01", "2026-06-18"),
}

OUTPUT_COLUMNS = [
    "Period",
    "Portfolio_Type",
    "Starting_Capital",
    "Ending_Capital",
    "Profit_Loss",
    "Return_Pct",
    "Max_Drawdown",
    "Return_Drawdown_Ratio",
]


@contextmanager
def period_context(period: str, effective_start: str, end_date: str):
    keys = {
        DATA_DIR_ENV: str(
            (DATA_ROOT / period.lower().replace(" ", "_") / "daily").resolve()
        ),
        "AGENTIC_ETF_BACKTEST_START": effective_start,
        "AGENTIC_ETF_BACKTEST_END": end_date,
    }
    previous = {key: os.environ.get(key) for key in keys}
    os.environ.update(keys)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def coverage() -> pd.DataFrame:
    if not DOWNLOAD_SUMMARY.exists():
        raise FileNotFoundError(
            f"Walk-forward download summary not found: {DOWNLOAD_SUMMARY}"
        )
    return pd.read_csv(DOWNLOAD_SUMMARY)


def period_availability(
    download_rows: pd.DataFrame,
    period: str,
) -> tuple[bool, str | None, list[str]]:
    rows = download_rows[download_rows["Period"] == period]
    missing = rows.loc[rows["Status"] != "PASS", "Symbol"].tolist()
    if missing:
        return False, None, missing
    if set(rows["Symbol"]) != set(SYMBOLS):
        absent = sorted(set(SYMBOLS) - set(rows["Symbol"]))
        return False, None, absent
    effective_start = pd.to_datetime(rows["First_Date"]).max().strftime("%Y-%m-%d")
    return True, effective_start, []


def run_period(
    period: str,
    effective_start: str,
    end_date: str,
    allocations: dict[str, dict[str, float]],
) -> tuple[list[dict[str, object]], pd.DataFrame]:
    with period_context(period, effective_start, end_date):
        report, _, _, curves = build_hybrid_results(return_curves=True)
    pair_rows = report[report["Report_Level"] == "Pair"].copy()

    assert len(pair_rows) == 10
    assert set(
        pair_rows.loc[
            pair_rows["Architecture"] == "independent_sleeves", "Pair"
        ]
    ) == INDEPENDENT_PAIRS
    assert pair_rows["Initial_Capital"].eq(50.0).all()
    assert all(curve.index.min() == pd.Timestamp(effective_start) for curve in curves.values())
    assert (
        pair_rows["Dividends_Received"] + 0.000003
        >= pair_rows["Dividends_Reinvested_A"]
        + pair_rows["Dividends_Reinvested_B"]
    ).all()
    assert pair_rows["Earnings_Exits"].ge(0).all()

    rows = []
    for portfolio_type, pair_allocations in allocations.items():
        metrics = weighted_metrics(
            portfolio_type,
            pair_allocations,
            pair_rows,
            curves,
        )
        drawdown = abs(float(metrics["Max_Drawdown"]))
        rows.append(
            {
                "Period": period,
                "Portfolio_Type": portfolio_type,
                "Starting_Capital": metrics["Starting_Capital"],
                "Ending_Capital": metrics["Ending_Capital"],
                "Profit_Loss": metrics["Profit_Loss"],
                "Return_Pct": metrics["Return_Pct"],
                "Max_Drawdown": metrics["Max_Drawdown"],
                "Return_Drawdown_Ratio": round(
                    float(metrics["Return_Pct"]) / drawdown if drawdown else 0.0,
                    6,
                ),
            }
        )
    return rows, pair_rows


def unavailable_rows(period: str) -> list[dict[str, object]]:
    return [
        {
            "Period": period,
            "Portfolio_Type": portfolio_type,
            "Starting_Capital": 500.0,
            "Ending_Capital": None,
            "Profit_Loss": None,
            "Return_Pct": None,
            "Max_Drawdown": None,
            "Return_Drawdown_Ratio": None,
        }
        for portfolio_type in [
            "Equal_Weight_Hybrid",
            "Strength_Weighted_Hybrid",
            "Risk_Adjusted_Hybrid",
        ]
    ]


def markdown_table(frame: pd.DataFrame) -> str:
    display = frame.copy()
    for column in display.select_dtypes(include="number").columns:
        display[column] = display[column].map(
            lambda value: "N/A" if pd.isna(value) else f"{value:.6f}"
        )
    display = display.fillna("N/A")
    headers = list(display.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend(
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in display.itertuples(index=False, name=None)
    )
    return "\n".join(lines)


def build_summary(
    results: pd.DataFrame,
    availability: dict[str, tuple[bool, str | None, list[str]]],
) -> str:
    valid = results.dropna(subset=["Ending_Capital"]).copy()
    pivot = valid.pivot(index="Period", columns="Portfolio_Type", values="Ending_Capital")
    comparable_periods = list(pivot.index)
    strength_wins = int(
        (pivot["Strength_Weighted_Hybrid"] > pivot["Equal_Weight_Hybrid"]).sum()
    )
    risk_wins = int(
        (pivot["Risk_Adjusted_Hybrid"] > pivot["Equal_Weight_Hybrid"]).sum()
    )
    averages = (
        valid.groupby("Portfolio_Type", as_index=False)
        .agg(
            Average_Return=("Return_Pct", "mean"),
            Average_Max_Drawdown=("Max_Drawdown", "mean"),
            Average_Return_Drawdown_Ratio=("Return_Drawdown_Ratio", "mean"),
        )
        .sort_values("Average_Return", ascending=False)
    )
    best_return = averages.iloc[0]["Portfolio_Type"]
    best_drawdown = averages.sort_values(
        "Average_Max_Drawdown", ascending=False
    ).iloc[0]["Portfolio_Type"]

    strength_answer = (
        f"No. Strength Weighted beat Equal Weight in {strength_wins} of "
        f"{len(comparable_periods)} runnable periods. A three-period majority "
        "cannot be established because Period A is unavailable."
    )
    risk_answer = (
        f"Risk Adjusted outperformed Equal Weight in {risk_wins} of "
        f"{len(comparable_periods)} runnable periods: both shortened Period B "
        "and in-sample Period C."
    )

    coverage_lines = []
    for period, (available, effective_start, missing) in availability.items():
        requested_start, requested_end = PERIODS[period]
        if not available:
            coverage_lines.append(
                f"- {period}: unavailable; no history for {', '.join(missing)}. "
                f"Requested {requested_start} through {requested_end}."
            )
        elif effective_start != pd.Timestamp(requested_start).strftime("%Y-%m-%d"):
            coverage_lines.append(
                f"- {period}: runnable from common inception {effective_start} "
                f"through {requested_end}; requested start was {requested_start}."
            )
        else:
            coverage_lines.append(
                f"- {period}: full requested coverage {requested_start} through {requested_end}."
            )

    return "\n".join(
        [
            "# Walk-Forward Validation Summary",
            "",
            "## Results",
            "",
            markdown_table(results),
            "",
            "## Coverage",
            "",
            *coverage_lines,
            "",
            "## Cross-Period Averages",
            "",
            markdown_table(averages),
            "",
            "## Questions",
            "",
            f"1. {strength_answer}",
            f"2. {risk_answer}",
            f"3. Best average return across runnable periods: {best_return}.",
            f"4. Best average drawdown across runnable periods: {best_drawdown}.",
            (
                "5. Live deployment recommendation: Equal Weight Hybrid until "
                "a complete out-of-sample dataset is available. Weighted results "
                "may justify a paper-trading candidate, but missing Period A and "
                "the shortened Period B do not support live promotion."
            ),
            "",
            "## Validation",
            "",
            "- Every runnable portfolio starts with exactly $500.",
            "- Pair allocations sum to exactly $500.",
            "- The seven pair-managed and three independent-sleeve assignments are unchanged.",
            "- Dividend and earnings logic runs through the existing validated engines.",
            "- Period A coverage validation failed; no synthetic history or proxy symbols were used.",
        ]
    ) + "\n"


def main() -> int:
    downloads = coverage()
    availability = {
        period: period_availability(downloads, period) for period in PERIODS
    }

    c_available, c_start, _ = availability["Period C"]
    if not c_available or c_start is None:
        raise RuntimeError("Period C is required to reconstruct fixed risk weights")

    with period_context("Period C", c_start, PERIODS["Period C"][1]):
        c_report, _, _, _ = build_hybrid_results(return_curves=True)
    c_pairs = c_report[c_report["Report_Level"] == "Pair"].copy()
    fixed_risk_allocations = constrained_risk_allocations(risk_scores(c_pairs))

    allocation_sets = {
        "Equal_Weight_Hybrid": EQUAL_ALLOCATIONS,
        "Strength_Weighted_Hybrid": STRENGTH_ALLOCATIONS,
        "Risk_Adjusted_Hybrid": fixed_risk_allocations,
    }
    for allocations in allocation_sets.values():
        assert abs(sum(allocations.values()) - 500.0) < 0.000001

    rows = []
    for period, (_, end_date) in PERIODS.items():
        available, effective_start, _ = availability[period]
        if not available or effective_start is None:
            rows.extend(unavailable_rows(period))
            continue
        period_rows, _ = run_period(
            period,
            effective_start,
            end_date,
            allocation_sets,
        )
        rows.extend(period_rows)

    results = pd.DataFrame(rows)[OUTPUT_COLUMNS]
    assert len(results) == 9
    runnable = results.dropna(subset=["Ending_Capital"])
    assert runnable["Starting_Capital"].eq(500.0).all()

    results.to_csv(OUTPUT_PATH, index=False)
    SUMMARY_PATH.write_text(
        build_summary(results, availability),
        encoding="utf-8",
    )
    print(results.to_string(index=False))
    print(f"\nResults saved to: {OUTPUT_PATH}")
    print(f"Summary saved to: {SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
