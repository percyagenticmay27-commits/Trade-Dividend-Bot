"""Qualified-entry wrapper for the Dividend paper trading engine.

The accounting, dividend, earnings, and SGOV implementation remains in
``paper_trading_engine_core``. This compatibility layer changes permission to
open/re-open ETF exposure, binds paper sizing to the Enterprise AI CIO's
DIVIDEND-001 allocation, and persists the strategy methodology that owns every
qualified paper entry.

PAPER ONLY - NO REAL TRADES EXECUTED.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

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


class PaperTradingEngine(CorePaperTradingEngine):
    """Legacy paper ledger with fail-closed qualification before every BUY."""

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

    @staticmethod
    def _technical_snapshot(signal: str, signal_symbol: str) -> dict[str, Any]:
        return {
            "signal": str(signal).upper(),
            "signal_symbol": str(signal_symbol).upper(),
            "source": "paper_trading_engine.approved_daily_signal",
        }

    @staticmethod
    def _persist_pair_strategy_owner(entry: dict[str, Any], decision: Mapping[str, Any]) -> None:
        """Persist one unambiguous owner across a pair-managed open position.

        Pair-managed positions are one lifecycle. If the gate cannot provide one
        common strategy owner, ownership remains unset instead of fabricating a
        precedence rule.
        """
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
        """Normalize existing paper state to the current Enterprise allocation."""
        allocation = self._enterprise_allocation()
        if self.state_path.exists() and not reinitialize_signal_aware:
            try:
                existing = json.loads(self.state_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                existing = None
            if isinstance(existing, Mapping):
                normalized, factor = scale_paper_state_to_allocation(existing, allocation)
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