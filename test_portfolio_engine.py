"""Milestone 4 accounting tests for BUY -> SELL -> BUY cycles."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from portfolio_engine import (
    IndependentPairPortfolio,
    PairPortfolio,
    ReentryMode,
)


OUTPUT_PATH = Path("portfolio_engine_test_output.txt")


def assert_decimal_equal(actual: Decimal, expected: Decimal) -> None:
    assert actual == expected, f"expected {expected}, got {actual}"


def test_pair_cycle(reentry_mode: ReentryMode) -> list[str]:
    portfolio = PairPortfolio("A", "B", reentry_mode=reentry_mode)
    portfolio.initialize(a_price="10", b_price="5")

    assert_decimal_equal(portfolio.a_shares, Decimal("3.5"))
    assert_decimal_equal(portfolio.b_shares, Decimal("3"))
    assert_decimal_equal(portfolio.current_value("10", "5"), Decimal("50"))

    assert portfolio.process_signal("BUY", "10", "5") is False
    assert portfolio.process_signal("SELL", "12", "4") is True
    assert_decimal_equal(portfolio.sgov_value, Decimal("54"))
    assert_decimal_equal(portfolio.current_value("12", "4"), Decimal("54"))

    yield_amount = portfolio.accrue_sgov("0.01")
    assert_decimal_equal(yield_amount, Decimal("0.54"))
    assert_decimal_equal(portfolio.sgov_value, Decimal("54.54"))

    assert portfolio.process_signal("BUY", "11", "6") is True
    assert_decimal_equal(portfolio.sgov_value, Decimal("0"))
    assert_decimal_equal(portfolio.current_value("11", "6"), Decimal("54.54"))

    if reentry_mode == ReentryMode.PROPORTIONAL:
        assert_decimal_equal(portfolio.a_shares * Decimal("11"), Decimal("42.420"))
        assert_decimal_equal(portfolio.b_shares * Decimal("6"), Decimal("12.120"))
    else:
        assert_decimal_equal(portfolio.a_shares * Decimal("11"), Decimal("38.178"))
        assert_decimal_equal(portfolio.b_shares * Decimal("6"), Decimal("16.362"))

    snapshot = portfolio.snapshot("11", "6")
    assert snapshot["trade_count"] == 2
    assert snapshot["sgov_entries"] == 1
    assert snapshot["sgov_exits"] == 1

    return [
        f"{reentry_mode.value}: PASS",
        f"  ending value: USD {snapshot['current_value']}",
        f"  A shares: {snapshot['a_shares']}",
        f"  B shares: {snapshot['b_shares']}",
        f"  trades: {snapshot['trade_count']}",
        f"  SGOV entries/exits: {snapshot['sgov_entries']}/{snapshot['sgov_exits']}",
    ]


def test_independent_mst_xxrp() -> list[str]:
    portfolio = IndependentPairPortfolio()
    portfolio.initialize(a_price="10", b_price="5")

    assert_decimal_equal(portfolio.current_value("10", "5"), Decimal("50"))
    assert portfolio.a_sleeve.process_signal("SELL", "12") is True
    assert portfolio.b_sleeve.in_sgov is False
    assert_decimal_equal(portfolio.a_sleeve.sgov_value, Decimal("42"))
    assert_decimal_equal(portfolio.b_sleeve.current_value("4"), Decimal("12"))

    yield_amount = portfolio.a_sleeve.accrue_sgov("0.01")
    assert_decimal_equal(yield_amount, Decimal("0.42"))
    assert portfolio.a_sleeve.process_signal("BUY", "11") is True
    assert portfolio.b_sleeve.trade_count == 0

    snapshot = portfolio.snapshot("11", "4")
    assert_decimal_equal(snapshot["current_value"], Decimal("54.42"))
    assert snapshot["trade_count"] == 2
    assert snapshot["sgov_entries"] == 1
    assert snapshot["sgov_exits"] == 1

    return [
        "independent MST/XXRP: PASS",
        f"  ending value: USD {snapshot['current_value']}",
        f"  MST shares: {snapshot['a_shares']}",
        f"  XXRP shares: {snapshot['b_shares']}",
        f"  trades: {snapshot['trade_count']}",
        "  XXRP remained invested while MST rotated through SGOV",
    ]


def main() -> int:
    lines = ["Milestone 4 Portfolio Engine Tests", ""]
    lines.extend(test_pair_cycle(ReentryMode.PROPORTIONAL))
    lines.append("")
    lines.extend(test_pair_cycle(ReentryMode.FIXED_70_30))
    lines.append("")
    lines.extend(test_independent_mst_xxrp())
    lines.extend(["", "All accounting assertions: PASS"])

    output = "\n".join(lines) + "\n"
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    print(output, end="")
    print(f"Test output saved to: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
