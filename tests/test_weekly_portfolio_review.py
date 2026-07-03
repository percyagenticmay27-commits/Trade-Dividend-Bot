"""Validate the reconciled PAPER ONLY weekly review."""

from __future__ import annotations

from pathlib import Path

from generate_weekly_portfolio_review import generate_weekly_review
from run_daily_paper_cycle import update_signal_history
import json


def main() -> int:
    root = Path.cwd()
    output = root / "weekly_review_test.md"
    signals = root / "weekly_review_test_signals.csv"
    output.unlink(missing_ok=True)
    signals.unlink(missing_ok=True)
    try:
        state = json.loads(Path("paper_state.json").read_text(encoding="utf-8"))
        update_signal_history(signals, state)
        result = generate_weekly_review(
            signal_history_path=signals,
            output_path=output,
        )
        assert result["week_end"] == "2026-06-18"
        assert abs(result["weekly_change"]) < 0.000001
        assert result["new_buy"] == 1
        assert result["new_sell"] == 10
        assert result["new_hold"] == 2
        report = output.read_text(encoding="utf-8")
        for section in [
            "Portfolio Overview", "Signal Changes", "Position Changes",
            "Dividend Activity", "Earnings Activity", "Pair Ranking",
            "Risk Review", "Readiness Review", "Final Review",
        ]:
            assert section in report
        assert "Current Portfolio Value: $500.000000" in report
        assert "Current Live Readiness: 1.111111%" in report
        assert "No abnormal pair behavior detected" in report
        assert "PAPER ONLY" in report
    finally:
        output.unlink(missing_ok=True)
        signals.unlink(missing_ok=True)

    print("Weekly portfolio review validation: PASS")
    print("Health/readiness/snapshot reconciliation: PASS")
    print("Signal, transition, dividend, earnings, ranking, and risk sections: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
