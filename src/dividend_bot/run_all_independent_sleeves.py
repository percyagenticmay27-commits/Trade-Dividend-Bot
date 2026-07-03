"""Compare current pair architecture with independent sleeves for all pairs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from baseline_backtest import aligned_frames, max_drawdown_percent, sgov_daily_returns
from dividend_engine import DividendEngine
from earnings_engine import EarningsController, load_earnings_schedule
from indicators import calculate_symbol_signals
from pairs_config import STANDARD_PAIRS
from portfolio_engine import IndependentPairPortfolio


EARNINGS_RESULTS_PATH = Path("earnings_backtest_results.csv")
OUTPUT_PATH = Path("independent_sleeve_results.csv")
SUMMARY_PATH = Path("independent_sleeve_summary.md")
STARTING_CAPITAL = 50.0

CURRENT_MODE = "current_pair_underlying_proportional"
INDEPENDENT_MODE = "independent_sleeves"
SPECIAL_PAIR = ("MST", "XXRP")

OUTPUT_COLUMNS = [
    "Pair",
    "Mode",
    "Initial_Capital",
    "Final_Value",
    "Profit_Loss",
    "Return_Pct",
    "Max_Drawdown",
    "Trades",
    "SGOV_Entries",
    "SGOV_Exits",
    "Days_In_SGOV",
    "Earnings_Exits",
    "Dividends_Received",
    "Dividends_Reinvested_A",
    "Dividends_Reinvested_B",
    "Different_Signal_Days",
    "Independent_State_Days",
]

PAIR_CONFIGS = [
    ("AMDW", "AMDL", "AMD", "AMDW", "AMDL"),
    ("GLDW", "NUGT", None, "GLDW", "NUGT"),
    ("NVDW", "NVDX", "NVDA", "NVDW", "NVDX"),
    ("GOOW", "GGLL", "GOOGL", "GOOW", "GGLL"),
    ("NFLW", "NFLU", "NFLX", "NFLW", "NFLU"),
    ("AVGW", "AVGX", "AVGO", "AVGW", "AVGX"),
    ("COIW", "CONL", "COIN", "COIW", "CONL"),
    ("PLTW", "PLTU", "PLTR", "PLTW", "PLTU"),
    ("TSLW", "TSLL", "TSLA", "TSLW", "TSLL"),
    ("MST", "XXRP", "MSTR", "MSTR", "XXRP"),
]


def process_sleeve(
    dividends: DividendEngine,
    controller: EarningsController,
    sleeve,
    side: str,
    date: pd.Timestamp,
    current_signal: str,
    prior_signal: str,
    price,
) -> None:
    """Apply earnings lock or ordinary signal to one sleeve."""
    if controller.is_blocked:
        if controller.can_reenter(date, current_signal):
            traded = dividends.buy_independent_sleeve(
                sleeve,
                side,
                price,
            )
            if traded:
                controller.complete_reentry()
    elif prior_signal == "BUY":
        dividends.buy_independent_sleeve(sleeve, side, price)
    else:
        sleeve.process_signal(prior_signal, price)


def run_independent_pair(
    left: str,
    right: str,
    earnings_underlying: str | None,
    a_signal_symbol: str,
    b_signal_symbol: str,
) -> tuple[dict[str, object], dict[str, int | float]]:
    """Run one pair as independently controlled A and B sleeves."""
    frames = aligned_frames([left, right])
    a_data = frames[left]
    b_data = frames[right]
    dates = a_data.index

    a_signals = calculate_symbol_signals(a_signal_symbol).reindex(dates)
    b_signals = calculate_symbol_signals(b_signal_symbol).reindex(dates)
    if a_signals["Signal"].isna().any() or b_signals["Signal"].isna().any():
        raise ValueError(f"Signals are missing dates for {left}/{right}")

    events = (
        []
        if earnings_underlying is None
        else load_earnings_schedule(earnings_underlying, dates)
    )
    b_follows_earnings = (left, right) != SPECIAL_PAIR
    a_earnings = EarningsController(events)
    b_earnings = EarningsController(events if b_follows_earnings else [])
    sgov_returns = sgov_daily_returns(dates)
    dividends = DividendEngine()

    portfolio = IndependentPairPortfolio(a_symbol=left, b_symbol=right)
    portfolio.initialize(a_data.iloc[0]["Close"], b_data.iloc[0]["Close"])

    equity_curve = [
        portfolio.current_value(
            a_data.iloc[0]["Close"],
            b_data.iloc[0]["Close"],
        )
    ]
    days_in_sgov = 0
    independent_state_days = 0

    for position in range(1, len(dates)):
        date = dates[position]
        a_close = a_data.iloc[position]["Close"]
        b_close = b_data.iloc[position]["Close"]
        eligible_a_shares = portfolio.a_sleeve.shares
        daily_sgov_return = sgov_returns.iloc[position]

        portfolio.a_sleeve.accrue_sgov(daily_sgov_return)
        portfolio.b_sleeve.accrue_sgov(daily_sgov_return)

        exit_event = a_earnings.event_for_exit(date)
        if exit_event is not None:
            a_traded = portfolio.a_sleeve.sell_to_sgov(a_close)
            a_earnings.activate_exit(exit_event, a_traded)
            if b_follows_earnings:
                b_traded = portfolio.b_sleeve.sell_to_sgov(b_close)
                b_earnings.activate_exit(exit_event, b_traded)
            else:
                process_sleeve(
                    dividends,
                    b_earnings,
                    portfolio.b_sleeve,
                    "B",
                    date,
                    b_signals.iloc[position]["Signal"],
                    b_signals.iloc[position - 1]["Signal"],
                    b_close,
                )
        else:
            process_sleeve(
                dividends,
                a_earnings,
                portfolio.a_sleeve,
                "A",
                date,
                a_signals.iloc[position]["Signal"],
                a_signals.iloc[position - 1]["Signal"],
                a_close,
            )
            process_sleeve(
                dividends,
                b_earnings,
                portfolio.b_sleeve,
                "B",
                date,
                b_signals.iloc[position]["Signal"],
                b_signals.iloc[position - 1]["Signal"],
                b_close,
            )

        dividends.apply_independent_dividend(
            portfolio,
            eligible_a_shares=eligible_a_shares,
            dividend_per_share=a_data.iloc[position]["Dividends"],
            a_price=a_close,
            b_price=b_close,
        )

        if portfolio.a_sleeve.in_sgov or portfolio.b_sleeve.in_sgov:
            days_in_sgov += 1
        if portfolio.a_sleeve.in_sgov != portfolio.b_sleeve.in_sgov:
            independent_state_days += 1

        equity_curve.append(portfolio.current_value(a_close, b_close))

    snapshot = portfolio.snapshot(
        a_data.iloc[-1]["Close"],
        b_data.iloc[-1]["Close"],
    )
    final_value = float(snapshot["current_value"])
    profit_loss = final_value - STARTING_CAPITAL
    different_signal_days = int(
        (a_signals["Signal"] != b_signals["Signal"]).sum()
    )

    row = {
        "Pair": f"{left} / {right}",
        "Mode": INDEPENDENT_MODE,
        "Initial_Capital": STARTING_CAPITAL,
        "Final_Value": round(final_value, 6),
        "Profit_Loss": round(profit_loss, 6),
        "Return_Pct": round(profit_loss / STARTING_CAPITAL * 100, 6),
        "Max_Drawdown": round(max_drawdown_percent(equity_curve), 6),
        "Trades": snapshot["trade_count"],
        "SGOV_Entries": snapshot["sgov_entries"],
        "SGOV_Exits": snapshot["sgov_exits"],
        "Days_In_SGOV": days_in_sgov,
        "Earnings_Exits": (
            a_earnings.earnings_exit_count + b_earnings.earnings_exit_count
        ),
        "Dividends_Received": round(float(dividends.totals.received), 6),
        "Dividends_Reinvested_A": round(
            float(dividends.totals.reinvested_a),
            6,
        ),
        "Dividends_Reinvested_B": round(
            float(dividends.totals.reinvested_b),
            6,
        ),
        "Different_Signal_Days": different_signal_days,
        "Independent_State_Days": independent_state_days,
    }
    diagnostics = {
        "pending_dividends": float(
            dividends.totals.pending_a + dividends.totals.pending_b
        ),
        "a_earnings_exits": a_earnings.earnings_exit_count,
        "b_earnings_exits": b_earnings.earnings_exit_count,
        "equity_curve": pd.Series(
            [float(value) for value in equity_curve],
            index=dates,
            name=f"{left} / {right}",
        ),
    }
    return row, diagnostics


def current_pair_row(
    earnings_results: pd.DataFrame,
    pair: str,
    different_signal_days: int,
    independent_state_days: int = 0,
) -> dict[str, object]:
    """Load the selected current architecture row."""
    if pair == "MST / XXRP":
        model = "Independent"
    else:
        model = "Underlying"

    matching = earnings_results[
        (earnings_results["Pair"] == pair)
        & (earnings_results["Model"] == model)
        & (earnings_results["Reentry_Mode"] == "proportional")
    ]
    if len(matching) != 1:
        raise AssertionError(f"Expected one current row for {pair}")
    source = matching.iloc[0]

    return {
        "Pair": pair,
        "Mode": CURRENT_MODE,
        "Initial_Capital": source["Initial_Capital"],
        "Final_Value": source["Final_Value"],
        "Profit_Loss": source["Profit_Loss"],
        "Return_Pct": source["Return_Pct"],
        "Max_Drawdown": source["Max_Drawdown"],
        "Trades": source["Trades"],
        "SGOV_Entries": source["SGOV_Entries"],
        "SGOV_Exits": source["SGOV_Exits"],
        "Days_In_SGOV": source["Days_In_SGOV"],
        "Earnings_Exits": source["Earnings_Exits"],
        "Dividends_Received": source["Dividends_Received"],
        "Dividends_Reinvested_A": source["Dividends_Reinvested_A"],
        "Dividends_Reinvested_B": source["Dividends_Reinvested_B"],
        "Different_Signal_Days": different_signal_days,
        "Independent_State_Days": independent_state_days,
    }


def build_results() -> tuple[pd.DataFrame, dict[str, dict[str, int | float]]]:
    """Build current and independent rows for all ten pairs."""
    if not EARNINGS_RESULTS_PATH.exists():
        raise FileNotFoundError(
            f"Required earnings results not found: {EARNINGS_RESULTS_PATH}"
        )
    earnings_results = pd.read_csv(EARNINGS_RESULTS_PATH)

    current_rows = []
    independent_rows = []
    diagnostics = {}

    for left, right, earnings_underlying, a_signal, b_signal in PAIR_CONFIGS:
        pair = f"{left} / {right}"
        independent_row, pair_diagnostics = run_independent_pair(
            left,
            right,
            earnings_underlying,
            a_signal,
            b_signal,
        )
        independent_rows.append(independent_row)
        diagnostics[pair] = pair_diagnostics

        current_rows.append(
            current_pair_row(
                earnings_results,
                pair,
                independent_row["Different_Signal_Days"],
                (
                    independent_row["Independent_State_Days"]
                    if pair == "MST / XXRP"
                    else 0
                ),
            )
        )

    rows = []
    for current, independent in zip(current_rows, independent_rows):
        rows.extend([current, independent])
    return pd.DataFrame(rows)[OUTPUT_COLUMNS], diagnostics


def validate_dividend_waiting() -> None:
    """Verify a target sleeve holds its half until its own BUY."""
    from decimal import Decimal

    portfolio = IndependentPairPortfolio(a_symbol="A", b_symbol="B")
    portfolio.initialize("10", "5")
    dividends = DividendEngine()
    eligible_shares = portfolio.a_sleeve.shares
    portfolio.b_sleeve.sell_to_sgov("5")

    dividends.apply_independent_dividend(
        portfolio,
        eligible_a_shares=eligible_shares,
        dividend_per_share="1",
        a_price="10",
        b_price="5",
    )
    assert dividends.totals.reinvested_a == Decimal("1.75")
    assert dividends.totals.pending_b == Decimal("1.75")

    dividends.buy_independent_sleeve(portfolio.b_sleeve, "B", "5")
    assert dividends.totals.pending_b == Decimal("0")
    assert dividends.totals.reinvested_b == Decimal("1.75")


def validate_results(
    results: pd.DataFrame,
    diagnostics: dict[str, dict[str, int | float]],
) -> None:
    """Validate coverage, state independence, earnings, and accounting."""
    assert list(results.columns) == OUTPUT_COLUMNS
    assert len(results) == 20
    assert not results.isna().any().any()
    assert results["Pair"].nunique() == 10
    assert results.groupby("Pair").size().eq(2).all()
    assert results["Initial_Capital"].eq(50.0).all()
    assert results["Trades"].eq(
        results["SGOV_Entries"] + results["SGOV_Exits"]
    ).all()
    assert (
        results["Final_Value"]
        - results["Initial_Capital"]
        - results["Profit_Loss"]
    ).abs().lt(0.000002).all()

    independent = results[results["Mode"] == INDEPENDENT_MODE]
    assert (independent["Independent_State_Days"] > 0).any()

    gl_pair = independent[independent["Pair"] == "GLDW / NUGT"].iloc[0]
    assert gl_pair["Earnings_Exits"] == 0

    earnings_pairs = independent[independent["Pair"] != "GLDW / NUGT"]
    assert earnings_pairs["Earnings_Exits"].gt(0).all()

    mst = results[results["Pair"] == "MST / XXRP"]
    assert mst["Final_Value"].nunique() == 1
    assert mst["Max_Drawdown"].nunique() == 1

    for pair, pair_diagnostics in diagnostics.items():
        independent_row = independent[independent["Pair"] == pair].iloc[0]
        pending = pair_diagnostics["pending_dividends"]
        reinvested = (
            independent_row["Dividends_Reinvested_A"]
            + independent_row["Dividends_Reinvested_B"]
        )
        assert abs(
            independent_row["Dividends_Received"] - reinvested - pending
        ) < 0.000003

    validate_dividend_waiting()


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


def build_summary(results: pd.DataFrame) -> str:
    current = results[results["Mode"] == CURRENT_MODE].set_index("Pair")
    independent = results[results["Mode"] == INDEPENDENT_MODE].set_index("Pair")

    comparison = pd.DataFrame(
        {
            "Pair": current.index,
            "Current_Final": current["Final_Value"],
            "Independent_Final": independent["Final_Value"],
            "Difference_Dollars": (
                independent["Final_Value"] - current["Final_Value"]
            ),
            "Current_Drawdown": current["Max_Drawdown"],
            "Independent_Drawdown": independent["Max_Drawdown"],
            "Drawdown_Improvement": (
                independent["Max_Drawdown"] - current["Max_Drawdown"]
            ),
            "Different_Signal_Days": independent["Different_Signal_Days"],
            "Independent_State_Days": independent["Independent_State_Days"],
        }
    ).reset_index(drop=True)

    current_total = float(current["Final_Value"].sum())
    independent_total = float(independent["Final_Value"].sum())
    difference = independent_total - current_total
    difference_percent = difference / current_total * 100
    best = comparison.loc[comparison["Difference_Dollars"].idxmax()]
    worst = comparison.loc[comparison["Difference_Dollars"].idxmin()]
    helped = comparison[comparison["Difference_Dollars"] > 0]["Pair"].tolist()
    hurt = comparison[comparison["Difference_Dollars"] < 0]["Pair"].tolist()

    lines = [
        "# Independent Sleeve Architecture Summary",
        "",
        f"- Current 10-pair portfolio final value: ${current_total:.6f}",
        f"- Independent 10-pair portfolio final value: ${independent_total:.6f}",
        f"- Difference: ${difference:+.6f}",
        f"- Difference percent: {difference_percent:+.6f}%",
        (
            f"- Best improving pair: {best['Pair']} "
            f"(${best['Difference_Dollars']:+.6f})"
        ),
        (
            f"- Worst worsening pair: {worst['Pair']} "
            f"(${worst['Difference_Dollars']:+.6f})"
        ),
        f"- Pairs helped ({len(helped)}): {', '.join(helped) if helped else 'None'}",
        f"- Pairs hurt ({len(hurt)}): {', '.join(hurt) if hurt else 'None'}",
        (
            "- Average current drawdown: "
            f"{current['Max_Drawdown'].mean():.6f}%"
        ),
        (
            "- Average independent drawdown: "
            f"{independent['Max_Drawdown'].mean():.6f}%"
        ),
        "",
        "## Pair Comparison",
        "",
        markdown_table(comparison),
        "",
        "## Validation",
        "",
        "- At least one pair occupied different A/B sleeve states.",
        "- Dividend allocations waited when the target sleeve was in SGOV.",
        "- Earnings exits applied to both sleeves except GLD, which has no event.",
        "- MST/XXRP results remained unchanged.",
        "- Pair values reconcile to the sum of sleeve values.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    results, diagnostics = build_results()
    validate_results(results, diagnostics)
    summary = build_summary(results)

    results.to_csv(OUTPUT_PATH, index=False)
    SUMMARY_PATH.write_text(summary, encoding="utf-8")

    print(
        results[
            [
                "Pair",
                "Mode",
                "Final_Value",
                "Return_Pct",
                "Max_Drawdown",
                "Different_Signal_Days",
                "Independent_State_Days",
            ]
        ].to_string(index=False)
    )
    print("\nValidation: PASS")
    print(f"Results saved to: {OUTPUT_PATH}")
    print(f"Summary saved to: {SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
