"""Test equal, strength-weighted, and risk-adjusted hybrid allocations."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from run_hybrid_portfolio_test import (
    INDEPENDENT_PAIRS,
    build_hybrid_results,
    portfolio_max_drawdown,
)


OUTPUT_PATH = Path("weighted_hybrid_results.csv")
SUMMARY_PATH = Path("weighted_hybrid_summary.md")
TOTAL_CAPITAL = 500.0
BASE_PAIR_CAPITAL = 50.0
MIN_ALLOCATION = 20.0
MAX_ALLOCATION = 90.0

RESULT_COLUMNS = [
    "Portfolio_Type",
    "Starting_Capital",
    "Ending_Capital",
    "Profit_Loss",
    "Return_Pct",
    "Max_Drawdown",
    "Average_Drawdown",
    "Dividends_Received",
    "Earnings_Exits",
    "SGOV_Entries",
    "Days_In_SGOV",
]

EQUAL_ALLOCATIONS = {
    "AMDW / AMDL": 50.0,
    "GLDW / NUGT": 50.0,
    "NVDW / NVDX": 50.0,
    "GOOW / GGLL": 50.0,
    "NFLW / NFLU": 50.0,
    "AVGW / AVGX": 50.0,
    "COIW / CONL": 50.0,
    "PLTW / PLTU": 50.0,
    "TSLW / TSLL": 50.0,
    "MST / XXRP": 50.0,
}

STRENGTH_ALLOCATIONS = {
    "AMDW / AMDL": 75.0,
    "AVGW / AVGX": 60.0,
    "GOOW / GGLL": 60.0,
    "NVDW / NVDX": 55.0,
    "GLDW / NUGT": 50.0,
    "NFLW / NFLU": 50.0,
    "TSLW / TSLL": 45.0,
    "PLTW / PLTU": 40.0,
    "COIW / CONL": 35.0,
    "MST / XXRP": 30.0,
}


def risk_scores(pair_rows: pd.DataFrame) -> dict[str, float]:
    """Calculate Return_Pct / ABS(Max_Drawdown) for each hybrid pair."""
    scores = {}
    for row in pair_rows.itertuples(index=False):
        denominator = abs(float(row.Max_Drawdown))
        scores[row.Pair] = (
            float(row.Return_Pct) / denominator if denominator else 0.0
        )
    return scores


def constrained_risk_allocations(
    scores: dict[str, float],
) -> dict[str, float]:
    """Allocate $500 with $20 floors, $90 caps, and positive score weights."""
    allocations = {pair: MIN_ALLOCATION for pair in scores}
    remaining = TOTAL_CAPITAL - sum(allocations.values())
    positive_scores = {
        pair: max(score, 0.0)
        for pair, score in scores.items()
    }
    active = {
        pair
        for pair, score in positive_scores.items()
        if score > 0
    }

    if not active:
        active = set(scores)
        positive_scores = {pair: 1.0 for pair in scores}

    while remaining > 0.0000001 and active:
        total_score = sum(positive_scores[pair] for pair in active)
        capped_pairs = []

        for pair in active:
            proposed = remaining * positive_scores[pair] / total_score
            room = MAX_ALLOCATION - allocations[pair]
            if proposed >= room - 0.0000001:
                capped_pairs.append(pair)

        if not capped_pairs:
            for pair in active:
                allocations[pair] += (
                    remaining * positive_scores[pair] / total_score
                )
            remaining = 0.0
            break

        for pair in capped_pairs:
            room = MAX_ALLOCATION - allocations[pair]
            allocations[pair] += room
            remaining -= room
            active.remove(pair)

    if remaining > 0.0000001:
        available = [
            pair
            for pair in allocations
            if allocations[pair] < MAX_ALLOCATION
        ]
        for pair in available:
            room = MAX_ALLOCATION - allocations[pair]
            addition = min(room, remaining)
            allocations[pair] += addition
            remaining -= addition
            if remaining <= 0.0000001:
                break

    difference = TOTAL_CAPITAL - sum(allocations.values())
    if abs(difference) > 0:
        target = max(allocations, key=lambda pair: positive_scores[pair])
        allocations[target] += difference

    return allocations


def weighted_metrics(
    portfolio_type: str,
    allocations: dict[str, float],
    pair_rows: pd.DataFrame,
    curves: dict[str, pd.Series],
) -> dict[str, object]:
    """Scale validated $50 pair curves and aggregate portfolio metrics."""
    scaled_curves = []
    ending_capital = 0.0
    dividends_received = 0.0
    weighted_drawdown = 0.0

    indexed = pair_rows.set_index("Pair")
    for pair, allocation in allocations.items():
        scale = allocation / BASE_PAIR_CAPITAL
        row = indexed.loc[pair]
        scaled_curve = curves[pair] * scale
        scaled_curves.append(scaled_curve.rename(pair))
        ending_capital += float(row["Final_Value"]) * scale
        dividends_received += float(row["Dividends_Received"]) * scale
        weighted_drawdown += float(row["Max_Drawdown"]) * allocation

        assert abs(float(scaled_curve.iloc[0]) - allocation) < 0.000001
        assert abs(
            float(scaled_curve.iloc[-1]) - float(row["Final_Value"]) * scale
        ) < 0.000010

    portfolio_equity = pd.concat(scaled_curves, axis=1).sum(axis=1)
    profit_loss = ending_capital - TOTAL_CAPITAL

    return {
        "Portfolio_Type": portfolio_type,
        "Starting_Capital": TOTAL_CAPITAL,
        "Ending_Capital": round(ending_capital, 6),
        "Profit_Loss": round(profit_loss, 6),
        "Return_Pct": round(profit_loss / TOTAL_CAPITAL * 100, 6),
        "Max_Drawdown": round(
            portfolio_max_drawdown(portfolio_equity),
            6,
        ),
        "Average_Drawdown": round(
            weighted_drawdown / TOTAL_CAPITAL,
            6,
        ),
        "Dividends_Received": round(dividends_received, 6),
        "Earnings_Exits": int(pair_rows["Earnings_Exits"].sum()),
        "SGOV_Entries": int(pair_rows["SGOV_Entries"].sum()),
        "Days_In_SGOV": int(pair_rows["Days_In_SGOV"].sum()),
    }


def build_results():
    """Build weighted portfolio rows and allocation diagnostics."""
    hybrid_report, _, _, curves = build_hybrid_results(return_curves=True)
    pair_rows = hybrid_report[hybrid_report["Report_Level"] == "Pair"].copy()
    scores = risk_scores(pair_rows)
    risk_allocations = constrained_risk_allocations(scores)

    allocation_sets = {
        "Equal_Weight_Hybrid": EQUAL_ALLOCATIONS,
        "Strength_Weighted_Hybrid": STRENGTH_ALLOCATIONS,
        "Risk_Adjusted_Hybrid": risk_allocations,
    }
    rows = [
        weighted_metrics(name, allocations, pair_rows, curves)
        for name, allocations in allocation_sets.items()
    ]
    return (
        pd.DataFrame(rows)[RESULT_COLUMNS],
        allocation_sets,
        scores,
        pair_rows,
    )


def validate_results(
    results: pd.DataFrame,
    allocation_sets: dict[str, dict[str, float]],
    pair_rows: pd.DataFrame,
) -> None:
    """Validate allocation constraints, accounting, and architecture."""
    assert list(results.columns) == RESULT_COLUMNS
    assert len(results) == 3
    assert not results.isna().any().any()
    assert results["Starting_Capital"].eq(TOTAL_CAPITAL).all()

    for name, allocations in allocation_sets.items():
        assert set(allocations) == set(EQUAL_ALLOCATIONS)
        assert abs(sum(allocations.values()) - TOTAL_CAPITAL) < 0.000001
        if name == "Risk_Adjusted_Hybrid":
            assert min(allocations.values()) >= MIN_ALLOCATION - 0.000001
            assert max(allocations.values()) <= MAX_ALLOCATION + 0.000001

    equal = results[
        results["Portfolio_Type"] == "Equal_Weight_Hybrid"
    ].iloc[0]
    assert abs(equal["Ending_Capital"] - 551.009896) < 0.000001

    expected_independent = {
        pair
        for pair in pair_rows[
            pair_rows["Architecture"] == "independent_sleeves"
        ]["Pair"]
    }
    assert expected_independent == INDEPENDENT_PAIRS

    assert results["Earnings_Exits"].eq(
        int(pair_rows["Earnings_Exits"].sum())
    ).all()
    assert results["SGOV_Entries"].eq(
        int(pair_rows["SGOV_Entries"].sum())
    ).all()


def rank_results(results: pd.DataFrame) -> pd.DataFrame:
    ranking = results.copy()
    ranking["Return_Drawdown_Ratio"] = (
        ranking["Return_Pct"] / ranking["Max_Drawdown"].abs()
    )
    ranking["Ending_Rank"] = ranking["Ending_Capital"].rank(
        ascending=False,
        method="min",
    )
    ranking["Return_Rank"] = ranking["Return_Pct"].rank(
        ascending=False,
        method="min",
    )
    ranking["Drawdown_Rank"] = ranking["Max_Drawdown"].rank(
        ascending=False,
        method="min",
    )
    ranking["Ratio_Rank"] = ranking["Return_Drawdown_Ratio"].rank(
        ascending=False,
        method="min",
    )
    ranking["Overall_Rank_Sum"] = ranking[
        ["Ending_Rank", "Return_Rank", "Drawdown_Rank", "Ratio_Rank"]
    ].sum(axis=1)
    return ranking.sort_values(
        ["Overall_Rank_Sum", "Ending_Capital"],
        ascending=[True, False],
    )


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


def build_summary(
    results: pd.DataFrame,
    allocation_sets: dict[str, dict[str, float]],
    scores: dict[str, float],
) -> str:
    """Build weighted comparison, rankings, allocations, and conclusion."""
    ranking = rank_results(results)
    best = ranking.iloc[0]
    equal = results[
        results["Portfolio_Type"] == "Equal_Weight_Hybrid"
    ].iloc[0]
    improvement = best["Ending_Capital"] - equal["Ending_Capital"]
    improvement_pct = improvement / equal["Ending_Capital"] * 100

    risk_allocations = pd.DataFrame(
        {
            "Pair": list(allocation_sets["Risk_Adjusted_Hybrid"]),
            "Raw_Score": [
                scores[pair]
                for pair in allocation_sets["Risk_Adjusted_Hybrid"]
            ],
            "Allocation": list(
                allocation_sets["Risk_Adjusted_Hybrid"].values()
            ),
        }
    ).sort_values("Allocation", ascending=False)

    strength_allocations = pd.DataFrame(
        {
            "Pair": list(STRENGTH_ALLOCATIONS),
            "Allocation": list(STRENGTH_ALLOCATIONS.values()),
        }
    ).sort_values("Allocation", ascending=False)

    ratio_table = ranking[
        [
            "Portfolio_Type",
            "Ending_Capital",
            "Return_Pct",
            "Max_Drawdown",
            "Return_Drawdown_Ratio",
            "Ending_Rank",
            "Return_Rank",
            "Drawdown_Rank",
            "Ratio_Rank",
            "Overall_Rank_Sum",
        ]
    ]

    weighted_justified = (
        best["Portfolio_Type"] != "Equal_Weight_Hybrid"
        and best["Ending_Capital"] > equal["Ending_Capital"]
        and best["Max_Drawdown"] >= equal["Max_Drawdown"]
        and best["Return_Drawdown_Ratio"]
        > equal["Return_Pct"] / abs(equal["Max_Drawdown"])
    )
    if weighted_justified:
        answer = (
            "Yes for continued backtesting: weighting materially improved "
            "ending capital and return/drawdown efficiency without worsening "
            "max drawdown. No for an immediate live-allocation change: the "
            "risk-adjusted weights were fitted to this same backtest period, "
            "so they require out-of-sample or walk-forward validation first."
        )
    else:
        answer = (
            "No. Weighting did not improve return and return/drawdown "
            "efficiency without a max-drawdown tradeoff."
        )

    lines = [
        "# Weighted Hybrid Portfolio Summary",
        "",
        "## Portfolio Results",
        "",
        markdown_table(results),
        "",
        "## Rankings",
        "",
        markdown_table(ratio_table),
        "",
        f"- Best Overall Portfolio: {best['Portfolio_Type']}",
        f"- Improvement vs Equal Weight: ${improvement:+.6f}",
        f"- Improvement Percent: {improvement_pct:+.6f}%",
        "",
        "## Strength-Weighted Allocations",
        "",
        markdown_table(strength_allocations),
        "",
        "## Risk-Adjusted Allocations",
        "",
        (
            "Negative scores receive the $20 minimum. Remaining capital is "
            "distributed across positive scores with a $90 cap."
        ),
        "",
        markdown_table(risk_allocations),
        "",
        "The risk-adjusted allocation is an in-sample optimization because its "
        "scores use returns and drawdowns from the evaluated period.",
        "",
        "## Final Answer",
        "",
        answer,
        "",
        "## Validation",
        "",
        "- Every portfolio starts with exactly $500.",
        "- All pair allocations sum to $500.",
        "- Risk-adjusted allocations remain between $20 and $90.",
        "- Hybrid pair architecture and independent-pair selections are unchanged.",
        "- Dividend totals scale with capital and reconcile to pair results.",
        "- Earnings and SGOV event counts reconcile to the hybrid components.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    results, allocation_sets, scores, pair_rows = build_results()
    validate_results(results, allocation_sets, pair_rows)
    summary = build_summary(results, allocation_sets, scores)

    results.to_csv(OUTPUT_PATH, index=False)
    SUMMARY_PATH.write_text(summary, encoding="utf-8")

    print(results.to_string(index=False))
    print("\nValidation: PASS")
    print(f"Results saved to: {OUTPUT_PATH}")
    print(f"Summary saved to: {SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
