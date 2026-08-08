"""Qualified-entry wrapper for the Dividend paper trading engine.

The accounting, dividend, earnings, and SGOV implementation remains in
``paper_trading_engine_core``.  This compatibility layer changes only permission
to open or re-open ETF exposure: HOLD/SELL, missing promotion evidence, stale
market data, or missing/UNKNOWN Entry Quality must remain in SGOV.

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
from paper_trading_engine_core import (  # re-export legacy public surface
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

WATCHLIST_PATH = Path("watchlist_report.json")
ENTRY_SCORE_PATH = Path("entry_score_report.json")


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

    def _entry_evidence(self) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        return _read_json(self.watchlist_path), _read_json(self.entry_score_path)

    @staticmethod
    def _technical_snapshot(signal: str, signal_symbol: str) -> dict[str, Any]:
        # The core engine already calculates the approved daily technical signal.
        # Preserve that authoritative result in the gate evidence without inventing
        # unavailable indicator values.
        return {
            "signal": str(signal).upper(),
            "signal_symbol": str(signal_symbol).upper(),
            "source": "paper_trading_engine.approved_daily_signal",
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
        """Require pair-managed sleeves to qualify together.

        Pair-managed architecture follows the A/underlying timing signal in the
        legacy engine. Both securities must also be promoted/fresh on the strategy
        watchlist before the pair may leave SGOV.
        """
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
        """Initialize only qualified entries; all others begin in SGOV."""
        state, _legacy_logs = super().initial_state(frames, as_of)
        logs: list[dict[str, Any]] = []

        for pair, config in PAPER_PAIRS.items():
            entry = state["pairs"][pair]
            signals = entry["last_signal"]
            a_capital = float(config["allocation"]) * INITIAL_A_WEIGHT
            b_capital = float(config["allocation"]) * INITIAL_B_WEIGHT

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
                    entry["last_action"] = "PAPER_WAIT_IN_SGOV"
                else:
                    entry["a_in_sgov"] = False
                    entry["b_in_sgov"] = False
                    entry["a_sgov_balance"] = 0.0
                    entry["b_sgov_balance"] = 0.0
                    entry["sgov_balance"] = 0.0
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

            # Independent sleeves are evaluated independently.
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
                    logs.append(self.log_row(
                        as_of, pair, side, signals[side], "PAPER_BUY_OPEN",
                        config[key], entry[f"{key}_shares"], entry["last_prices"][side],
                        capital, "Qualified entry gate approved initial paper position",
                    ))
                else:
                    entry[f"{key}_shares"] = 0.0
                    entry[f"{key}_in_sgov"] = True
                    entry[f"{key}_sgov_balance"] = capital
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

    def buy_pair(self, pair, entry, config, signals, prices, as_of, reason, logs):
        """Re-enter a pair only after the qualified entry gate approves it."""
        decision = self._gate_pair(pair=pair, config=config, signals=signals)
        entry["entry_gate"] = decision
        if not decision["approved"]:
            entry["last_action"] = "PAPER_WAIT_IN_SGOV"
            return
        super().buy_pair(
            pair, entry, config, signals, prices, as_of,
            "Qualified entry gate approved re-entry: " + reason, logs,
        )

    def buy_sleeve(self, pair, entry, config, side, signal, price, as_of, reason, logs):
        """Re-enter an independent sleeve only after gate approval."""
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


def main() -> int:
    # Keep the established CLI while ensuring this qualified wrapper is the class
    # instantiated by the production entry point.
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
