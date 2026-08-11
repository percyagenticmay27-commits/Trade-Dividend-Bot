"""Qualified-entry wrapper for the Dividend paper trading engine.

The accounting, dividend, earnings, and SGOV implementation remains in
``paper_trading_engine_core``. This compatibility layer changes permission to
open/re-open ETF exposure, binds paper sizing to the Enterprise AI CIO's
DIVIDEND-001 allocation, persists the strategy methodology that owns every
qualified paper entry, and routes normal technical exits only through that
persisted owner.

PAPER ONLY - NO REAL TRADES EXECUTED.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from dividend_entry_gate import evaluate_entry_gate, evaluate_pair_entry_gate
from paper_portfolio_config import (
    INDEPENDENT_SLEEVES,
    INITIAL_A_WEIGHT,
    INITIAL_B_WEIGHT,
    PAIR_MANAGED,
    PAPER_PAIRS,
)
from paper_trading_engine_core import (
    COMPARISON_PATH,
    EARNINGS_DIR,
    LOG_COLUMNS,
    LOG_PATH,
    PAPER_LABEL,
    REPORT_PATH,
    STATE_PATH,
    MarketDataProvider,
    PaperTradingEngine as CorePaperTradingEngine,
    YahooMarketDataProvider,
)
from src.dividend_bot.dividend_enterprise_capital_contract import (
    LEGACY_BASELINE_CAPITAL,
    read_enterprise_dividend_allocation,
    scale_paper_state_to_allocation,
)
from src.dividend_bot.dividend_strategy_ownership import owned_exit_signal

WATCHLIST_PATH = Path("watchlist_report.json")
ENTRY_SCORE_PATH = Path("entry_score_report.json")
ENTERPRISE_CASH_STATE_PATH = Path("state/paper_cash_account.json")


def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, Mapping) else {}


def _read_log_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except (OSError, UnicodeError, csv.Error):
        return []


def _dividend_window_starts(
    state: Mapping[str, Any],
    log_rows: list[Mapping[str, Any]],
) -> dict[str, pd.Timestamp]:
    default = pd.Timestamp(state.get("last_processed_date") or state.get("as_of_date"))
    pairs = state.get("pairs")
    if not isinstance(pairs, Mapping):
        return {}
    starts: dict[str, pd.Timestamp] = {}
    for pair, raw_entry in pairs.items():
        if not isinstance(raw_entry, Mapping):
            continue
        pair_name = str(pair)
        entry = raw_entry
        starts[pair_name] = default
        has_recorded_distribution = any(
            str(row.get("Pair") or row.get("pair") or "") == pair_name
            and "DIVIDEND" in str(row.get("Action") or row.get("action") or "").upper()
            for row in log_rows
        )
        state_income = float(entry.get("total_dividends_received") or 0.0)
        if has_recorded_distribution or state_income > 0:
            continue
        config = PAPER_PAIRS.get(pair_name)
        if not isinstance(config, Mapping):
            continue
        income_symbol = str(config.get("a") or "").upper()
        buys = [
            pd.Timestamp(row.get("Date") or row.get("date"))
            for row in log_rows
            if str(row.get("Pair") or row.get("pair") or "") == pair_name
            and str(row.get("Ticker") or row.get("ticker") or "").upper() == income_symbol
            and str(row.get("Action") or row.get("action") or "").upper()
            in {"PAPER_BUY_OPEN", "PAPER_BUY", "PAPER_BUY_FROM_SGOV"}
            and row.get("Date") or row.get("date")
        ]
        if buys:
            starts[pair_name] = max(buys)
    return starts


def _unprocessed_dividend_payments(
    frame: pd.DataFrame,
    *,
    after: pd.Timestamp,
    through: pd.Timestamp,
) -> list[tuple[pd.Timestamp, float]]:
    eligible = frame.loc[(frame.index > after) & (frame.index <= through)]
    if eligible.empty or "Dividends" not in eligible:
        return []
    return [
        (pd.Timestamp(date), float(value))
        for date, value in eligible["Dividends"].fillna(0.0).items()
        if float(value) > 0
    ]


class PaperTradingEngine(CorePaperTradingEngine):
    """Paper ledger with strategy-owned qualification and lifecycle routing."""

    watchlist_path: Path = WATCHLIST_PATH
    entry_score_path: Path = ENTRY_SCORE_PATH
    enterprise_cash_state_path: Path = ENTERPRISE_CASH_STATE_PATH

    def _enterprise_allocation(self) -> float:
        return (
            read_enterprise_dividend_allocation(self.enterprise_cash_state_path)
            or LEGACY_BASELINE_CAPITAL
        )

    def _allocation_scale(self) -> float:
        return self._enterprise_allocation() / LEGACY_BASELINE_CAPITAL

    def _entry_evidence(self) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        return _read_json(self.watchlist_path), _read_json(self.entry_score_path)

    def _entry_row_for_symbol(self, symbol: str) -> Mapping[str, Any] | None:
        _watchlist, report = self._entry_evidence()
        rows = report.get("entries") if isinstance(report, Mapping) else None
        target = str(symbol or "").strip().upper()
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, Mapping) and str(row.get("symbol") or "").strip().upper() == target:
                    return row
            if report.get("symbol_specific"):
                return None
        return report if isinstance(report, Mapping) and report else None

    def _strategy_signals_for_symbol(self, symbol: str) -> Mapping[str, Any]:
        row = self._entry_row_for_symbol(symbol)
        value = row.get("strategy_signals") if isinstance(row, Mapping) else None
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _technical_snapshot(signal: str, signal_symbol: str) -> dict[str, Any]:
        return {
            "signal": str(signal).upper(),
            "signal_symbol": str(signal_symbol).upper(),
            "source": "paper_trading_engine.approved_daily_signal",
        }

    @staticmethod
    def _persist_pair_strategy_owner(entry: dict[str, Any], decision: Mapping[str, Any]) -> None:
        owners = [str(value).upper() for value in decision.get("strategy_owners", []) if value]
        unique = sorted(set(owners))
        if len(unique) != 1:
            entry["strategy_owner"] = None
            entry["a_strategy_owner"] = None
            entry["b_strategy_owner"] = None
            entry["strategy_ownership_source"] = "ENTRY_GATE_UNRESOLVED"
            return
        owner = unique[0]
        entry["strategy_owner"] = owner
        entry["a_strategy_owner"] = owner
        entry["b_strategy_owner"] = owner
        entry["strategy_ownership_source"] = "QUALIFIED_ENTRY_GATE"

    @staticmethod
    def _persist_sleeve_strategy_owner(
        entry: dict[str, Any], side: str, decision: Mapping[str, Any]
    ) -> None:
        owner = decision.get("strategy_owner")
        key = side.lower()
        if owner:
            entry[f"{key}_strategy_owner"] = str(owner).upper()
            entry[f"{key}_strategy_ownership_source"] = "QUALIFIED_ENTRY_GATE"
        else:
            entry[f"{key}_strategy_owner"] = None
            entry[f"{key}_strategy_ownership_source"] = "ENTRY_GATE_UNRESOLVED"

    @staticmethod
    def _clear_pair_strategy_owner(entry: dict[str, Any], exit_decision: Mapping[str, Any]) -> None:
        owner = entry.get("strategy_owner")
        entry["last_exit_strategy_owner"] = owner
        entry["last_exit_strategy_reasons"] = list(exit_decision.get("sell_reasons") or [])
        entry["strategy_owner"] = None
        entry["a_strategy_owner"] = None
        entry["b_strategy_owner"] = None
        entry["strategy_ownership_source"] = "CLOSED_TO_SGOV"

    @staticmethod
    def _clear_sleeve_strategy_owner(
        entry: dict[str, Any], side: str, exit_decision: Mapping[str, Any]
    ) -> None:
        key = side.lower()
        owner = entry.get(f"{key}_strategy_owner")
        entry[f"{key}_last_exit_strategy_owner"] = owner
        entry[f"{key}_last_exit_strategy_reasons"] = list(exit_decision.get("sell_reasons") or [])
        entry[f"{key}_strategy_owner"] = None
        entry[f"{key}_strategy_ownership_source"] = "CLOSED_TO_SGOV"

    def _owned_sleeve_exit_decision(
        self, *, entry: Mapping[str, Any], config: Mapping[str, Any], side: str
    ) -> dict[str, Any]:
        key = side.lower()
        owner = entry.get(f"{key}_strategy_owner")
        symbol = str(config.get(key) or "")
        signal_symbol = str(config.get(f"{key}_signal") or symbol)
        decision = owned_exit_signal(
            self._strategy_signals_for_symbol(signal_symbol),
            owner,
        )
        return {
            **decision,
            "symbol": symbol,
            "signal_symbol": signal_symbol,
            "sleeve": side,
            "ownership_source": entry.get(f"{key}_strategy_ownership_source"),
        }

    def _owned_pair_exit_decision(
        self, *, entry: Mapping[str, Any], config: Mapping[str, Any]
    ) -> dict[str, Any]:
        owner = entry.get("strategy_owner")
        decisions = []
        for side in ("A", "B"):
            key = side.lower()
            symbol = str(config.get(key) or "")
            signal_symbol = str(config.get(f"{key}_signal") or symbol)
            detail = owned_exit_signal(
                self._strategy_signals_for_symbol(signal_symbol),
                owner,
            )
            decisions.append({
                **detail,
                "symbol": symbol,
                "signal_symbol": signal_symbol,
                "sleeve": side,
            })
        triggered = [item for item in decisions if item.get("sell_trigger")]
        reasons = sorted({reason for item in triggered for reason in item.get("sell_reasons", [])})
        return {
            "strategy_owner": owner,
            "sell_trigger": bool(triggered),
            "sell_reasons": reasons,
            "reason": "PAIR_OWNER_EXIT_TRIGGERED" if triggered else "PAIR_OWNER_EXIT_NOT_TRIGGERED",
            "sleeves": decisions,
            "ownership_source": entry.get("strategy_ownership_source"),
        }

    def _gate_sleeve(
        self,
        *,
        pair: str,
        config: Mapping[str, Any],
        side: str,
        signal: str,
    ) -> dict[str, Any]:
        key = side.lower()
        watchlist, entry_score = self._entry_evidence()
        signal_symbol = str(config.get(f"{key}_signal") or config[key])
        return evaluate_entry_gate(
            symbol=str(config[key]),
            pair=pair,
            sleeve=side,
            signal_symbol=signal_symbol,
            technical_snapshot=self._technical_snapshot(signal, signal_symbol),
            watchlist_report=watchlist,
            entry_score_report=entry_score,
            currently_held=False,
        )

    def _gate_pair(
        self,
        *,
        pair: str,
        config: Mapping[str, Any],
        signals: Mapping[str, str],
    ) -> dict[str, Any]:
        watchlist, entry_score = self._entry_evidence()
        technical = self._technical_snapshot(
            str(signals["A"]), str(config.get("a_signal") or config["a"])
        )
        return evaluate_pair_entry_gate(
            pair=pair,
            config=config,
            technical_snapshot=technical,
            watchlist_report=watchlist,
            entry_score_report=entry_score,
        )

    def initial_state(self, frames, as_of):
        """Initialize from Enterprise allocation and only qualified entries."""
        state, _legacy_logs = super().initial_state(frames, as_of)
        allocation = self._enterprise_allocation()
        state, _factor = scale_paper_state_to_allocation(state, allocation)
        logs: list[dict[str, Any]] = []
        scale = allocation / LEGACY_BASELINE_CAPITAL

        for pair, config in PAPER_PAIRS.items():
            entry = state["pairs"][pair]
            signals = entry["last_signal"]
            a_capital = float(config["allocation"]) * scale * INITIAL_A_WEIGHT
            b_capital = float(config["allocation"]) * scale * INITIAL_B_WEIGHT

            if config["architecture"] == PAIR_MANAGED:
                decision = self._gate_pair(pair=pair, config=config, signals=signals)
                entry["entry_gate"] = decision
                if not decision["approved"]:
                    entry["a_shares"] = 0.0
                    entry["b_shares"] = 0.0
                    entry["a_in_sgov"] = True
                    entry["b_in_sgov"] = True
                    entry["a_sgov_balance"] = 0.0
                    entry["b_sgov_balance"] = 0.0
                    entry["sgov_balance"] = a_capital + b_capital
                    entry["strategy_owner"] = None
                    entry["a_strategy_owner"] = None
                    entry["b_strategy_owner"] = None
                    entry["strategy_ownership_source"] = "WAIT_IN_SGOV"
                    entry["last_action"] = "PAPER_WAIT_IN_SGOV"
                else:
                    entry["a_in_sgov"] = False
                    entry["b_in_sgov"] = False
                    entry["a_sgov_balance"] = 0.0
                    entry["b_sgov_balance"] = 0.0
                    entry["sgov_balance"] = 0.0
                    self._persist_pair_strategy_owner(entry, decision)
                    entry["last_action"] = "PAPER_BUY_OPEN"

                for side, capital in (("A", a_capital), ("B", b_capital)):
                    key = side.lower()
                    if decision["approved"]:
                        logs.append(self.log_row(
                            as_of, pair, side, signals[side], "PAPER_BUY_OPEN",
                            config[key], entry[f"{key}_shares"], entry["last_prices"][side],
                            capital, "Qualified entry gate approved initial paper position",
                        ))
                    else:
                        logs.append(self.log_row(
                            as_of, pair, side, signals[side], "PAPER_WAIT_IN_SGOV",
                            "SGOV", 0.0, self.price(frames["SGOV"], as_of), capital,
                            "Entry gate blocked initialization: " + ", ".join(decision["reasons"]),
                        ))
                continue

            decisions: dict[str, Any] = {}
            for side, capital in (("A", a_capital), ("B", b_capital)):
                key = side.lower()
                decision = self._gate_sleeve(
                    pair=pair, config=config, side=side, signal=signals[side]
                )
                decisions[side] = decision
                if decision["approved"]:
                    entry[f"{key}_in_sgov"] = False
                    entry[f"{key}_sgov_balance"] = 0.0
                    self._persist_sleeve_strategy_owner(entry, side, decision)
                    logs.append(self.log_row(
                        as_of, pair, side, signals[side], "PAPER_BUY_OPEN",
                        config[key], entry[f"{key}_shares"], entry["last_prices"][side],
                        capital, "Qualified entry gate approved initial paper position",
                    ))
                else:
                    entry[f"{key}_shares"] = 0.0
                    entry[f"{key}_in_sgov"] = True
                    entry[f"{key}_sgov_balance"] = capital
                    entry[f"{key}_strategy_owner"] = None
                    entry[f"{key}_strategy_ownership_source"] = "WAIT_IN_SGOV"
                    logs.append(self.log_row(
                        as_of, pair, side, signals[side], "PAPER_WAIT_IN_SGOV",
                        "SGOV", 0.0, self.price(frames["SGOV"], as_of), capital,
                        "Entry gate blocked initialization: " + ", ".join(decision["reasons"]),
                    ))
            entry["entry_gate"] = decisions
            entry["sgov_balance"] = entry["a_sgov_balance"] + entry["b_sgov_balance"]
            if entry["a_in_sgov"] and entry["b_in_sgov"]:
                entry["last_action"] = "PAPER_WAIT_IN_SGOV"
            elif entry["a_in_sgov"] != entry["b_in_sgov"]:
                entry["last_action"] = "PAPER_MIXED_INITIALIZATION"
            else:
                entry["last_action"] = "PAPER_BUY_OPEN"

        return state, logs

    def run(self, reinitialize_signal_aware: bool = False) -> dict:
        allocation = self._enterprise_allocation()
        self._dividend_window_starts: dict[str, pd.Timestamp] = {}
        if self.state_path.exists() and not reinitialize_signal_aware:
            try:
                existing = json.loads(self.state_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                existing = None
            if isinstance(existing, Mapping):
                normalized, factor = scale_paper_state_to_allocation(existing, allocation)
                self._dividend_window_starts = _dividend_window_starts(
                    normalized,
                    _read_log_rows(self.log_path),
                )
                if abs(factor - 1.0) > 1e-12:
                    self.write_state(normalized)
        return super().run(reinitialize_signal_aware=reinitialize_signal_aware)

    def buy_pair(self, pair, entry, config, signals, prices, as_of, reason, logs):
        decision = self._gate_pair(pair=pair, config=config, signals=signals)
        entry["entry_gate"] = decision
        if not decision["approved"]:
            entry["last_action"] = "PAPER_WAIT_IN_SGOV"
            return
        super().buy_pair(
            pair, entry, config, signals, prices, as_of,
            "Qualified entry gate approved re-entry: " + reason, logs,
        )
        if not self.is_pair_in_sgov(entry):
            self._persist_pair_strategy_owner(entry, decision)

    def buy_sleeve(self, pair, entry, config, side, signal, price, as_of, reason, logs):
        decision = self._gate_sleeve(
            pair=pair, config=config, side=side, signal=signal
        )
        gates = entry.get("entry_gate")
        if not isinstance(gates, dict) or "approved" in gates:
            gates = {}
        gates[side] = decision
        entry["entry_gate"] = gates
        if not decision["approved"]:
            entry["last_action"] = f"PAPER_{side}_WAIT_IN_SGOV"
            return
        super().buy_sleeve(
            pair, entry, config, side, signal, price, as_of,
            "Qualified entry gate approved re-entry: " + reason, logs,
        )
        if not self.sleeve_in_sgov(entry, side):
            self._persist_sleeve_strategy_owner(entry, side, decision)

    def process_pair(self, pair, entry, config, frames, as_of, logs, report_rows):
        """Route ordinary paper exits through the persisted strategy owner.

        Earnings exits remain an independent risk/governance override. Ordinary
        technical SELL/BUY decisions no longer use the legacy aggregate signal as
        execution authority when Strategy A/B evidence is available.
        """
        entry["last_action"] = "NO_PAPER_TRADE"
        prices = {
            "A": self.price(frames[config["a"]], as_of),
            "B": self.price(frames[config["b"]], as_of),
        }
        # Preserve legacy signal values for reporting/audit only.
        signals = {
            "A": self.signal(frames[config["a_signal"]], as_of),
            "B": self.signal(frames[config["b_signal"]], as_of),
        }
        eligible_a_shares = entry["a_shares"]
        status = self.earnings_status(as_of, self.load_earnings(config["earnings_source"]))

        if config["architecture"] == PAIR_MANAGED:
            if status["exit_now"]:
                exit_decision = {
                    "sell_reasons": ["SCHEDULED_PRE_EARNINGS_EXIT"],
                    "reason": "RISK_GOVERNANCE_OVERRIDE",
                }
                super().sell_pair(
                    pair, entry, config, signals, prices, as_of,
                    "Scheduled pre-earnings exit", logs,
                )
                if self.is_pair_in_sgov(entry):
                    self._clear_pair_strategy_owner(entry, exit_decision)
                entry["a_earnings_lock"] = entry["b_earnings_lock"] = True
                entry["a_locked_earnings_date"] = status["earnings_date"]
                entry["b_locked_earnings_date"] = status["earnings_date"]
            elif entry["a_earnings_lock"]:
                earnings_date = entry["a_locked_earnings_date"]
                if earnings_date and as_of > pd.Timestamp(earnings_date):
                    self.buy_pair(
                        pair, entry, config, signals, prices, as_of,
                        "Post-earnings qualified re-entry", logs,
                    )
                    if not self.is_pair_in_sgov(entry):
                        entry["a_earnings_lock"] = entry["b_earnings_lock"] = False
                        entry["a_locked_earnings_date"] = entry["b_locked_earnings_date"] = None
            elif self.is_pair_in_sgov(entry):
                self.buy_pair(
                    pair, entry, config, signals, prices, as_of,
                    "Strategy-owned qualified entry", logs,
                )
            else:
                exit_decision = self._owned_pair_exit_decision(entry=entry, config=config)
                entry["exit_gate"] = exit_decision
                if exit_decision["sell_trigger"]:
                    reason = "Strategy-owner exit: " + ", ".join(exit_decision["sell_reasons"])
                    super().sell_pair(pair, entry, config, signals, prices, as_of, reason, logs)
                    if self.is_pair_in_sgov(entry):
                        self._clear_pair_strategy_owner(entry, exit_decision)
        else:
            for side in ["A", "B"]:
                follows = side == "A" or config["b_follows_earnings"]
                lock = f"{side.lower()}_earnings_lock"
                key = side.lower()
                if follows and status["exit_now"]:
                    exit_decision = {
                        "sell_reasons": ["SCHEDULED_PRE_EARNINGS_EXIT"],
                        "reason": "RISK_GOVERNANCE_OVERRIDE",
                    }
                    super().sell_sleeve(
                        pair, entry, config, side, signals[side], prices[side], as_of,
                        "Scheduled pre-earnings exit", logs,
                    )
                    if self.sleeve_in_sgov(entry, side):
                        self._clear_sleeve_strategy_owner(entry, side, exit_decision)
                    entry[lock] = True
                    entry[f"{key}_locked_earnings_date"] = status["earnings_date"]
                elif entry[lock]:
                    earnings_date = entry[f"{key}_locked_earnings_date"]
                    if earnings_date and as_of > pd.Timestamp(earnings_date):
                        self.buy_sleeve(
                            pair, entry, config, side, signals[side], prices[side], as_of,
                            "Post-earnings qualified re-entry", logs,
                        )
                        if not self.sleeve_in_sgov(entry, side):
                            entry[lock] = False
                            entry[f"{key}_locked_earnings_date"] = None
                elif self.sleeve_in_sgov(entry, side):
                    self.buy_sleeve(
                        pair, entry, config, side, signals[side], prices[side], as_of,
                        "Strategy-owned qualified entry", logs,
                    )
                else:
                    exit_decision = self._owned_sleeve_exit_decision(
                        entry=entry, config=config, side=side
                    )
                    gates = entry.get("exit_gate")
                    if not isinstance(gates, dict) or "sell_trigger" in gates:
                        gates = {}
                    gates[side] = exit_decision
                    entry["exit_gate"] = gates
                    if exit_decision["sell_trigger"]:
                        reason = "Strategy-owner exit: " + ", ".join(exit_decision["sell_reasons"])
                        super().sell_sleeve(
                            pair, entry, config, side, signals[side], prices[side], as_of,
                            reason, logs,
                        )
                        if self.sleeve_in_sgov(entry, side):
                            self._clear_sleeve_strategy_owner(entry, side, exit_decision)

        window_start = getattr(self, "_dividend_window_starts", {}).get(
            pair,
            as_of - pd.Timedelta(days=1),
        )
        dividend_cash = 0.0
        for payment_date, dividend in _unprocessed_dividend_payments(
            frames[config["a"]],
            after=window_start,
            through=as_of,
        ):
            payment_prices = {
                "A": self.price(frames[config["a"]], payment_date),
                "B": self.price(frames[config["b"]], payment_date),
            }
            payment_shares = entry["a_shares"]
            payment_cash = self.apply_dividend(
                entry,
                dividend,
                payment_prices,
                eligible_a_shares=payment_shares,
            )
            dividend_cash += payment_cash
            if payment_cash > 0:
                logs.append(
                    self.log_row(
                        payment_date,
                        pair,
                        "A",
                        signals["A"],
                        "PAPER_DIVIDEND_RECEIVED",
                        config["a"],
                        payment_shares,
                        dividend,
                        payment_cash,
                        "Income ETF dividend split 50/50 between A and B",
                    )
                )
        entry["last_signal"] = signals
        entry["last_prices"] = prices
        report_rows.append(
            self.report_row(pair, entry, signals, prices, status, dividend_cash, entry["last_action"])
        )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reinitialize-signal-aware",
        action="store_true",
        help="replace the paper state using current qualified-entry allocations",
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
