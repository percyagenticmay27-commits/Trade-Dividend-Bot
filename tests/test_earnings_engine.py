"""Milestone 7 earnings schedule and accounting validation."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pandas as pd

from dividend_engine import DividendEngine
from earnings_engine import EarningsController, build_earnings_schedule
from portfolio_engine import IndependentPairPortfolio, PairPortfolio


OUTPUT_PATH = Path("earnings_engine_test_output.txt")


def synthetic_schedule():
    trading_dates = pd.DatetimeIndex(
        [
            "2026-01-05",
            "2026-01-06",
            "2026-01-07",
            "2026-01-08",
            "2026-01-09",
            "2026-01-12",
        ]
    )
    events = build_earnings_schedule(
        pd.DatetimeIndex(["2026-01-08"]),
        trading_dates,
    )
    assert len(events) == 1
    event = events[0]
    assert event.exit_date == pd.Timestamp("2026-01-07")
    assert event.reentry_start_date == pd.Timestamp("2026-01-09")
    return event


def test_standard_pair_exit_and_reentry() -> list[str]:
    event = synthetic_schedule()
    controller = EarningsController([event])
    portfolio = PairPortfolio("A", "B")
    portfolio.initialize("10", "5")
    dividends = DividendEngine()

    eligible_shares = portfolio.a_shares
    traded = portfolio.sell_to_sgov("12", "4")
    controller.activate_exit(event, traded)

    assert traded is True
    assert controller.earnings_exit_count == 1
    assert portfolio.in_sgov is True
    assert portfolio.sgov_value == Decimal("54")

    dividends.apply_pair_dividend(
        portfolio,
        eligible_a_shares=eligible_shares,
        dividend_per_share="1",
        a_price="12",
        b_price="4",
    )
    assert portfolio.sgov_value == Decimal("57.5")
    assert dividends.totals.pending_a == Decimal("1.75")
    assert dividends.totals.pending_b == Decimal("1.75")

    assert controller.can_reenter(pd.Timestamp("2026-01-08"), "BUY") is False
    assert controller.can_reenter(pd.Timestamp("2026-01-09"), "HOLD") is False
    assert controller.can_reenter(pd.Timestamp("2026-01-12"), "BUY") is True

    dividends.buy_pair_from_sgov(portfolio, "11", "6")
    controller.complete_reentry()
    assert portfolio.current_value("11", "6") == Decimal("57.50")
    assert portfolio.in_sgov is False
    assert controller.is_blocked is False
    return ["standard exit/re-entry and pending dividends: PASS"]


def test_mst_xxrp_independence() -> list[str]:
    event = synthetic_schedule()
    controller = EarningsController([event])
    portfolio = IndependentPairPortfolio()
    portfolio.initialize("10", "5")
    original_xxrp_shares = portfolio.b_sleeve.shares

    traded = portfolio.a_sleeve.sell_to_sgov("12")
    controller.activate_exit(event, traded)

    assert portfolio.a_sleeve.in_sgov is True
    assert portfolio.b_sleeve.in_sgov is False
    assert portfolio.b_sleeve.shares == original_xxrp_shares
    assert controller.earnings_exit_count == 1

    assert controller.can_reenter(pd.Timestamp("2026-01-09"), "BUY") is True
    portfolio.a_sleeve.buy_from_sgov("11")
    controller.complete_reentry()
    assert portfolio.b_sleeve.shares == original_xxrp_shares
    assert portfolio.current_value("11", "5") == Decimal("57")
    return ["MST exits on MSTR while XXRP remains independent: PASS"]


def main() -> int:
    lines = ["Milestone 7 Earnings Engine Tests", ""]
    lines.extend(test_standard_pair_exit_and_reentry())
    lines.extend(test_mst_xxrp_independence())
    lines.extend(["", "All earnings accounting assertions: PASS"])

    output = "\n".join(lines) + "\n"
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    print(output, end="")
    print(f"Test output saved to: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
