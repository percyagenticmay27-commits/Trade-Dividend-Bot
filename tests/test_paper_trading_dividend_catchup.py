from __future__ import annotations

import pandas as pd

from paper_trading_engine import (
    _dividend_window_starts,
    _unprocessed_dividend_payments,
)


def test_zero_income_open_pair_recovers_from_latest_income_sleeve_buy() -> None:
    state = {
        "last_processed_date": "2026-08-11",
        "pairs": {
            "AMDW / AMDL": {
                "a_shares": 4.0,
                "b_shares": 3.0,
                "total_dividends_received": 0.0,
            }
        },
    }
    rows = [
        {
            "Date": "2026-06-18",
            "Pair": "AMDW / AMDL",
            "Ticker": "AMDW",
            "Action": "PAPER_BUY_OPEN",
        }
    ]

    starts = _dividend_window_starts(state, rows)

    assert starts["AMDW / AMDL"] == pd.Timestamp("2026-06-18")


def test_existing_distribution_uses_last_processed_date_not_purchase_date() -> None:
    state = {
        "last_processed_date": "2026-08-11",
        "pairs": {
            "AMDW / AMDL": {
                "a_shares": 4.0,
                "b_shares": 3.0,
                "total_dividends_received": 2.0,
            }
        },
    }
    rows = [
        {
            "Date": "2026-06-18",
            "Pair": "AMDW / AMDL",
            "Ticker": "AMDW",
            "Action": "PAPER_BUY_OPEN",
        },
        {
            "Date": "2026-08-10",
            "Pair": "AMDW / AMDL",
            "Ticker": "AMDW",
            "Action": "PAPER_DIVIDEND_RECEIVED",
        },
    ]

    starts = _dividend_window_starts(state, rows)

    assert starts["AMDW / AMDL"] == pd.Timestamp("2026-08-11")


def test_catchup_returns_every_distribution_after_watermark_through_as_of() -> None:
    frame = pd.DataFrame(
        {
            "Close": [10.0, 10.5, 11.0, 11.5],
            "Dividends": [0.0, 1.25, 0.0, 0.75],
        },
        index=pd.DatetimeIndex([
            "2026-08-07",
            "2026-08-10",
            "2026-08-11",
            "2026-08-12",
        ]),
    )

    payments = _unprocessed_dividend_payments(
        frame,
        after=pd.Timestamp("2026-08-07"),
        through=pd.Timestamp("2026-08-12"),
    )

    assert payments == [
        (pd.Timestamp("2026-08-10"), 1.25),
        (pd.Timestamp("2026-08-12"), 0.75),
    ]


def test_watermark_date_is_exclusive_to_prevent_duplicate_income() -> None:
    frame = pd.DataFrame(
        {"Close": [10.0, 10.5], "Dividends": [1.25, 0.75]},
        index=pd.DatetimeIndex(["2026-08-10", "2026-08-11"]),
    )

    payments = _unprocessed_dividend_payments(
        frame,
        after=pd.Timestamp("2026-08-10"),
        through=pd.Timestamp("2026-08-11"),
    )

    assert payments == [(pd.Timestamp("2026-08-11"), 0.75)]
