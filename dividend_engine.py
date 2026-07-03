"""Dividend accounting for income ETF A positions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from portfolio_engine import (
    MONEY_ZERO,
    IndependentPairPortfolio,
    PairPortfolio,
    SingleAssetSleeve,
    to_decimal,
)


@dataclass
class DividendTotals:
    """Track received, reinvested, and pending dividend cash."""

    received: Decimal = MONEY_ZERO
    reinvested_a: Decimal = MONEY_ZERO
    reinvested_b: Decimal = MONEY_ZERO
    pending_a: Decimal = MONEY_ZERO
    pending_b: Decimal = MONEY_ZERO


class DividendEngine:
    """Apply 50/50 dividend reinvestment without earnings logic."""

    def __init__(self) -> None:
        self.totals = DividendTotals()

    @staticmethod
    def _validate_inputs(
        eligible_a_shares: Decimal | float | int | str,
        dividend_per_share: Decimal | float | int | str,
    ) -> tuple[Decimal, Decimal]:
        shares = to_decimal(eligible_a_shares)
        dividend = to_decimal(dividend_per_share)
        if shares < 0:
            raise ValueError("eligible_a_shares cannot be negative")
        if dividend < 0:
            raise ValueError("dividend_per_share cannot be negative")
        return shares, dividend

    def apply_pair_dividend(
        self,
        portfolio: PairPortfolio,
        eligible_a_shares: Decimal | float | int | str,
        dividend_per_share: Decimal | float | int | str,
        a_price: Decimal | float | int | str,
        b_price: Decimal | float | int | str,
    ) -> Decimal:
        """Apply an A-side dividend to a jointly controlled pair."""
        shares, dividend = self._validate_inputs(
            eligible_a_shares,
            dividend_per_share,
        )
        dividend_cash = shares * dividend
        if dividend_cash == 0:
            return MONEY_ZERO

        a_price_decimal = PairPortfolio._validate_price(a_price, "a_price")
        b_price_decimal = PairPortfolio._validate_price(b_price, "b_price")
        half = dividend_cash / Decimal("2")
        self.totals.received += dividend_cash

        if portfolio.in_sgov:
            portfolio.sgov_value += dividend_cash
            self.totals.pending_a += half
            self.totals.pending_b += half
        else:
            portfolio.a_shares += half / a_price_decimal
            portfolio.b_shares += half / b_price_decimal
            self.totals.reinvested_a += half
            self.totals.reinvested_b += half

        return dividend_cash

    def buy_pair_from_sgov(
        self,
        portfolio: PairPortfolio,
        a_price: Decimal | float | int | str,
        b_price: Decimal | float | int | str,
    ) -> bool:
        """Re-enter a pair, preserving 50/50 allocation of pending dividends."""
        if not portfolio.in_sgov:
            return False

        a_price_decimal = PairPortfolio._validate_price(a_price, "a_price")
        b_price_decimal = PairPortfolio._validate_price(b_price, "b_price")
        pending = self.totals.pending_a + self.totals.pending_b
        portfolio.sgov_value -= pending

        traded = portfolio.buy_from_sgov(a_price_decimal, b_price_decimal)
        if not traded:
            portfolio.sgov_value += pending
            return False

        portfolio.a_shares += self.totals.pending_a / a_price_decimal
        portfolio.b_shares += self.totals.pending_b / b_price_decimal
        self.totals.reinvested_a += self.totals.pending_a
        self.totals.reinvested_b += self.totals.pending_b
        self.totals.pending_a = MONEY_ZERO
        self.totals.pending_b = MONEY_ZERO
        return True

    def apply_independent_dividend(
        self,
        portfolio: IndependentPairPortfolio,
        eligible_a_shares: Decimal | float | int | str,
        dividend_per_share: Decimal | float | int | str,
        a_price: Decimal | float | int | str,
        b_price: Decimal | float | int | str,
    ) -> Decimal:
        """Apply an MST dividend while preserving independent sleeve states."""
        shares, dividend = self._validate_inputs(
            eligible_a_shares,
            dividend_per_share,
        )
        dividend_cash = shares * dividend
        if dividend_cash == 0:
            return MONEY_ZERO

        a_price_decimal = PairPortfolio._validate_price(a_price, "a_price")
        b_price_decimal = PairPortfolio._validate_price(b_price, "b_price")
        half = dividend_cash / Decimal("2")
        self.totals.received += dividend_cash

        if portfolio.a_sleeve.in_sgov:
            portfolio.a_sleeve.sgov_value += half
            self.totals.pending_a += half
        else:
            portfolio.a_sleeve.shares += half / a_price_decimal
            self.totals.reinvested_a += half

        if portfolio.b_sleeve.in_sgov:
            portfolio.b_sleeve.sgov_value += half
            self.totals.pending_b += half
        else:
            portfolio.b_sleeve.shares += half / b_price_decimal
            self.totals.reinvested_b += half

        return dividend_cash

    def buy_independent_sleeve(
        self,
        sleeve: SingleAssetSleeve,
        side: str,
        price: Decimal | float | int | str,
    ) -> bool:
        """Re-enter one sleeve and reinvest its pending dividend portion."""
        if not sleeve.in_sgov:
            return False

        price_decimal = PairPortfolio._validate_price(price, "price")
        if side == "A":
            pending = self.totals.pending_a
        elif side == "B":
            pending = self.totals.pending_b
        else:
            raise ValueError("side must be A or B")

        sleeve.sgov_value -= pending
        traded = sleeve.buy_from_sgov(price_decimal)
        if not traded:
            sleeve.sgov_value += pending
            return False

        sleeve.shares += pending / price_decimal
        if side == "A":
            self.totals.reinvested_a += pending
            self.totals.pending_a = MONEY_ZERO
        else:
            self.totals.reinvested_b += pending
            self.totals.pending_b = MONEY_ZERO
        return True
