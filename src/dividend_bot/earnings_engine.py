"""Earnings-date scheduling and forced-exit state management."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


EARNINGS_DIR = Path("earnings_data")


@dataclass(frozen=True)
class EarningsEvent:
    earnings_date: pd.Timestamp
    exit_date: pd.Timestamp
    reentry_start_date: pd.Timestamp


def load_earnings_dates(
    symbol: str,
    earnings_dir: Path = EARNINGS_DIR,
) -> pd.DatetimeIndex:
    """Load cached earnings dates for one underlying."""
    path = earnings_dir / f"{symbol}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Earnings cache not found for {symbol}: {path}")

    data = pd.read_csv(path, parse_dates=["earnings_date"])
    return pd.DatetimeIndex(data["earnings_date"].dropna()).normalize().unique()


def build_earnings_schedule(
    earnings_dates: pd.DatetimeIndex | list[pd.Timestamp],
    trading_dates: pd.DatetimeIndex | list[pd.Timestamp],
) -> list[EarningsEvent]:
    """Map each earnings date to its previous and next trading dates."""
    trading_index = pd.DatetimeIndex(trading_dates).normalize().unique().sort_values()
    events = []

    for raw_date in pd.DatetimeIndex(earnings_dates).normalize().unique().sort_values():
        previous_dates = trading_index[trading_index < raw_date]
        following_dates = trading_index[trading_index > raw_date]
        if previous_dates.empty or following_dates.empty:
            continue

        events.append(
            EarningsEvent(
                earnings_date=raw_date,
                exit_date=previous_dates[-1],
                reentry_start_date=following_dates[0],
            )
        )

    return events


def load_earnings_schedule(
    symbol: str,
    trading_dates: pd.DatetimeIndex | list[pd.Timestamp],
) -> list[EarningsEvent]:
    """Load cached dates and build the symbol's trading-day schedule."""
    return build_earnings_schedule(load_earnings_dates(symbol), trading_dates)


class EarningsController:
    """Track forced-exit and post-earnings re-entry state."""

    def __init__(self, events: list[EarningsEvent]) -> None:
        self._events_by_exit = {event.exit_date: event for event in events}
        self.active_event: EarningsEvent | None = None
        self.earnings_exit_count = 0

    def event_for_exit(self, date: pd.Timestamp) -> EarningsEvent | None:
        return self._events_by_exit.get(pd.Timestamp(date).normalize())

    def activate_exit(self, event: EarningsEvent, traded: bool) -> None:
        """Start or refresh an earnings lock and count an actual forced exit."""
        self.active_event = event
        if traded:
            self.earnings_exit_count += 1

    @property
    def is_blocked(self) -> bool:
        return self.active_event is not None

    def can_reenter(self, date: pd.Timestamp, signal: str) -> bool:
        """Return true when the lock is post-earnings and signal is BUY."""
        if self.active_event is None:
            return False
        normalized_date = pd.Timestamp(date).normalize()
        return (
            normalized_date >= self.active_event.reentry_start_date
            and signal.upper() == "BUY"
        )

    def complete_reentry(self) -> None:
        self.active_event = None
