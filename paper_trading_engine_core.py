"""PAPER ONLY daily simulator for the Strength Weighted Hybrid strategy."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd

from indicators import apply_approved_signal_rules
from paper_portfolio_config import (
    INDEPENDENT_SLEEVES,
    INITIAL_A_WEIGHT,
    INITIAL_B_WEIGHT,
    PAIR_MANAGED,
    PAPER_PAIRS,
    TOTAL_PAPER_CAPITAL,
    validate_paper_config,
)


PAPER_LABEL = "PAPER ONLY - NO REAL TRADES EXECUTED"
STATE_PATH = Path("paper_state.json")
LOG_PATH = Path("paper_trade_log.csv")
REPORT_PATH = Path("daily_paper_report.md")
COMPARISON_PATH = Path("initialization_comparison.md")
EARNINGS_DIR = Path("earnings_data")
LOG_COLUMNS = [
    "Date", "Pair", "Sleeve", "Signal", "Action", "Ticker",
    "Shares", "Price", "Paper_Value", "Reason",
]


class MarketDataProvider(Protocol):
    def fetch(self, symbols: set[str]) -> dict[str, pd.DataFrame]: ...


class YahooMarketDataProvider:
    """Download enough adjusted daily history for EMA50 and RSI14."""

    def fetch(self, symbols: set[str]) -> dict[str, pd.DataFrame]:
        import yfinance as yf

        frames = {}
        for symbol in sorted(symbols):
            history = yf.Ticker(symbol).history(
                period="1y", interval="1d", auto_adjust=False, actions=True
            )
            if history.empty:
                raise ValueError(f"No Yahoo Finance data returned for {symbol}")
            history.index = pd.DatetimeIndex(history.index).tz_localize(None).normalize()
            if "Adj Close" not in history:
                history["Adj Close"] = history["Close"]
            if "Dividends" not in history:
                history["Dividends"] = 0.0
            frames[symbol] = history.sort_index()
        return frames


@dataclass
class PaperTradingEngine:
    provider: MarketDataProvider
    state_path: Path = STATE_PATH
    log_path: Path = LOG_PATH
    report_path: Path = REPORT_PATH
    comparison_path: Path = COMPARISON_PATH
    earnings_dir: Path = EARNINGS_DIR

    def required_symbols(self) -> set[str]:
        symbols = {"SGOV"}
        for config in PAPER_PAIRS.values():
            symbols.update(
                [config["a"], config["b"], config["a_signal"], config["b_signal"]]
            )
        return symbols

    @staticmethod
    def common_as_of(frames: dict[str, pd.DataFrame]) -> pd.Timestamp:
        return min(frame.index.max() for frame in frames.values())

    @staticmethod
    def price(frame: pd.DataFrame, date: pd.Timestamp) -> float:
        eligible = frame.loc[:date]
        if eligible.empty:
            raise ValueError(f"No price available on or before {date.date()}")
        return float(eligible.iloc[-1]["Close"])

    @staticmethod
    def signal(frame: pd.DataFrame, date: pd.Timestamp) -> str:
        signals = apply_approved_signal_rules(frame.loc[:date])
        return str(signals.iloc[-1]["Signal"])

    def load_earnings(self, symbol: str | None) -> pd.DatetimeIndex:
        if symbol is None:
            return pd.DatetimeIndex([])
        path = self.earnings_dir / f"{symbol}.csv"
        if not path.exists():
            return pd.DatetimeIndex([])
        data = pd.read_csv(path, parse_dates=["earnings_date"])
        return pd.DatetimeIndex(data["earnings_date"].dropna()).normalize().sort_values()

    @staticmethod
    def earnings_status(
        as_of: pd.Timestamp,
        earnings_dates: pd.DatetimeIndex,
    ) -> dict[str, str | bool | None]:
        future = earnings_dates[earnings_dates >= as_of]
        if future.empty:
            return {"earnings_date": None, "exit_date": None, "exit_now": False, "warning": ""}
        earnings_date = pd.Timestamp(future[0]).normalize()
        exit_date = earnings_date - pd.offsets.BDay(1)
        next_day = as_of + pd.offsets.BDay(1)
        return {
            "earnings_date": earnings_date.strftime("%Y-%m-%d"),
            "exit_date": exit_date.strftime("%Y-%m-%d"),
            "exit_now": as_of.normalize() == exit_date,
            "warning": (
                f"Exit day is tomorrow ({exit_date.date()}) before earnings "
                f"on {earnings_date.date()}."
                if next_day.normalize() == exit_date else ""
            ),
        }

    def initial_state(
        self,
        frames: dict[str, pd.DataFrame],
        as_of: pd.Timestamp,
    ) -> tuple[dict, list[dict]]:
        validate_paper_config()
        state = {
            "paper_only": True,
            "notice": PAPER_LABEL,
            "version": 2,
            "as_of_date": as_of.strftime("%Y-%m-%d"),
            "last_processed_date": as_of.strftime("%Y-%m-%d"),
            "starting_capital": TOTAL_PAPER_CAPITAL,
            "pairs": {},
        }
        logs = []
        for pair, config in PAPER_PAIRS.items():
            a_price = self.price(frames[config["a"]], as_of)
            b_price = self.price(frames[config["b"]], as_of)
            signals = {
                "A": self.signal(frames[config["a_signal"]], as_of),
                "B": self.signal(frames[config["b_signal"]], as_of),
            }
            a_capital = config["allocation"] * INITIAL_A_WEIGHT
            b_capital = config["allocation"] * INITIAL_B_WEIGHT
            a_shares = a_capital / a_price
            b_shares = b_capital / b_price
            pair_signal = signals["A"]
            if config["architecture"] == PAIR_MANAGED:
                a_in_sgov = b_in_sgov = pair_signal == "SELL"
            else:
                a_in_sgov = signals["A"] == "SELL"
                b_in_sgov = signals["B"] == "SELL"

            if a_in_sgov:
                a_shares = 0.0
            if b_in_sgov:
                b_shares = 0.0
            a_sgov = a_capital if a_in_sgov else 0.0
            b_sgov = b_capital if b_in_sgov else 0.0
            pair_sgov = a_sgov + b_sgov
            entry = {
                "architecture": config["architecture"],
                "capital_bucket": config["allocation"],
                "a_ticker": config["a"], "b_ticker": config["b"],
                "a_shares": a_shares, "b_shares": b_shares,
                "sgov_balance": pair_sgov,
                "a_sgov_balance": a_sgov if config["architecture"] == INDEPENDENT_SLEEVES else 0.0,
                "b_sgov_balance": b_sgov if config["architecture"] == INDEPENDENT_SLEEVES else 0.0,
                "a_in_sgov": a_in_sgov, "b_in_sgov": b_in_sgov,
                "pending_dividend_a": 0.0, "pending_dividend_b": 0.0,
                "total_dividends_received": 0.0,
                "restoration_a_weight": INITIAL_A_WEIGHT,
                "a_earnings_lock": False, "b_earnings_lock": False,
                "a_locked_earnings_date": None, "b_locked_earnings_date": None,
                "last_signal": signals,
                "last_action": (
                    "PAPER_PARK_IN_SGOV" if a_in_sgov and b_in_sgov
                    else "PAPER_MIXED_INITIALIZATION" if a_in_sgov != b_in_sgov
                    else "PAPER_BUY_OPEN"
                ),
                "last_prices": {"A": a_price, "B": b_price},
            }
            state["pairs"][pair] = entry
            for side, capital, price, shares, in_sgov in [
                ("A", a_capital, a_price, a_shares, a_in_sgov),
                ("B", b_capital, b_price, b_shares, b_in_sgov),
            ]:
                if in_sgov:
                    logs.append(self.log_row(as_of, pair, side, signals[side], "PAPER_PARK_IN_SGOV", "SGOV", 0.0, self.price(frames["SGOV"], as_of), capital, "Signal-aware initialization on SELL"))
                else:
                    logs.append(self.log_row(as_of, pair, side, signals[side], "PAPER_BUY_OPEN", config[side.lower()], shares, price, capital, "Signal-aware Strength Weighted initialization"))
        return state, logs

    @staticmethod
    def log_row(date, pair, sleeve, signal, action, ticker, shares, price, value, reason):
        return {
            "Date": pd.Timestamp(date).strftime("%Y-%m-%d"), "Pair": pair,
            "Sleeve": sleeve, "Signal": signal, "Action": action, "Ticker": ticker,
            "Shares": round(float(shares), 10), "Price": round(float(price), 6),
            "Paper_Value": round(float(value), 6),
            "Reason": f"{PAPER_LABEL}: {reason}",
        }

    @staticmethod
    def is_pair_in_sgov(entry: dict) -> bool:
        return bool(entry.get("a_in_sgov") and entry.get("b_in_sgov"))

    @staticmethod
    def sleeve_in_sgov(entry: dict, side: str) -> bool:
        return bool(entry.get(f"{side.lower()}_in_sgov"))

    def accrue_sgov(self, state: dict, frames: dict[str, pd.DataFrame], as_of: pd.Timestamp) -> None:
        previous = pd.Timestamp(state["last_processed_date"])
        sgov = frames["SGOV"]
        prior_rows = sgov.loc[:previous]
        current_rows = sgov.loc[:as_of]
        if prior_rows.empty or current_rows.empty:
            return
        factor = float(current_rows.iloc[-1]["Adj Close"]) / float(prior_rows.iloc[-1]["Adj Close"])
        for entry in state["pairs"].values():
            entry["sgov_balance"] *= factor
            entry["a_sgov_balance"] *= factor
            entry["b_sgov_balance"] *= factor

    def sell_pair(self, pair, entry, config, signals, prices, as_of, reason, logs):
        if self.is_pair_in_sgov(entry):
            return
        a_value = entry["a_shares"] * prices["A"]
        b_value = entry["b_shares"] * prices["B"]
        total = a_value + b_value
        if total > 0:
            entry["restoration_a_weight"] = a_value / total
        for side, value in [("A", a_value), ("B", b_value)]:
            shares = entry[f"{side.lower()}_shares"]
            logs.append(self.log_row(as_of, pair, side, signals[side], "PAPER_SELL_TO_SGOV", config[side.lower()], shares, prices[side], value, reason))
            entry[f"{side.lower()}_shares"] = 0.0
        entry["sgov_balance"] += total
        entry["a_in_sgov"] = entry["b_in_sgov"] = True
        entry["last_action"] = "PAPER_SELL_TO_SGOV"

    def buy_pair(self, pair, entry, config, signals, prices, as_of, reason, logs):
        if not self.is_pair_in_sgov(entry):
            return
        pending_a = entry["pending_dividend_a"]
        pending_b = entry["pending_dividend_b"]
        principal = max(entry["sgov_balance"] - pending_a - pending_b, 0.0)
        a_value = principal * entry["restoration_a_weight"] + pending_a
        b_value = principal * (1 - entry["restoration_a_weight"]) + pending_b
        entry["a_shares"] = a_value / prices["A"]
        entry["b_shares"] = b_value / prices["B"]
        entry["sgov_balance"] = 0.0
        entry["a_in_sgov"] = entry["b_in_sgov"] = False
        entry["pending_dividend_a"] = entry["pending_dividend_b"] = 0.0
        for side, value in [("A", a_value), ("B", b_value)]:
            logs.append(self.log_row(as_of, pair, side, signals[side], "PAPER_BUY_FROM_SGOV", config[side.lower()], entry[f"{side.lower()}_shares"], prices[side], value, reason))
        entry["last_action"] = "PAPER_BUY_FROM_SGOV"

    def sell_sleeve(self, pair, entry, config, side, signal, price, as_of, reason, logs):
        if self.sleeve_in_sgov(entry, side):
            return
        key = side.lower()
        shares = entry[f"{key}_shares"]
        value = shares * price
        entry[f"{key}_shares"] = 0.0
        entry[f"{key}_sgov_balance"] += value
        entry[f"{key}_in_sgov"] = True
        entry["sgov_balance"] = entry["a_sgov_balance"] + entry["b_sgov_balance"]
        entry["last_action"] = f"PAPER_{side}_SELL_TO_SGOV"
        logs.append(self.log_row(as_of, pair, side, signal, "PAPER_SELL_TO_SGOV", config[key], shares, price, value, reason))

    def buy_sleeve(self, pair, entry, config, side, signal, price, as_of, reason, logs):
        if not self.sleeve_in_sgov(entry, side):
            return
        key = side.lower()
        value = entry[f"{key}_sgov_balance"]
        shares = value / price
        entry[f"{key}_shares"] = shares
        entry[f"{key}_sgov_balance"] = 0.0
        entry[f"{key}_in_sgov"] = False
        entry[f"pending_dividend_{key}"] = 0.0
        entry["sgov_balance"] = entry["a_sgov_balance"] + entry["b_sgov_balance"]
        entry["last_action"] = f"PAPER_{side}_BUY_FROM_SGOV"
        logs.append(self.log_row(as_of, pair, side, signal, "PAPER_BUY_FROM_SGOV", config[key], shares, price, value, reason))

    def apply_dividend(
        self,
        entry: dict,
        dividend_per_share: float,
        prices: dict,
        eligible_a_shares: float | None = None,
    ) -> float:
        shares = entry["a_shares"] if eligible_a_shares is None else eligible_a_shares
        cash = shares * dividend_per_share
        if cash <= 0:
            return 0.0
        half = cash / 2
        entry["total_dividends_received"] += cash
        if entry["architecture"] == PAIR_MANAGED and self.is_pair_in_sgov(entry):
            entry["sgov_balance"] += cash
            entry["pending_dividend_a"] += half
            entry["pending_dividend_b"] += half
        else:
            for side in ["A", "B"]:
                key = side.lower()
                if entry["architecture"] == INDEPENDENT_SLEEVES and self.sleeve_in_sgov(entry, side):
                    entry[f"{key}_sgov_balance"] += half
                    entry[f"pending_dividend_{key}"] += half
                else:
                    entry[f"{key}_shares"] += half / prices[side]
            entry["sgov_balance"] = entry["a_sgov_balance"] + entry["b_sgov_balance"]
        return cash

    def process_pair(self, pair, entry, config, frames, as_of, logs, report_rows):
        entry["last_action"] = "NO_PAPER_TRADE"
        prices = {"A": self.price(frames[config["a"]], as_of), "B": self.price(frames[config["b"]], as_of)}
        signals = {"A": self.signal(frames[config["a_signal"]], as_of), "B": self.signal(frames[config["b_signal"]], as_of)}
        eligible_a_shares = entry["a_shares"]
        status = self.earnings_status(as_of, self.load_earnings(config["earnings_source"]))
        if config["architecture"] == PAIR_MANAGED:
            if status["exit_now"]:
                self.sell_pair(pair, entry, config, signals, prices, as_of, "Scheduled pre-earnings exit", logs)
                entry["a_earnings_lock"] = entry["b_earnings_lock"] = True
                entry["a_locked_earnings_date"] = status["earnings_date"]
                entry["b_locked_earnings_date"] = status["earnings_date"]
            elif entry["a_earnings_lock"]:
                earnings_date = entry["a_locked_earnings_date"]
                if earnings_date and as_of > pd.Timestamp(earnings_date) and signals["A"] == "BUY":
                    self.buy_pair(pair, entry, config, signals, prices, as_of, "Post-earnings BUY re-entry", logs)
                    entry["a_earnings_lock"] = entry["b_earnings_lock"] = False
                    entry["a_locked_earnings_date"] = entry["b_locked_earnings_date"] = None
            elif signals["A"] == "SELL":
                self.sell_pair(pair, entry, config, signals, prices, as_of, "Underlying SELL signal", logs)
            elif signals["A"] == "BUY":
                self.buy_pair(pair, entry, config, signals, prices, as_of, "Underlying BUY signal", logs)
        else:
            for side in ["A", "B"]:
                follows = side == "A" or config["b_follows_earnings"]
                lock = f"{side.lower()}_earnings_lock"
                if follows and status["exit_now"]:
                    self.sell_sleeve(pair, entry, config, side, signals[side], prices[side], as_of, "Scheduled pre-earnings exit", logs)
                    entry[lock] = True
                    entry[f"{side.lower()}_locked_earnings_date"] = status["earnings_date"]
                elif entry[lock]:
                    earnings_date = entry[f"{side.lower()}_locked_earnings_date"]
                    if earnings_date and as_of > pd.Timestamp(earnings_date) and signals[side] == "BUY":
                        self.buy_sleeve(pair, entry, config, side, signals[side], prices[side], as_of, "Post-earnings BUY re-entry", logs)
                        entry[lock] = False
                        entry[f"{side.lower()}_locked_earnings_date"] = None
                elif signals[side] == "SELL":
                    self.sell_sleeve(pair, entry, config, side, signals[side], prices[side], as_of, "ETF sleeve SELL signal", logs)
                elif signals[side] == "BUY":
                    self.buy_sleeve(pair, entry, config, side, signals[side], prices[side], as_of, "ETF sleeve BUY signal", logs)

        dividend = float(frames[config["a"]].reindex([as_of])["Dividends"].fillna(0).iloc[0])
        dividend_cash = self.apply_dividend(
            entry,
            dividend,
            prices,
            eligible_a_shares=eligible_a_shares,
        )
        if dividend_cash > 0:
            logs.append(
                self.log_row(
                    as_of,
                    pair,
                    "A",
                    signals["A"],
                    "PAPER_DIVIDEND_RECEIVED",
                    config["a"],
                    eligible_a_shares,
                    dividend,
                    dividend_cash,
                    "Income ETF dividend split 50/50 between A and B",
                )
            )
        entry["last_signal"] = signals
        entry["last_prices"] = prices
        value = entry["a_shares"] * prices["A"] + entry["b_shares"] * prices["B"] + entry["sgov_balance"]
        report_rows.append(self.report_row(pair, entry, signals, prices, status, dividend_cash, entry["last_action"]))

    @staticmethod
    def report_row(pair, entry, signals, prices, earnings, dividend, action):
        invested = (
            entry["a_shares"] * prices["A"]
            + entry["b_shares"] * prices["B"]
        )
        state_text = (
            f"A: {'SGOV' if entry['a_in_sgov'] else 'ETF'}; "
            f"B: {'SGOV' if entry['b_in_sgov'] else 'ETF'}"
        )
        return {
            "Pair": pair,
            "Value": invested + entry["sgov_balance"],
            "Signals": f"A={signals['A']}, B={signals['B']}",
            "Invested": invested,
            "SGOV": entry["sgov_balance"],
            "Recommended_State": state_text,
            "Earnings": earnings["warning"] or earnings["earnings_date"] or "None",
            "Dividend": dividend,
            "Action": action,
        }

    def append_log(self, rows: list[dict]) -> None:
        if not rows:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        exists = self.log_path.exists()
        with self.log_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=LOG_COLUMNS)
            if not exists:
                writer.writeheader()
            writer.writerows(rows)

    def write_state(self, state: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def write_report(self, state: dict, rows: list[dict], as_of: pd.Timestamp, note: str = "") -> None:
        total = sum(row["Value"] for row in rows) if rows else self.state_value(state)
        invested = sum(row["Invested"] for row in rows)
        sgov = sum(row["SGOV"] for row in rows)
        lines = [f"# Daily Paper Report - {as_of.date()}", "", f"**{PAPER_LABEL}**", "", f"- Portfolio Value: ${total:.6f}", f"- ETF Exposure: ${invested:.6f}", f"- SGOV Exposure: ${sgov:.6f}", f"- Starting Paper Capital: ${TOTAL_PAPER_CAPITAL:.2f}", f"- Status: {note or 'Daily paper ledger updated'}", "", "## Pair Status", "", "| Pair | Signal | Invested Amount | SGOV Amount | Recommended State | Earnings | Dividends Today | Suggested Action |", "| --- | --- | ---: | ---: | --- | --- | ---: | --- |"]
        for row in rows:
            lines.append(f"| {row['Pair']} | {row['Signals']} | ${row['Invested']:.6f} | ${row['SGOV']:.6f} | {row['Recommended_State']} | {row['Earnings']} | ${row['Dividend']:.6f} | {row['Action']} |")
        lines.extend(["", "No broker or order API is connected. No real trades were submitted.", ""])
        self.report_path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def state_value(state: dict) -> float:
        return sum(
            entry["a_shares"] * entry["last_prices"]["A"]
            + entry["b_shares"] * entry["last_prices"]["B"]
            + entry["sgov_balance"]
            for entry in state["pairs"].values()
        )

    @staticmethod
    def exposure_summary(state: dict | None) -> dict[str, float | int]:
        if state is None:
            return {
                "etf": TOTAL_PAPER_CAPITAL,
                "sgov": 0.0,
                "invested_pairs": len(PAPER_PAIRS),
                "sgov_pairs": 0,
                "mixed_pairs": 0,
            }
        etf = sgov = 0.0
        invested_pairs = sgov_pairs = mixed_pairs = 0
        for entry in state["pairs"].values():
            etf += (
                entry["a_shares"] * entry["last_prices"]["A"]
                + entry["b_shares"] * entry["last_prices"]["B"]
            )
            sgov += entry["sgov_balance"]
            a_in_sgov = entry.get("a_in_sgov", entry["a_shares"] == 0)
            b_in_sgov = entry.get("b_in_sgov", entry["b_shares"] == 0)
            if a_in_sgov and b_in_sgov:
                sgov_pairs += 1
            elif a_in_sgov != b_in_sgov:
                mixed_pairs += 1
            else:
                invested_pairs += 1
        return {
            "etf": etf,
            "sgov": sgov,
            "invested_pairs": invested_pairs,
            "sgov_pairs": sgov_pairs,
            "mixed_pairs": mixed_pairs,
        }

    def write_initialization_comparison(
        self,
        previous_state: dict | None,
        signal_state: dict,
    ) -> None:
        before = self.exposure_summary(previous_state)
        after = self.exposure_summary(signal_state)
        lines = [
            "# Initialization Comparison",
            "",
            f"**{PAPER_LABEL}**",
            "",
            "| Metric | Current Initialization | Signal-Aware Initialization |",
            "| --- | ---: | ---: |",
            f"| Total ETF Exposure | ${before['etf']:.6f} | ${after['etf']:.6f} |",
            f"| Total SGOV Exposure | ${before['sgov']:.6f} | ${after['sgov']:.6f} |",
            f"| Pairs Fully Invested | {before['invested_pairs']} | {after['invested_pairs']} |",
            f"| Pairs Fully In SGOV | {before['sgov_pairs']} | {after['sgov_pairs']} |",
            f"| Mixed-State Pairs | {before['mixed_pairs']} | {after['mixed_pairs']} |",
            "",
            f"Signal-aware capital reconciliation: ${after['etf'] + after['sgov']:.6f}.",
            "",
            "No broker connection exists and no real trades were executed.",
            "",
        ]
        self.comparison_path.parent.mkdir(parents=True, exist_ok=True)
        self.comparison_path.write_text("\n".join(lines), encoding="utf-8")

    def process_pending_dividends_only(
        self,
        state: dict,
        frames: dict[str, pd.DataFrame],
        as_of: pd.Timestamp,
    ) -> list[dict]:
        """Extension hook for idempotent paper-income recovery."""
        return []


    def run(self, reinitialize_signal_aware: bool = False) -> dict:
        frames = self.provider.fetch(self.required_symbols())
        as_of = self.common_as_of(frames)
        if reinitialize_signal_aware or not self.state_path.exists():
            previous_state = (
                json.loads(self.state_path.read_text(encoding="utf-8"))
                if self.state_path.exists()
                else None
            )
            state, logs = self.initial_state(frames, as_of)
            rows = []
            for pair, config in PAPER_PAIRS.items():
                entry = state["pairs"][pair]
                prices = entry["last_prices"]
                signals = entry["last_signal"]
                earnings = self.earnings_status(
                    as_of, self.load_earnings(config["earnings_source"])
                )
                rows.append(self.report_row(pair, entry, signals, prices, earnings, 0.0, entry["last_action"]))
            self.write_state(state)
            self.append_log(logs)
            self.write_report(state, rows, as_of, "Initialized signal-aware Strength Weighted paper portfolio")
            self.write_initialization_comparison(previous_state, state)
            return state

        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        if pd.Timestamp(state["last_processed_date"]) >= as_of:
            recovered_logs = self.process_pending_dividends_only(state, frames, as_of)
            if recovered_logs:
                self.write_state(state)
                self.append_log(recovered_logs)
            rows = []
            for pair, entry in state["pairs"].items():
                config = PAPER_PAIRS[pair]
                prices = {"A": self.price(frames[config["a"]], as_of), "B": self.price(frames[config["b"]], as_of)}
                signals = {"A": self.signal(frames[config["a_signal"]], as_of), "B": self.signal(frames[config["b_signal"]], as_of)}
                earnings = self.earnings_status(as_of, self.load_earnings(config["earnings_source"]))
                entry["last_signal"] = signals
                entry["last_prices"] = prices
                rows.append(self.report_row(pair, entry, signals, prices, earnings, 0.0, "NO_CHANGE"))
            self.write_state(state)
            self.write_report(state, rows, as_of, "Market date already processed; no duplicate actions")
            return state

        self.accrue_sgov(state, frames, as_of)
        logs, report_rows = [], []
        for pair, config in PAPER_PAIRS.items():
            self.process_pair(pair, state["pairs"][pair], config, frames, as_of, logs, report_rows)
        state["as_of_date"] = state["last_processed_date"] = as_of.strftime("%Y-%m-%d")
        self.write_state(state)
        self.append_log(logs)
        self.write_report(state, report_rows, as_of)
        return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reinitialize-signal-aware",
        action="store_true",
        help="replace the paper state using current signal-aware allocations",
    )
    args = parser.parse_args()
    print(PAPER_LABEL)
    engine = PaperTradingEngine(YahooMarketDataProvider())
    state = engine.run(reinitialize_signal_aware=args.reinitialize_signal_aware)
    print(f"Paper state updated through: {state['as_of_date']}")
    print(f"State: {engine.state_path}")
    print(f"Log: {engine.log_path}")
    print(f"Report: {engine.report_path}")
    print(f"Initialization comparison: {engine.comparison_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
