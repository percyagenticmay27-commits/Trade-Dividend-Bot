"""Run the first local-data baseline backtest for approved pair signal models."""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import pandas as pd

from indicators import load_symbol_data
from pairs_config import STANDARD_PAIRS
from portfolio_engine import (
    DEFAULT_CAPITAL,
    IndependentPairPortfolio,
    PairPortfolio,
    ReentryMode,
    to_decimal,
)
from signal_model_etf import generate_etf_signals
from signal_model_underlying import generate_pair_signals


OUTPUT_PATH = Path("baseline_backtest_results.csv")
REENTRY_MODES = [
    ReentryMode.PROPORTIONAL,
    ReentryMode.FIXED_70_30,
]
BACKTEST_START_ENV = "AGENTIC_ETF_BACKTEST_START"
BACKTEST_END_ENV = "AGENTIC_ETF_BACKTEST_END"


def aligned_frames(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """Load symbol frames and restrict them to their common dates."""
    frames = {symbol: load_symbol_data(symbol) for symbol in symbols}
    start_date = os.environ.get(BACKTEST_START_ENV)
    end_date = os.environ.get(BACKTEST_END_ENV)
    if start_date or end_date:
        for symbol, frame in frames.items():
            mask = pd.Series(True, index=frame.index)
            if start_date:
                mask &= frame.index >= pd.Timestamp(start_date)
            if end_date:
                mask &= frame.index <= pd.Timestamp(end_date)
            frames[symbol] = frame.loc[mask].copy()

    common_dates = None
    for frame in frames.values():
        common_dates = (
            frame.index
            if common_dates is None
            else common_dates.intersection(frame.index)
        )

    if common_dates is None or common_dates.empty:
        raise ValueError(f"No common dates for symbols: {symbols}")

    return {symbol: frame.loc[common_dates].copy() for symbol, frame in frames.items()}


def sgov_daily_returns(index: pd.Index) -> pd.Series:
    """Return SGOV adjusted-close returns aligned to a backtest index."""
    sgov = load_symbol_data("SGOV").reindex(index)
    if sgov["Adj Close"].isna().any():
        raise ValueError("SGOV data is missing one or more required dates")
    return sgov["Adj Close"].pct_change().fillna(0)


def max_drawdown_percent(values: list[Decimal]) -> float:
    """Return maximum drawdown as a negative percentage."""
    equity = pd.Series([float(value) for value in values])
    drawdowns = equity / equity.cummax() - 1
    return float(drawdowns.min() * 100)


def result_row(
    pair: str,
    model: str,
    reentry_mode: str,
    final_value: Decimal,
    max_drawdown: float,
    sgov_entries: int,
    sgov_exits: int,
    days_in_sgov: int,
    trades: int,
) -> dict[str, object]:
    """Build one baseline result row."""
    profit_loss = final_value - DEFAULT_CAPITAL
    return_pct = profit_loss / DEFAULT_CAPITAL * Decimal("100")

    return {
        "Pair": pair,
        "Model": model,
        "Reentry_Mode": reentry_mode,
        "Initial_Capital": float(DEFAULT_CAPITAL),
        "Final_Value": round(float(final_value), 6),
        "Profit_Loss": round(float(profit_loss), 6),
        "Return_Pct": round(float(return_pct), 6),
        "Max_Drawdown": round(max_drawdown, 6),
        "SGOV_Entries": sgov_entries,
        "SGOV_Exits": sgov_exits,
        "Days_In_SGOV": days_in_sgov,
        "Trades": trades,
    }


def run_standard_pair(
    left: str,
    right: str,
    model: str,
    reentry_mode: ReentryMode,
) -> dict[str, object]:
    """Backtest one standard pair with a shared signal stream."""
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
        if portfolio.in_sgov:
            portfolio.accrue_sgov(sgov_returns.iloc[position])

        portfolio.process_signal(
            signals.iloc[position - 1]["Signal"],
            left_data.iloc[position]["Close"],
            right_data.iloc[position]["Close"],
        )

        if portfolio.in_sgov:
            days_in_sgov += 1

        equity_curve.append(
            portfolio.current_value(
                left_data.iloc[position]["Close"],
                right_data.iloc[position]["Close"],
            )
        )

    snapshot = portfolio.snapshot(
        left_data.iloc[-1]["Close"],
        right_data.iloc[-1]["Close"],
    )
    return result_row(
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


def run_independent_special_pair(
    reentry_mode: ReentryMode,
) -> dict[str, object]:
    """Backtest MST and XXRP as independently signaled sleeves."""
    frames = aligned_frames(["MST", "XXRP"])
    mst_data = frames["MST"]
    xxrp_data = frames["XXRP"]
    dates = mst_data.index

    mst_signals = generate_pair_signals("MST").reindex(dates)
    xxrp_signals = generate_etf_signals("XXRP").reindex(dates)
    if mst_signals["Signal"].isna().any() or xxrp_signals["Signal"].isna().any():
        raise ValueError("MST/XXRP independent signals are missing dates")

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
        daily_sgov_return = sgov_returns.iloc[position]
        portfolio.a_sleeve.accrue_sgov(daily_sgov_return)
        portfolio.b_sleeve.accrue_sgov(daily_sgov_return)

        portfolio.a_sleeve.process_signal(
            mst_signals.iloc[position - 1]["Signal"],
            mst_data.iloc[position]["Close"],
        )
        portfolio.b_sleeve.process_signal(
            xxrp_signals.iloc[position - 1]["Signal"],
            xxrp_data.iloc[position]["Close"],
        )

        if portfolio.a_sleeve.in_sgov or portfolio.b_sleeve.in_sgov:
            days_in_sgov += 1

        equity_curve.append(
            portfolio.current_value(
                mst_data.iloc[position]["Close"],
                xxrp_data.iloc[position]["Close"],
            )
        )

    snapshot = portfolio.snapshot(
        mst_data.iloc[-1]["Close"],
        xxrp_data.iloc[-1]["Close"],
    )
    return result_row(
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


def run_baseline_backtest() -> pd.DataFrame:
    """Run every standard model/mode combination and the special pair."""
    rows = []

    for left, right in STANDARD_PAIRS:
        for model in ["Underlying", "ETF"]:
            for reentry_mode in REENTRY_MODES:
                rows.append(
                    run_standard_pair(
                        left,
                        right,
                        model,
                        reentry_mode,
                    )
                )

    for reentry_mode in REENTRY_MODES:
        rows.append(run_independent_special_pair(reentry_mode))

    return pd.DataFrame(rows)


def validate_results(results: pd.DataFrame) -> None:
    """Validate baseline result coverage and accounting output."""
    expected_columns = [
        "Pair",
        "Model",
        "Reentry_Mode",
        "Initial_Capital",
        "Final_Value",
        "Profit_Loss",
        "Return_Pct",
        "Max_Drawdown",
        "SGOV_Entries",
        "SGOV_Exits",
        "Days_In_SGOV",
        "Trades",
    ]
    assert list(results.columns) == expected_columns
    assert len(results) == 38
    assert results["Initial_Capital"].eq(50.0).all()
    assert results["Final_Value"].gt(0).all()
    assert results["Max_Drawdown"].le(0).all()
    assert results["SGOV_Entries"].ge(results["SGOV_Exits"]).all()
    assert results["Trades"].eq(
        results["SGOV_Entries"] + results["SGOV_Exits"]
    ).all()
    assert not results.isna().any().any()

    independent = results[results["Model"] == "Independent"]
    assert len(independent) == 2
    assert independent["Final_Value"].nunique() == 1


def main() -> int:
    results = run_baseline_backtest()
    validate_results(results)
    results.to_csv(OUTPUT_PATH, index=False)

    print(results.to_string(index=False))
    print("\nAssertions: PASS")
    print(f"Rows: {len(results)}")
    print(f"Results saved to: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
