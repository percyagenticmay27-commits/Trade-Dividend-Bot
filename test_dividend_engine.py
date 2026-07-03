"""Milestone 6 dividend accounting tests."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from dividend_engine import DividendEngine
from portfolio_engine import IndependentPairPortfolio, PairPortfolio, ReentryMode


OUTPUT_PATH = Path("dividend_engine_test_output.txt")


def assert_decimal_equal(actual: Decimal, expected: Decimal) -> None:
    assert actual == expected, f"expected {expected}, got {actual}"


def test_active_reinvestment() -> list[str]:
    portfolio = PairPortfolio("A", "B")
    portfolio.initialize("10", "5")
    dividends = DividendEngine()

    received = dividends.apply_pair_dividend(
        portfolio,
        eligible_a_shares=portfolio.a_shares,
        dividend_per_share="1",
        a_price="10",
        b_price="5",
    )

    assert_decimal_equal(received, Decimal("3.5"))
    assert_decimal_equal(portfolio.a_shares, Decimal("3.675"))
    assert_decimal_equal(portfolio.b_shares, Decimal("3.35"))
    assert_decimal_equal(dividends.totals.reinvested_a, Decimal("1.75"))
    assert_decimal_equal(dividends.totals.reinvested_b, Decimal("1.75"))
    assert_decimal_equal(portfolio.current_value("10", "5"), Decimal("53.50"))
    return ["active 50/50 reinvestment: PASS"]


def test_pending_sgov_reinvestment() -> list[str]:
    portfolio = PairPortfolio(
        "A",
        "B",
        reentry_mode=ReentryMode.FIXED_70_30,
    )
    portfolio.initialize("10", "5")
    dividends = DividendEngine()
    eligible_shares = portfolio.a_shares

    portfolio.sell_to_sgov("12", "4")
    dividends.apply_pair_dividend(
        portfolio,
        eligible_a_shares=eligible_shares,
        dividend_per_share="1",
        a_price="12",
        b_price="4",
    )

    assert_decimal_equal(portfolio.sgov_value, Decimal("57.5"))
    assert_decimal_equal(dividends.totals.pending_a, Decimal("1.75"))
    assert_decimal_equal(dividends.totals.pending_b, Decimal("1.75"))

    dividends.buy_pair_from_sgov(portfolio, "11", "6")
    assert_decimal_equal(portfolio.current_value("11", "6"), Decimal("57.50"))
    assert_decimal_equal(portfolio.a_shares * Decimal("11"), Decimal("39.55"))
    assert_decimal_equal(portfolio.b_shares * Decimal("6"), Decimal("17.95"))
    assert_decimal_equal(dividends.totals.pending_a, Decimal("0"))
    assert_decimal_equal(dividends.totals.pending_b, Decimal("0"))
    return ["SGOV pending dividend reinvestment: PASS"]


def test_independent_sleeves() -> list[str]:
    portfolio = IndependentPairPortfolio()
    portfolio.initialize("10", "5")
    dividends = DividendEngine()
    eligible_shares = portfolio.a_sleeve.shares

    portfolio.a_sleeve.sell_to_sgov("12")
    dividends.apply_independent_dividend(
        portfolio,
        eligible_a_shares=eligible_shares,
        dividend_per_share="1",
        a_price="12",
        b_price="5",
    )

    assert_decimal_equal(dividends.totals.received, Decimal("3.5"))
    assert_decimal_equal(portfolio.a_sleeve.sgov_value, Decimal("43.75"))
    assert_decimal_equal(portfolio.b_sleeve.shares, Decimal("3.35"))
    assert_decimal_equal(dividends.totals.pending_a, Decimal("1.75"))
    assert_decimal_equal(dividends.totals.reinvested_b, Decimal("1.75"))

    dividends.buy_independent_sleeve(portfolio.a_sleeve, "A", "11")
    assert_decimal_equal(portfolio.a_sleeve.shares, Decimal("43.75") / Decimal("11"))
    assert_decimal_equal(dividends.totals.reinvested_a, Decimal("1.75"))
    return ["independent MST/XXRP dividend handling: PASS"]


def main() -> int:
    lines = ["Milestone 6 Dividend Engine Tests", ""]
    lines.extend(test_active_reinvestment())
    lines.extend(test_pending_sgov_reinvestment())
    lines.extend(test_independent_sleeves())
    lines.extend(["", "All dividend accounting assertions: PASS"])

    output = "\n".join(lines) + "\n"
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    print(output, end="")
    print(f"Test output saved to: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
