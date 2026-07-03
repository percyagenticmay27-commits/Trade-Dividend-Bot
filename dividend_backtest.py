"""Run the baseline backtest with income ETF A-side dividends."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pandas as pd

from baseline_backtest import (
    REENTRY_MODES,
    aligned_frames,
    max_drawdown_percent,
    result_row,
    sgov_daily_returns,
)
from dividend_engine import DividendEngine
from pairs_config import STANDARD_PAIRS
from portfolio_engine import (
    IndependentPairPortfolio,
    PairPortfolio,
    ReentryMode,
)
from signal_model_etf import generate_etf_signals
from signal_model_underlying import generate_pair_signals


OUTPUT_PATH = Path("dividend_backtest_results.csv")
BASELINE_PATH = Path("baseline_backtest_results.csv")


def add_dividend_columns(
    row: dict[str, object],
    dividends: DividendEngine,
) -> dict[str, object]:
    """Append required dividend totals to one result row."""
    row.update(
        {
            "Dividends_Received": round(float(dividends.totals.received), 6),
            "Dividends_Reinvested_A": round(
                float(dividends.totals.reinvested_a),
                6,
            ),
            "Dividends_Reinvested_B": round(
                float(dividends.totals.reinvested_b),
                6,
            ),
        }
    )
    return row


def run_standard_pair_with_dividends(
    left: str,
    right: str,
    model: str,
    reentry_mode: ReentryMode,
) -> dict[str, object]:
    """Backtest one standard pair with A-side dividend reinvestment."""
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
    dividends = DividendEngine()

    equity_curve = [
        portfolio.current_value(
            left_data.iloc[0]["Close"],
            right_data.iloc[0]["Close"],
        )
    ]
    days_in_sgov = 0

    for position in range(1, len(dates)):
        left_close = left_data.iloc[position]["Close"]
        right_close = right_data.iloc[position]["Close"]
        eligible_a_shares = portfolio.a_shares

        if portfolio.in_sgov:
            portfolio.accrue_sgov(sgov_returns.iloc[position])

        signal = signals.iloc[position - 1]["Signal"]
        if signal == "BUY":
            dividends.buy_pair_from_sgov(portfolio, left_close, right_close)
        else:
            portfolio.process_signal(signal, left_close, right_close)

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
    return add_dividend_columns(row, dividends)


def process_independent_signal(
    dividends: DividendEngine,
    signal: str,
    side: str,
    sleeve,
    price: Decimal | float | int | str,
) -> bool:
    """Apply one independent signal with pending-dividend handling."""
    if signal == "BUY":
        return dividends.buy_independent_sleeve(sleeve, side, price)
    return sleeve.process_signal(signal, price)


def run_independent_pair_with_dividends(
    reentry_mode: ReentryMode,
) -> dict[str, object]:
    """Backtest MST dividends with independent MST and XXRP signals."""
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
    dividends = DividendEngine()

    equity_curve = [
        portfolio.current_value(
            mst_data.iloc[0]["Close"],
            xxrp_data.iloc[0]["Close"],
        )
    ]
    days_in_sgov = 0

    for position in range(1, len(dates)):
        mst_close = mst_data.iloc[position]["Close"]
        xxrp_close = xxrp_data.iloc[position]["Close"]
        eligible_mst_shares = portfolio.a_sleeve.shares
        daily_sgov_return = sgov_returns.iloc[position]

        portfolio.a_sleeve.accrue_sgov(daily_sgov_return)
        portfolio.b_sleeve.accrue_sgov(daily_sgov_return)

        process_independent_signal(
            dividends,
            mst_signals.iloc[position - 1]["Signal"],
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
    return add_dividend_columns(row, dividends)


def run_dividend_backtest() -> pd.DataFrame:
    """Run all baseline combinations with A-side dividends enabled."""
    rows = []

    for left, right in STANDARD_PAIRS:
        for model in ["Underlying", "ETF"]:
            for reentry_mode in REENTRY_MODES:
                rows.append(
                    run_standard_pair_with_dividends(
                        left,
                        right,
                        model,
                        reentry_mode,
                    )
                )

    for reentry_mode in REENTRY_MODES:
        rows.append(run_independent_pair_with_dividends(reentry_mode))

    return pd.DataFrame(rows)


def validate_results(results: pd.DataFrame) -> None:
    """Validate dividend result coverage, schema, and accounting."""
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
        "Dividends_Received",
        "Dividends_Reinvested_A",
        "Dividends_Reinvested_B",
    ]
    assert list(results.columns) == expected_columns
    assert len(results) == 38
    assert not results.isna().any().any()
    assert results["Initial_Capital"].eq(50.0).all()
    assert results["Dividends_Received"].ge(0).all()
    assert results["Dividends_Reinvested_A"].ge(0).all()
    assert results["Dividends_Reinvested_B"].ge(0).all()
    assert (
        results["Dividends_Received"] + 0.000001
        >= results["Dividends_Reinvested_A"]
        + results["Dividends_Reinvested_B"]
    ).all()

    if BASELINE_PATH.exists():
        baseline = pd.read_csv(BASELINE_PATH)
        keys = ["Pair", "Model", "Reentry_Mode"]
        comparison = results.merge(
            baseline[keys + ["Final_Value"]],
            on=keys,
            suffixes=("_Dividend", "_Baseline"),
        )
        assert len(comparison) == len(results)
        assert (
            comparison["Final_Value_Dividend"]
            >= comparison["Final_Value_Baseline"] - 0.000001
        ).all()


def main() -> int:
    results = run_dividend_backtest()
    validate_results(results)
    results.to_csv(OUTPUT_PATH, index=False)

    print(results.to_string(index=False))
    print("\nAssertions: PASS")
    print(f"Rows: {len(results)}")
    print(
        "Total dividends received across result rows: "
        f"{results['Dividends_Received'].sum():.6f}"
    )
    print(f"Results saved to: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
