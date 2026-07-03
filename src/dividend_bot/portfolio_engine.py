"""Accounting engine for paired ETF allocations and independent special sleeves."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


MONEY_ZERO = Decimal("0")
DEFAULT_CAPITAL = Decimal("50")
DEFAULT_A_WEIGHT = Decimal("0.70")
DEFAULT_B_WEIGHT = Decimal("0.30")


def to_decimal(value: Decimal | float | int | str) -> Decimal:
    """Convert numeric input to Decimal without binary-float artifacts."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class ReentryMode(str, Enum):
    PROPORTIONAL = "proportional"
    FIXED_70_30 = "fixed_70_30"
    A_ONLY = "a_only_reentry"


@dataclass
class PairPortfolio:
    """A pair that jointly rotates between A/B and SGOV."""

    a_symbol: str
    b_symbol: str
    reentry_mode: ReentryMode = ReentryMode.PROPORTIONAL
    starting_capital: Decimal = DEFAULT_CAPITAL
    a_weight: Decimal = DEFAULT_A_WEIGHT
    b_weight: Decimal = DEFAULT_B_WEIGHT
    a_shares: Decimal = field(default=MONEY_ZERO, init=False)
    b_shares: Decimal = field(default=MONEY_ZERO, init=False)
    sgov_value: Decimal = field(default=MONEY_ZERO, init=False)
    trade_count: int = field(default=0, init=False)
    sgov_entries: int = field(default=0, init=False)
    sgov_exits: int = field(default=0, init=False)
    in_sgov: bool = field(default=False, init=False)
    initialized: bool = field(default=False, init=False)
    _restoration_a_weight: Decimal = field(
        default=DEFAULT_A_WEIGHT,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self.starting_capital = to_decimal(self.starting_capital)
        self.a_weight = to_decimal(self.a_weight)
        self.b_weight = to_decimal(self.b_weight)
        if self.starting_capital <= 0:
            raise ValueError("starting_capital must be positive")
        if self.a_weight + self.b_weight != Decimal("1"):
            raise ValueError("A and B weights must sum to 1")

    @staticmethod
    def _validate_price(price: Decimal | float | int | str, name: str) -> Decimal:
        value = to_decimal(price)
        if value <= 0:
            raise ValueError(f"{name} must be positive")
        return value

    def initialize(
        self,
        a_price: Decimal | float | int | str,
        b_price: Decimal | float | int | str,
    ) -> None:
        """Fund the pair at its default allocation; initial buys are not trades."""
        if self.initialized:
            raise RuntimeError("portfolio is already initialized")

        a_price_decimal = self._validate_price(a_price, "a_price")
        b_price_decimal = self._validate_price(b_price, "b_price")
        self.a_shares = self.starting_capital * self.a_weight / a_price_decimal
        self.b_shares = self.starting_capital * self.b_weight / b_price_decimal
        self.initialized = True

    def current_value(
        self,
        a_price: Decimal | float | int | str,
        b_price: Decimal | float | int | str,
    ) -> Decimal:
        """Return current A/B plus SGOV value."""
        a_price_decimal = self._validate_price(a_price, "a_price")
        b_price_decimal = self._validate_price(b_price, "b_price")
        return (
            self.a_shares * a_price_decimal
            + self.b_shares * b_price_decimal
            + self.sgov_value
        )

    def sell_to_sgov(
        self,
        a_price: Decimal | float | int | str,
        b_price: Decimal | float | int | str,
    ) -> bool:
        """Liquidate A and B and move all proceeds into SGOV."""
        if not self.initialized:
            raise RuntimeError("portfolio must be initialized before trading")
        if self.in_sgov:
            return False

        a_price_decimal = self._validate_price(a_price, "a_price")
        b_price_decimal = self._validate_price(b_price, "b_price")
        a_value = self.a_shares * a_price_decimal
        b_value = self.b_shares * b_price_decimal
        proceeds = a_value + b_value

        if proceeds > 0:
            self._restoration_a_weight = a_value / proceeds

        self.a_shares = MONEY_ZERO
        self.b_shares = MONEY_ZERO
        self.sgov_value = proceeds
        self.in_sgov = True
        self.trade_count += 1
        self.sgov_entries += 1
        return True

    def accrue_sgov(self, daily_yield_rate: Decimal | float | int | str) -> Decimal:
        """Accrue one day of SGOV yield and return the yield amount."""
        rate = to_decimal(daily_yield_rate)
        if rate < Decimal("-1"):
            raise ValueError("daily_yield_rate cannot be below -100%")
        if not self.in_sgov:
            return MONEY_ZERO

        yield_amount = self.sgov_value * rate
        self.sgov_value += yield_amount
        return yield_amount

    def buy_from_sgov(
        self,
        a_price: Decimal | float | int | str,
        b_price: Decimal | float | int | str,
    ) -> bool:
        """Exit SGOV and restore A/B according to the selected re-entry mode."""
        if not self.initialized:
            raise RuntimeError("portfolio must be initialized before trading")
        if not self.in_sgov:
            return False

        a_price_decimal = self._validate_price(a_price, "a_price")
        b_price_decimal = self._validate_price(b_price, "b_price")

        if self.reentry_mode == ReentryMode.PROPORTIONAL:
            a_restore_weight = self._restoration_a_weight
        elif self.reentry_mode == ReentryMode.FIXED_70_30:
            a_restore_weight = self.a_weight
        elif self.reentry_mode == ReentryMode.A_ONLY:
            a_restore_weight = Decimal("1")
        else:
            raise ValueError(f"unsupported re-entry mode: {self.reentry_mode}")

        b_restore_weight = Decimal("1") - a_restore_weight
        capital = self.sgov_value
        self.a_shares = capital * a_restore_weight / a_price_decimal
        self.b_shares = capital * b_restore_weight / b_price_decimal
        self.sgov_value = MONEY_ZERO
        self.in_sgov = False
        self.trade_count += 1
        self.sgov_exits += 1
        return True

    def process_signal(
        self,
        signal: str,
        a_price: Decimal | float | int | str,
        b_price: Decimal | float | int | str,
    ) -> bool:
        """Apply BUY/SELL/HOLD to the portfolio and return whether it traded."""
        normalized = signal.upper()
        if normalized == "SELL":
            return self.sell_to_sgov(a_price, b_price)
        if normalized == "BUY":
            return self.buy_from_sgov(a_price, b_price)
        if normalized == "HOLD":
            return False
        raise ValueError(f"unsupported signal: {signal}")

    def snapshot(
        self,
        a_price: Decimal | float | int | str,
        b_price: Decimal | float | int | str,
    ) -> dict[str, object]:
        """Return the required accounting state."""
        return {
            "current_value": self.current_value(a_price, b_price),
            "sgov_value": self.sgov_value,
            "a_shares": self.a_shares,
            "b_shares": self.b_shares,
            "trade_count": self.trade_count,
            "sgov_entries": self.sgov_entries,
            "sgov_exits": self.sgov_exits,
        }


@dataclass
class SingleAssetSleeve:
    """One independently signaled asset that rotates into its own SGOV balance."""

    symbol: str
    starting_capital: Decimal
    shares: Decimal = field(default=MONEY_ZERO, init=False)
    sgov_value: Decimal = field(default=MONEY_ZERO, init=False)
    trade_count: int = field(default=0, init=False)
    sgov_entries: int = field(default=0, init=False)
    sgov_exits: int = field(default=0, init=False)
    in_sgov: bool = field(default=False, init=False)
    initialized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self.starting_capital = to_decimal(self.starting_capital)
        if self.starting_capital <= 0:
            raise ValueError("starting_capital must be positive")

    def initialize(self, price: Decimal | float | int | str) -> None:
        price_decimal = PairPortfolio._validate_price(price, "price")
        if self.initialized:
            raise RuntimeError("sleeve is already initialized")
        self.shares = self.starting_capital / price_decimal
        self.initialized = True

    def current_value(self, price: Decimal | float | int | str) -> Decimal:
        price_decimal = PairPortfolio._validate_price(price, "price")
        return self.shares * price_decimal + self.sgov_value

    def sell_to_sgov(self, price: Decimal | float | int | str) -> bool:
        if not self.initialized:
            raise RuntimeError("sleeve must be initialized before trading")
        if self.in_sgov:
            return False
        price_decimal = PairPortfolio._validate_price(price, "price")
        self.sgov_value = self.shares * price_decimal
        self.shares = MONEY_ZERO
        self.in_sgov = True
        self.trade_count += 1
        self.sgov_entries += 1
        return True

    def accrue_sgov(self, daily_yield_rate: Decimal | float | int | str) -> Decimal:
        rate = to_decimal(daily_yield_rate)
        if rate < Decimal("-1"):
            raise ValueError("daily_yield_rate cannot be below -100%")
        if not self.in_sgov:
            return MONEY_ZERO
        yield_amount = self.sgov_value * rate
        self.sgov_value += yield_amount
        return yield_amount

    def buy_from_sgov(self, price: Decimal | float | int | str) -> bool:
        if not self.initialized:
            raise RuntimeError("sleeve must be initialized before trading")
        if not self.in_sgov:
            return False
        price_decimal = PairPortfolio._validate_price(price, "price")
        self.shares = self.sgov_value / price_decimal
        self.sgov_value = MONEY_ZERO
        self.in_sgov = False
        self.trade_count += 1
        self.sgov_exits += 1
        return True

    def process_signal(
        self,
        signal: str,
        price: Decimal | float | int | str,
    ) -> bool:
        normalized = signal.upper()
        if normalized == "SELL":
            return self.sell_to_sgov(price)
        if normalized == "BUY":
            return self.buy_from_sgov(price)
        if normalized == "HOLD":
            return False
        raise ValueError(f"unsupported signal: {signal}")


@dataclass
class IndependentPairPortfolio:
    """MST/XXRP pair with independently controlled 70% and 30% sleeves."""

    a_symbol: str = "MST"
    b_symbol: str = "XXRP"
    starting_capital: Decimal = DEFAULT_CAPITAL
    a_sleeve: SingleAssetSleeve = field(init=False)
    b_sleeve: SingleAssetSleeve = field(init=False)

    def __post_init__(self) -> None:
        capital = to_decimal(self.starting_capital)
        self.starting_capital = capital
        self.a_sleeve = SingleAssetSleeve(
            self.a_symbol,
            capital * DEFAULT_A_WEIGHT,
        )
        self.b_sleeve = SingleAssetSleeve(
            self.b_symbol,
            capital * DEFAULT_B_WEIGHT,
        )

    def initialize(
        self,
        a_price: Decimal | float | int | str,
        b_price: Decimal | float | int | str,
    ) -> None:
        self.a_sleeve.initialize(a_price)
        self.b_sleeve.initialize(b_price)

    def current_value(
        self,
        a_price: Decimal | float | int | str,
        b_price: Decimal | float | int | str,
    ) -> Decimal:
        return self.a_sleeve.current_value(a_price) + self.b_sleeve.current_value(
            b_price
        )

    def snapshot(
        self,
        a_price: Decimal | float | int | str,
        b_price: Decimal | float | int | str,
    ) -> dict[str, object]:
        return {
            "current_value": self.current_value(a_price, b_price),
            "sgov_value": self.a_sleeve.sgov_value + self.b_sleeve.sgov_value,
            "a_shares": self.a_sleeve.shares,
            "b_shares": self.b_sleeve.shares,
            "trade_count": self.a_sleeve.trade_count + self.b_sleeve.trade_count,
            "sgov_entries": self.a_sleeve.sgov_entries
            + self.b_sleeve.sgov_entries,
            "sgov_exits": self.a_sleeve.sgov_exits + self.b_sleeve.sgov_exits,
        }
