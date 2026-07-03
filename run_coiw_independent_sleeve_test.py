"""Compare pair-based COIW/CONL with independent SGOV sleeves."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from baseline_backtest import aligned_frames, max_drawdown_percent, sgov_daily_returns
from dividend_engine import DividendEngine
from earnings_engine import EarningsController, load_earnings_schedule
from indicators import calculate_symbol_signals
from portfolio_engine import IndependentPairPortfolio


SOURCE_RESULTS_PATH = Path("coiw_reentry_test.csv")
OUTPUT_PATH = Path("coiw_independent_sleeve_test.csv")
PAIR = "COIW / CONL"
STARTING_CAPITAL = 50.0

OUTPUT_COLUMNS = [
    "Pair",
    "Architecture",
    "Final_Value",
    "Return_Pct",
    "Max_Drawdown",
    "Trades",
    "SGOV_Entries",
    "Days_In_SGOV",
    "Dividends_Received",
]


def process_sleeve_day(
    dividends: DividendEngine,
    controller: EarningsController,
    sleeve,
    side: str,
    date: pd.Timestamp,
    current_signal: str,
    prior_signal: str,
    price,
) -> None:
    """Process earnings lock or ordinary signal for one independent sleeve."""
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


def run_independent_architecture() -> tuple[dict[str, object], dict[str, int]]:
    """Run COIW and CONL with independent signals and SGOV sleeves."""
    frames = aligned_frames(["COIW", "CONL"])
    coiw_data = frames["COIW"]
    conl_data = frames["CONL"]
    dates = coiw_data.index

    coiw_signals = calculate_symbol_signals("COIW").reindex(dates)
    conl_signals = calculate_symbol_signals("CONL").reindex(dates)
    if coiw_signals["Signal"].isna().any() or conl_signals["Signal"].isna().any():
        raise ValueError("Independent COIW/CONL signals are missing dates")

    events = load_earnings_schedule("COIN", dates)
    coiw_earnings = EarningsController(events)
    conl_earnings = EarningsController(events)
    sgov_returns = sgov_daily_returns(dates)
    dividends = DividendEngine()

    portfolio = IndependentPairPortfolio(a_symbol="COIW", b_symbol="CONL")
    portfolio.initialize(coiw_data.iloc[0]["Close"], conl_data.iloc[0]["Close"])

    equity_curve = [
        portfolio.current_value(
            coiw_data.iloc[0]["Close"],
            conl_data.iloc[0]["Close"],
        )
    ]
    days_in_sgov = 0
    split_state_days = 0

    for position in range(1, len(dates)):
        date = dates[position]
        coiw_close = coiw_data.iloc[position]["Close"]
        conl_close = conl_data.iloc[position]["Close"]
        eligible_coiw_shares = portfolio.a_sleeve.shares
        daily_sgov_return = sgov_returns.iloc[position]

        portfolio.a_sleeve.accrue_sgov(daily_sgov_return)
        portfolio.b_sleeve.accrue_sgov(daily_sgov_return)

        exit_event = coiw_earnings.event_for_exit(date)
        if exit_event is not None:
            coiw_traded = portfolio.a_sleeve.sell_to_sgov(coiw_close)
            conl_traded = portfolio.b_sleeve.sell_to_sgov(conl_close)
            coiw_earnings.activate_exit(exit_event, coiw_traded)
            conl_earnings.activate_exit(exit_event, conl_traded)
        else:
            process_sleeve_day(
                dividends,
                coiw_earnings,
                portfolio.a_sleeve,
                "A",
                date,
                coiw_signals.iloc[position]["Signal"],
                coiw_signals.iloc[position - 1]["Signal"],
                coiw_close,
            )
            process_sleeve_day(
                dividends,
                conl_earnings,
                portfolio.b_sleeve,
                "B",
                date,
                conl_signals.iloc[position]["Signal"],
                conl_signals.iloc[position - 1]["Signal"],
                conl_close,
            )

        dividends.apply_independent_dividend(
            portfolio,
            eligible_a_shares=eligible_coiw_shares,
            dividend_per_share=coiw_data.iloc[position]["Dividends"],
            a_price=coiw_close,
            b_price=conl_close,
        )

        if portfolio.a_sleeve.in_sgov or portfolio.b_sleeve.in_sgov:
            days_in_sgov += 1
        if portfolio.a_sleeve.in_sgov != portfolio.b_sleeve.in_sgov:
            split_state_days += 1

        equity_curve.append(portfolio.current_value(coiw_close, conl_close))

    snapshot = portfolio.snapshot(
        coiw_data.iloc[-1]["Close"],
        conl_data.iloc[-1]["Close"],
    )
    final_value = float(snapshot["current_value"])
    row = {
        "Pair": PAIR,
        "Architecture": "independent_sleeves",
        "Final_Value": round(final_value, 6),
        "Return_Pct": round(
            (final_value - STARTING_CAPITAL) / STARTING_CAPITAL * 100,
            6,
        ),
        "Max_Drawdown": round(max_drawdown_percent(equity_curve), 6),
        "Trades": snapshot["trade_count"],
        "SGOV_Entries": snapshot["sgov_entries"],
        "Days_In_SGOV": days_in_sgov,
        "Dividends_Received": round(float(dividends.totals.received), 6),
    }
    diagnostics = {
        "split_state_days": split_state_days,
        "different_signal_days": int(
            (coiw_signals["Signal"] != conl_signals["Signal"]).sum()
        ),
        "coiw_earnings_exits": coiw_earnings.earnings_exit_count,
        "conl_earnings_exits": conl_earnings.earnings_exit_count,
    }
    return row, diagnostics


def load_pair_architecture_rows() -> list[dict[str, object]]:
    """Load the current pair and A-only comparison rows."""
    if not SOURCE_RESULTS_PATH.exists():
        raise FileNotFoundError(f"Required source not found: {SOURCE_RESULTS_PATH}")

    source = pd.read_csv(SOURCE_RESULTS_PATH)
    selections = [
        ("proportional", "pair_underlying_proportional"),
        ("a_only_reentry", "pair_underlying_a_only"),
    ]
    rows = []

    for reentry_mode, architecture in selections:
        matching = source[
            (source["Pair"] == PAIR)
            & (source["Model"] == "Underlying")
            & (source["Reentry_Mode"] == reentry_mode)
        ]
        if len(matching) != 1:
            raise AssertionError(
                f"Expected one Underlying/{reentry_mode} source row"
            )
        source_row = matching.iloc[0]
        rows.append(
            {
                "Pair": PAIR,
                "Architecture": architecture,
                "Final_Value": source_row["Final_Value"],
                "Return_Pct": source_row["Return_Pct"],
                "Max_Drawdown": source_row["Max_Drawdown"],
                "Trades": source_row["Trades"],
                "SGOV_Entries": source_row["SGOV_Entries"],
                "Days_In_SGOV": source_row["Days_In_SGOV"],
                "Dividends_Received": source_row["Dividends_Received"],
            }
        )
    return rows


def validate_results(
    results: pd.DataFrame,
    diagnostics: dict[str, int],
) -> None:
    """Validate comparison coverage, independence, and accounting."""
    assert list(results.columns) == OUTPUT_COLUMNS
    assert len(results) == 3
    assert not results.isna().any().any()
    assert results["Pair"].eq(PAIR).all()
    assert results["Final_Value"].gt(0).all()
    assert results["SGOV_Entries"].ge(0).all()
    assert diagnostics["coiw_earnings_exits"] > 0
    assert diagnostics["conl_earnings_exits"] > 0
    if diagnostics["different_signal_days"] == 0:
        assert diagnostics["split_state_days"] == 0

    independent = results[results["Architecture"] == "independent_sleeves"].iloc[0]
    expected_return = (
        (independent["Final_Value"] - STARTING_CAPITAL)
        / STARTING_CAPITAL
        * 100
    )
    assert abs(independent["Return_Pct"] - expected_return) < 0.000002
    assert independent["Dividends_Received"] > 0


def main() -> int:
    rows = load_pair_architecture_rows()
    independent_row, diagnostics = run_independent_architecture()
    rows.append(independent_row)
    results = pd.DataFrame(rows)[OUTPUT_COLUMNS]
    validate_results(results, diagnostics)
    results.to_csv(OUTPUT_PATH, index=False)

    print(results.to_string(index=False))
    print("\nDiagnostics:")
    print(f"Different signal days: {diagnostics['different_signal_days']}")
    print(f"Independent state days: {diagnostics['split_state_days']}")
    print(f"COIW earnings exits: {diagnostics['coiw_earnings_exits']}")
    print(f"CONL earnings exits: {diagnostics['conl_earnings_exits']}")
    print("\nValidation: PASS")
    print(f"Results saved to: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
