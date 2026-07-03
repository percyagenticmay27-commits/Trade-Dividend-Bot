"""Generate a reconciled PAPER ONLY weekly portfolio review."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pandas as pd

from generate_strategy_health_dashboard import normalized_event_count
from paper_trading_engine import PAPER_LABEL


HEALTH_PATH = Path("strategy_health.csv")
PAIR_HEALTH_PATH = Path("pair_health.csv")
READINESS_PATH = Path("live_readiness.csv")
SNAPSHOT_PATH = Path("portfolio_snapshot.csv")
LOG_PATH = Path("paper_trade_log.csv")
SIGNAL_HISTORY_PATH = Path("paper_signal_history.csv")
OUTPUT_PATH = Path("weekly_portfolio_review.md")
BACKTEST_MAX_DRAWDOWN = -11.372222


def weekly_signal_changes(
    history: pd.DataFrame,
    week_start: pd.Timestamp,
    week_end: pd.Timestamp,
) -> dict[str, list[str]]:
    history = history.copy()
    history["Date"] = pd.to_datetime(history["Date"])
    history = history.sort_values(["Pair", "Sleeve", "Date"])
    changes = {"BUY": [], "SELL": [], "HOLD": []}
    for (pair, sleeve), rows in history.groupby(["Pair", "Sleeve"]):
        previous = None
        for row in rows.itertuples(index=False):
            if week_start <= row.Date <= week_end and row.Signal != previous:
                changes[row.Signal].append(
                    f"{pair} {sleeve}: {previous or 'NEW'} -> {row.Signal}"
                )
            previous = row.Signal
    return changes


def cumulative_delta(
    readiness: pd.DataFrame,
    week_start: pd.Timestamp,
    column: str,
) -> float:
    rows = readiness.copy()
    rows["Date"] = pd.to_datetime(rows["Date"])
    latest = float(rows.iloc[-1][column])
    prior = rows[rows["Date"] < week_start]
    baseline = float(prior.iloc[-1][column]) if not prior.empty else 0.0
    return latest - baseline


def bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- None"]


def generate_weekly_review(
    health_path: Path = HEALTH_PATH,
    pair_health_path: Path = PAIR_HEALTH_PATH,
    readiness_path: Path = READINESS_PATH,
    snapshot_path: Path = SNAPSHOT_PATH,
    log_path: Path = LOG_PATH,
    signal_history_path: Path = SIGNAL_HISTORY_PATH,
    output_path: Path = OUTPUT_PATH,
) -> dict[str, object]:
    required = [
        health_path, pair_health_path, readiness_path, snapshot_path,
        log_path, signal_history_path,
    ]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(f"Required weekly input not found: {path}")

    health = pd.read_csv(health_path)
    pairs = pd.read_csv(pair_health_path)
    readiness = pd.read_csv(readiness_path)
    snapshots = pd.read_csv(snapshot_path, parse_dates=["Date"]).sort_values("Date")
    log = pd.read_csv(log_path)
    signals = pd.read_csv(signal_history_path)
    if any(frame.empty for frame in [health, pairs, readiness, snapshots, signals]):
        raise ValueError("Weekly review inputs must contain data")

    current = health.iloc[-1]
    ready = readiness.iloc[-1]
    week_end = pd.Timestamp(snapshots.iloc[-1]["Date"]).normalize()
    week_start = week_end - timedelta(days=week_end.weekday())
    week_snapshots = snapshots[
        (snapshots["Date"] >= week_start) & (snapshots["Date"] <= week_end)
    ]
    prior_snapshots = snapshots[snapshots["Date"] < week_start]
    start_value = (
        float(prior_snapshots.iloc[-1]["Portfolio_Value"])
        if not prior_snapshots.empty
        else float(week_snapshots.iloc[0]["Portfolio_Value"])
    )
    current_value = float(current["Current_Portfolio_Value"])
    weekly_change = current_value - start_value

    changes = weekly_signal_changes(signals, week_start, week_end)
    weekly_log = log.copy()
    weekly_log["Date"] = pd.to_datetime(weekly_log["Date"])
    weekly_log = weekly_log[
        (weekly_log["Date"] >= week_start) & (weekly_log["Date"] <= week_end)
    ]
    etf_to_sgov = normalized_event_count(weekly_log, "PAPER_SELL_TO_SGOV")
    sgov_to_etf = normalized_event_count(weekly_log, "PAPER_BUY_FROM_SGOV")
    earnings_exits = normalized_event_count(
        weekly_log, "PAPER_SELL_TO_SGOV", "earnings"
    )
    earnings_reentries = normalized_event_count(
        weekly_log, "PAPER_BUY_FROM_SGOV", "earnings"
    )
    dividends_received = cumulative_delta(
        readiness, week_start, "Total_Dividends_Received"
    )
    dividends_reinvested = cumulative_delta(
        readiness, week_start, "Total_Dividends_Reinvested"
    )

    ranked = pairs.sort_values(
        ["Total_Return_Pct", "Current_Value", "Pair"],
        ascending=[False, False, True],
    )
    top_three = ranked.head(3)
    bottom_three = ranked.tail(3).sort_values(
        ["Total_Return_Pct", "Current_Value", "Pair"],
        ascending=[True, True, True],
    )
    best = ranked.iloc[0]
    worst = ranked.iloc[-1]
    ranking_note = (
        "All pairs are tied on return; ordering uses current value and pair name."
        if float(ranked["Total_Return_Pct"].max())
        == float(ranked["Total_Return_Pct"].min())
        else "Pairs are ranked by total return."
    )
    max_drawdown = float(current["Maximum_Drawdown"])
    abnormal = (
        ["Review strategy health alerts"]
        if int(current["Alert_Count"]) > 0
        else []
    )
    watch = []
    if float(current["Current_SGOV_Exposure"]) > float(current["Current_ETF_Exposure"]):
        watch.append("SGOV-heavy allocation: monitor parked sleeves for BUY re-entry signals.")
    if int(current["SELL_Signals"]) > int(current["BUY_Signals"]):
        watch.append("SELL signals dominate current decision streams.")
    watch.append(
        f"Readiness Gate 30 has {int(ready['Gate_30_Days_Remaining'])} market days remaining."
    )

    lines = [
        f"# Weekly Portfolio Review - Week Ending {week_end.date()}",
        "",
        f"**{PAPER_LABEL}**",
        "",
        "## Portfolio Overview",
        "",
        f"- Current Portfolio Value: ${current_value:.6f}",
        f"- Weekly Gain/Loss: ${weekly_change:+.6f}",
        f"- ETF Exposure: ${float(current['Current_ETF_Exposure']):.6f}",
        f"- SGOV Exposure: ${float(current['Current_SGOV_Exposure']):.6f}",
        "",
        "## Signal Changes",
        "",
        "### New BUY Signals",
        "",
        *bullets(changes["BUY"]),
        "",
        "### New SELL Signals",
        "",
        *bullets(changes["SELL"]),
        "",
        "### New HOLD Signals",
        "",
        *bullets(changes["HOLD"]),
        "",
        "## Position Changes",
        "",
        f"- ETF -> SGOV Transitions: {etf_to_sgov}",
        f"- SGOV -> ETF Transitions: {sgov_to_etf}",
        "",
        "## Dividend Activity",
        "",
        f"- Dividends Received: ${dividends_received:.6f}",
        f"- Dividends Reinvested: ${dividends_reinvested:.6f}",
        "",
        "## Earnings Activity",
        "",
        f"- Earnings Exits: {earnings_exits}",
        f"- Earnings Re-entries: {earnings_reentries}",
        "",
        "## Pair Ranking",
        "",
        f"- Ranking Note: {ranking_note}",
        f"- Best Performing Pair: {best['Pair']} ({float(best['Total_Return_Pct']):+.6f}%)",
        f"- Worst Performing Pair: {worst['Pair']} ({float(worst['Total_Return_Pct']):+.6f}%)",
        "- Top 3: " + "; ".join(
            f"{row.Pair} ({float(row.Total_Return_Pct):+.6f}%)"
            for row in top_three.itertuples(index=False)
        ),
        "- Bottom 3: " + "; ".join(
            f"{row.Pair} ({float(row.Total_Return_Pct):+.6f}%)"
            for row in bottom_three.itertuples(index=False)
        ),
        "",
        "## Risk Review",
        "",
        f"- Current Drawdown: {float(current['Current_Drawdown']):.6f}%",
        f"- Maximum Drawdown: {max_drawdown:.6f}%",
        f"- Backtest Expectation: {BACKTEST_MAX_DRAWDOWN:.6f}%",
        f"- Risk Status: {'WITHIN EXPECTATION' if max_drawdown >= BACKTEST_MAX_DRAWDOWN else 'EXCEEDED EXPECTATION'}",
        "",
        "## Readiness Review",
        "",
        f"- Current Live Readiness: {float(ready['Overall_Live_Readiness_Pct']):.6f}%",
        f"- Days Completed: {int(ready['Paper_Trading_Days_Completed'])}",
        f"- Days Remaining to Gate 30: {int(ready['Gate_30_Days_Remaining'])}",
        f"- Days Remaining to Gate 60: {int(ready['Gate_60_Days_Remaining'])}",
        f"- Days Remaining to Gate 90: {int(ready['Gate_90_Days_Remaining'])}",
        "",
        "## Final Review",
        "",
        "### What changed this week?",
        "",
        *bullets(
            changes["BUY"] + changes["SELL"] + changes["HOLD"]
            or ["No signal changes; portfolio state remained unchanged."]
        ),
        "",
        "### What should be watched next week?",
        "",
        *bullets(watch),
        "",
        "### Did any pair show abnormal behavior?",
        "",
        *bullets(abnormal or ["No abnormal pair behavior detected."]),
        "",
        "No broker connection exists. No real orders were submitted.",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")

    assert abs(current_value - float(snapshots.iloc[-1]["Portfolio_Value"])) < 0.000001
    assert int(ready["Paper_Trading_Days_Completed"]) == snapshots["Date"].nunique()
    assert abs(
        float(current["Current_ETF_Exposure"])
        + float(current["Current_SGOV_Exposure"])
        - current_value
    ) < 0.000001
    return {
        "week_end": week_end.strftime("%Y-%m-%d"),
        "weekly_change": weekly_change,
        "best_pair": best["Pair"],
        "worst_pair": worst["Pair"],
        "new_buy": len(changes["BUY"]),
        "new_sell": len(changes["SELL"]),
        "new_hold": len(changes["HOLD"]),
    }


def main() -> int:
    result = generate_weekly_review()
    print(pd.DataFrame([result]).to_string(index=False))
    print(f"\nReview: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
