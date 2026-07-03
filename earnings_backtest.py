"""Run the dividend baseline with earnings exits and BUY-gated re-entry."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from baseline_backtest import (
    REENTRY_MODES,
    aligned_frames,
    max_drawdown_percent,
    result_row,
    sgov_daily_returns,
)
from dividend_backtest import add_dividend_columns, process_independent_signal
from dividend_engine import DividendEngine
from earnings_engine import EarningsController, load_earnings_schedule
from pairs_config import STANDARD_PAIRS
from portfolio_engine import IndependentPairPortfolio, PairPortfolio, ReentryMode
from signal_model_etf import generate_etf_signals
from signal_model_underlying import (
    generate_pair_signals,
    get_underlying_signal_source,
)


OUTPUT_PATH = Path("earnings_backtest_results.csv")
IMPACT_PATH = Path("earnings_impact_summary.csv")
DIVIDEND_RESULTS_PATH = Path("dividend_backtest_results.csv")

RESULT_COLUMNS = [
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
    "SGOV_Exits",
    "Days_In_SGOV",
    "Earnings_Exits",
    "Dividends_Received",
    "Dividends_Reinvested_A",
    "Dividends_Reinvested_B",
]


def process_pair_ordinary_signal(
    dividends: DividendEngine,
    portfolio: PairPortfolio,
    signal: str,
    left_close,
    right_close,
) -> bool:
    """Process one non-earnings pair signal with pending dividends."""
    if signal == "BUY":
        return dividends.buy_pair_from_sgov(
            portfolio,
            left_close,
            right_close,
        )
    return portfolio.process_signal(signal, left_close, right_close)


def run_standard_pair_with_earnings(
    left: str,
    right: str,
    model: str,
    reentry_mode: ReentryMode,
    return_equity_curve: bool = False,
):
    """Backtest one standard pair with dividends and earnings exits."""
    frames = aligned_frames([left, right])
    left_data = frames[left]
    right_data = frames[right]
    dates = left_data.index

    if model == "Underlying":
        signals = generate_pair_signals(left).reindex(dates)
    elif model == "ETF":
        signals = generate_etf_signals(left).reindex(dates)
    else:
        raise ValueError(f"unsupported model: {model}")

    if signals["Signal"].isna().any():
        raise ValueError(f"{left}/{right} {model} signals are missing dates")

    underlying = get_underlying_signal_source(left)
    events = [] if underlying == "GLD" else load_earnings_schedule(underlying, dates)
    earnings = EarningsController(events)
    dividends = DividendEngine()
    sgov_returns = sgov_daily_returns(dates)

    portfolio = PairPortfolio(left, right, reentry_mode=reentry_mode)
    portfolio.initialize(left_data.iloc[0]["Close"], right_data.iloc[0]["Close"])

    equity_curve = [
        portfolio.current_value(
            left_data.iloc[0]["Close"],
            right_data.iloc[0]["Close"],
        )
    ]
    days_in_sgov = 0

    for position in range(1, len(dates)):
        date = dates[position]
        left_close = left_data.iloc[position]["Close"]
        right_close = right_data.iloc[position]["Close"]
        eligible_a_shares = portfolio.a_shares

        if portfolio.in_sgov:
            portfolio.accrue_sgov(sgov_returns.iloc[position])

        exit_event = earnings.event_for_exit(date)
        current_signal = signals.iloc[position]["Signal"]
        prior_signal = signals.iloc[position - 1]["Signal"]

        if exit_event is not None:
            traded = portfolio.sell_to_sgov(left_close, right_close)
            earnings.activate_exit(exit_event, traded)
        elif earnings.is_blocked:
            if earnings.can_reenter(date, current_signal):
                traded = dividends.buy_pair_from_sgov(
                    portfolio,
                    left_close,
                    right_close,
                )
                if traded:
                    earnings.complete_reentry()
        else:
            process_pair_ordinary_signal(
                dividends,
                portfolio,
                prior_signal,
                left_close,
                right_close,
            )

        dividends.apply_pair_dividend(
            portfolio,
            eligible_a_shares=eligible_a_shares,
            dividend_per_share=left_data.iloc[position]["Dividends"],
            a_price=left_close,
            b_price=right_close,
        )

        if portfolio.in_sgov:
            days_in_sgov += 1

        equity_curve.append(portfolio.current_value(left_close, right_close))

    snapshot = portfolio.snapshot(
        left_data.iloc[-1]["Close"],
        right_data.iloc[-1]["Close"],
    )
    row = result_row(
        pair=f"{left} / {right}",
        model=model,
        reentry_mode=reentry_mode.value,
        final_value=snapshot["current_value"],
        max_drawdown=max_drawdown_percent(equity_curve),
        sgov_entries=snapshot["sgov_entries"],
        sgov_exits=snapshot["sgov_exits"],
        days_in_sgov=days_in_sgov,
        trades=snapshot["trade_count"],
    )
    row["Earnings_Exits"] = earnings.earnings_exit_count
    row = add_dividend_columns(row, dividends)
    if return_equity_curve:
        curve = pd.Series(
            [float(value) for value in equity_curve],
            index=dates,
            name=f"{left} / {right}",
        )
        return row, curve
    return row


def run_independent_pair_with_earnings(
    reentry_mode: ReentryMode,
) -> dict[str, object]:
    """Backtest MSTR earnings exits for MST while XXRP stays independent."""
    frames = aligned_frames(["MST", "XXRP"])
    mst_data = frames["MST"]
    xxrp_data = frames["XXRP"]
    dates = mst_data.index

    mst_signals = generate_pair_signals("MST").reindex(dates)
    xxrp_signals = generate_etf_signals("XXRP").reindex(dates)
    if mst_signals["Signal"].isna().any() or xxrp_signals["Signal"].isna().any():
        raise ValueError("MST/XXRP independent signals are missing dates")

    earnings = EarningsController(load_earnings_schedule("MSTR", dates))
    dividends = DividendEngine()
    sgov_returns = sgov_daily_returns(dates)
    portfolio = IndependentPairPortfolio()
    portfolio.initialize(mst_data.iloc[0]["Close"], xxrp_data.iloc[0]["Close"])

    equity_curve = [
        portfolio.current_value(
            mst_data.iloc[0]["Close"],
            xxrp_data.iloc[0]["Close"],
        )
    ]
    days_in_sgov = 0

    for position in range(1, len(dates)):
        date = dates[position]
        mst_close = mst_data.iloc[position]["Close"]
        xxrp_close = xxrp_data.iloc[position]["Close"]
        eligible_mst_shares = portfolio.a_sleeve.shares
        daily_sgov_return = sgov_returns.iloc[position]

        portfolio.a_sleeve.accrue_sgov(daily_sgov_return)
        portfolio.b_sleeve.accrue_sgov(daily_sgov_return)

        exit_event = earnings.event_for_exit(date)
        current_mst_signal = mst_signals.iloc[position]["Signal"]
        prior_mst_signal = mst_signals.iloc[position - 1]["Signal"]

        if exit_event is not None:
            traded = portfolio.a_sleeve.sell_to_sgov(mst_close)
            earnings.activate_exit(exit_event, traded)
        elif earnings.is_blocked:
            if earnings.can_reenter(date, current_mst_signal):
                traded = dividends.buy_independent_sleeve(
                    portfolio.a_sleeve,
                    "A",
                    mst_close,
                )
                if traded:
                    earnings.complete_reentry()
        else:
            process_independent_signal(
                dividends,
                prior_mst_signal,
                "A",
                portfolio.a_sleeve,
                mst_close,
            )

        process_independent_signal(
            dividends,
            xxrp_signals.iloc[position - 1]["Signal"],
            "B",
            portfolio.b_sleeve,
            xxrp_close,
        )

        dividends.apply_independent_dividend(
            portfolio,
            eligible_a_shares=eligible_mst_shares,
            dividend_per_share=mst_data.iloc[position]["Dividends"],
            a_price=mst_close,
            b_price=xxrp_close,
        )

        if portfolio.a_sleeve.in_sgov or portfolio.b_sleeve.in_sgov:
            days_in_sgov += 1

        equity_curve.append(portfolio.current_value(mst_close, xxrp_close))

    snapshot = portfolio.snapshot(
        mst_data.iloc[-1]["Close"],
        xxrp_data.iloc[-1]["Close"],
    )
    row = result_row(
        pair="MST / XXRP",
        model="Independent",
        reentry_mode=reentry_mode.value,
        final_value=snapshot["current_value"],
        max_drawdown=max_drawdown_percent(equity_curve),
        sgov_entries=snapshot["sgov_entries"],
        sgov_exits=snapshot["sgov_exits"],
        days_in_sgov=days_in_sgov,
        trades=snapshot["trade_count"],
    )
    row["Earnings_Exits"] = earnings.earnings_exit_count
    return add_dividend_columns(row, dividends)


def run_earnings_backtest() -> pd.DataFrame:
    """Run all model/mode combinations with dividends and earnings exits."""
    rows = []

    for left, right in STANDARD_PAIRS:
        for model in ["Underlying", "ETF"]:
            for reentry_mode in REENTRY_MODES:
                rows.append(
                    run_standard_pair_with_earnings(
                        left,
                        right,
                        model,
                        reentry_mode,
                    )
                )

    for reentry_mode in REENTRY_MODES:
        rows.append(run_independent_pair_with_earnings(reentry_mode))

    return pd.DataFrame(rows)[RESULT_COLUMNS]


def build_impact_summary(results: pd.DataFrame) -> pd.DataFrame:
    """Compare earnings-enabled final values with dividend-only results."""
    if not DIVIDEND_RESULTS_PATH.exists():
        raise FileNotFoundError(
            f"Dividend baseline not found: {DIVIDEND_RESULTS_PATH}"
        )

    dividend = pd.read_csv(DIVIDEND_RESULTS_PATH)
    keys = ["Pair", "Model", "Reentry_Mode"]
    comparison = dividend[keys + ["Final_Value"]].merge(
        results[keys + ["Final_Value"]],
        on=keys,
        suffixes=("_Dividend", "_Earnings"),
    )
    comparison["Difference_Dollars"] = (
        comparison["Final_Value_Earnings"]
        - comparison["Final_Value_Dividend"]
    )
    comparison["Difference_Percent"] = (
        comparison["Difference_Dollars"]
        / comparison["Final_Value_Dividend"]
        * 100
    )
    comparison = comparison.rename(
        columns={
            "Final_Value_Dividend": "Dividend_Backtest_Final",
            "Final_Value_Earnings": "Earnings_Backtest_Final",
        }
    )
    numeric_columns = [
        "Dividend_Backtest_Final",
        "Earnings_Backtest_Final",
        "Difference_Dollars",
        "Difference_Percent",
    ]
    comparison[numeric_columns] = comparison[numeric_columns].round(6)
    return comparison[
        [
            "Pair",
            "Model",
            "Reentry_Mode",
            "Dividend_Backtest_Final",
            "Earnings_Backtest_Final",
            "Difference_Dollars",
            "Difference_Percent",
        ]
    ]


def validate_results(
    results: pd.DataFrame,
    impact: pd.DataFrame,
) -> None:
    """Validate schema, accounting counters, and comparison coverage."""
    assert list(results.columns) == RESULT_COLUMNS
    assert len(results) == 38
    assert len(impact) == 38
    assert not results.isna().any().any()
    assert not impact.isna().any().any()
    assert results["Initial_Capital"].eq(50.0).all()
    assert results["Earnings_Exits"].ge(0).all()
    assert results["Trades"].eq(
        results["SGOV_Entries"] + results["SGOV_Exits"]
    ).all()

    gl_from = results[results["Pair"] == "GLDW / NUGT"]
    assert gl_from["Earnings_Exits"].eq(0).all()

    mst = results[results["Pair"] == "MST / XXRP"]
    assert mst["Earnings_Exits"].ge(1).all()


def main() -> int:
    results = run_earnings_backtest()
    impact = build_impact_summary(results)
    validate_results(results, impact)

    results.to_csv(OUTPUT_PATH, index=False)
    impact.to_csv(IMPACT_PATH, index=False)

    print(results.to_string(index=False))
    print("\n====================================")
    print("EARNINGS IMPACT")
    print("====================================")
    print(impact.to_string(index=False))
    print("\nAssertions: PASS")
    print(f"Results saved to: {OUTPUT_PATH}")
    print(f"Impact summary saved to: {IMPACT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
