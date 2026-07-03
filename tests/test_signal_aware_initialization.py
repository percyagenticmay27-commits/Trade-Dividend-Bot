"""Validate BUY/HOLD/SELL-aware initial paper allocation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from paper_portfolio_config import PAPER_PAIRS
from paper_trading_engine import PaperTradingEngine


class SignalScenarioProvider:
    SIGNAL_SHAPES = {
        "AMD": "BUY",
        "AVGO": "HOLD",
        "GLD": "SELL",
        "GOOW": "BUY",
        "GGLL": "SELL",
    }

    def fetch(self, symbols: set[str]) -> dict[str, pd.DataFrame]:
        dates = pd.bdate_range(end="2026-06-18", periods=80)
        frames = {}
        for symbol in symbols:
            shape = self.SIGNAL_SHAPES.get(symbol, "HOLD")
            if shape == "BUY":
                values = [100 + index * 0.5 for index in range(len(dates))]
            elif shape == "SELL":
                values = [140 - index * 0.5 for index in range(len(dates))]
            else:
                values = [100.0] * len(dates)
            close = pd.Series(values, index=dates)
            frames[symbol] = pd.DataFrame(
                {
                    "Open": close,
                    "High": close,
                    "Low": close,
                    "Close": close,
                    "Adj Close": close,
                    "Volume": 1000,
                    "Dividends": 0.0,
                },
                index=dates,
            )
        return frames


def main() -> int:
    root = Path.cwd()
    paths = {
        "state": root / "signal_init_test_state.json",
        "log": root / "signal_init_test_log.csv",
        "report": root / "signal_init_test_report.md",
        "comparison": root / "signal_init_test_comparison.md",
    }
    for path in paths.values():
        path.unlink(missing_ok=True)

    try:
        engine = PaperTradingEngine(
            provider=SignalScenarioProvider(),
            state_path=paths["state"],
            log_path=paths["log"],
            report_path=paths["report"],
            comparison_path=paths["comparison"],
            earnings_dir=root / "signal_init_test_missing_earnings",
        )
        state = engine.run()

        buy_pair = state["pairs"]["AMDW / AMDL"]
        assert buy_pair["last_signal"]["A"] == "BUY"
        assert buy_pair["a_in_sgov"] is False
        assert buy_pair["b_in_sgov"] is False
        assert buy_pair["a_shares"] > 0 and buy_pair["b_shares"] > 0

        hold_pair = state["pairs"]["AVGW / AVGX"]
        assert hold_pair["last_signal"]["A"] == "HOLD"
        assert hold_pair["a_in_sgov"] is False
        assert hold_pair["b_in_sgov"] is False

        sell_pair = state["pairs"]["GLDW / NUGT"]
        assert sell_pair["last_signal"]["A"] == "SELL"
        assert sell_pair["a_in_sgov"] is True
        assert sell_pair["b_in_sgov"] is True
        assert sell_pair["sgov_balance"] == PAPER_PAIRS["GLDW / NUGT"]["allocation"]

        independent = state["pairs"]["GOOW / GGLL"]
        assert independent["last_signal"] == {"A": "BUY", "B": "SELL"}
        assert independent["a_in_sgov"] is False
        assert independent["b_in_sgov"] is True
        assert independent["a_shares"] > 0 and independent["b_shares"] == 0
        assert abs(independent["b_sgov_balance"] - 18.0) < 1e-9

        total = engine.state_value(state)
        exposure = engine.exposure_summary(state)
        assert abs(total - 500.0) < 1e-8
        assert abs(exposure["etf"] + exposure["sgov"] - 500.0) < 1e-8
        source = Path("paper_trading_engine.py").read_text(encoding="utf-8").lower()
        assert "robinhood" not in source
        assert "submit_order" not in source
    finally:
        for path in paths.values():
            path.unlink(missing_ok=True)

    print("Signal-aware paper initialization: PASS")
    print("BUY and HOLD initialize invested: PASS")
    print("SELL initializes in SGOV: PASS")
    print("Independent sleeve separation: PASS")
    print("$500 capital reconciliation: PASS")
    print("Broker API dependency check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
