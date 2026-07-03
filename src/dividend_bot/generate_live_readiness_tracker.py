"""Track PAPER ONLY progress toward staged live-deployment eligibility."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from generate_strategy_health_dashboard import normalized_event_count
from paper_trading_engine import PAPER_LABEL


HEALTH_PATH = Path("strategy_health.csv")
LOG_PATH = Path("paper_trade_log.csv")
SNAPSHOT_PATH = Path("portfolio_snapshot.csv")
OUTPUT_PATH = Path("live_readiness.csv")
REPORT_PATH = Path("live_readiness_report.md")

GATES = {
    30: "Operational Validation Eligible",
    60: "Limited Live Capital Eligible",
    90: "Production Candidate Eligible",
}

OUTPUT_COLUMNS = [
    "Date", "Paper_Trading_Days_Completed", "Days_Remaining_Until_Eligibility",
    "Consecutive_Clean_Validation_Days", "Signal_Changes_Observed",
    "Dividend_Events_Observed", "Earnings_Events_Observed",
    "Total_Dividends_Received", "Total_Dividends_Reinvested",
    "Earnings_Exit_Count", "Earnings_Reentry_Count",
    "ETF_to_SGOV_Transitions", "SGOV_to_ETF_Transitions",
    "Maximum_Drawdown", "Portfolio_Return_Pct", "Clean_Validation_Day",
    "Gate_30_Status", "Gate_30_Progress_Pct", "Gate_30_Days_Remaining",
    "Gate_60_Status", "Gate_60_Progress_Pct", "Gate_60_Days_Remaining",
    "Gate_90_Status", "Gate_90_Progress_Pct", "Gate_90_Days_Remaining",
    "Overall_Live_Readiness_Pct",
]


def gate_status(days: int, threshold: int) -> str:
    if days <= 0:
        return "NOT_STARTED"
    if days < threshold:
        return "IN_PROGRESS"
    return "PASSED"


def event_metrics(log: pd.DataFrame) -> dict[str, int]:
    if log.empty:
        return {
            "etf_to_sgov": 0,
            "sgov_to_etf": 0,
            "earnings": 0,
            "dividends": 0,
            "signal_changes": 0,
        }
    etf_to_sgov = normalized_event_count(log, "PAPER_SELL_TO_SGOV")
    sgov_to_etf = normalized_event_count(log, "PAPER_BUY_FROM_SGOV")
    earnings_exits = normalized_event_count(
        log, "PAPER_SELL_TO_SGOV", "earnings"
    )
    earnings_reentries = normalized_event_count(
        log, "PAPER_BUY_FROM_SGOV", "earnings"
    )
    dividend_rows = log[log["Action"] == "PAPER_DIVIDEND_RECEIVED"]
    dividend_events = len(dividend_rows.drop_duplicates(["Date", "Pair"]))
    signal_rows = log[
        log["Action"].isin(["PAPER_SELL_TO_SGOV", "PAPER_BUY_FROM_SGOV"])
        & log["Reason"].str.contains("signal", case=False, na=False)
    ].copy()
    if signal_rows.empty:
        signal_changes = 0
    else:
        signal_rows["Event_Sleeve"] = signal_rows.apply(
            lambda row: "PAIR"
            if row["Pair"] not in {"GOOW / GGLL", "COIW / CONL", "MST / XXRP"}
            else row["Sleeve"],
            axis=1,
        )
        signal_changes = len(
            signal_rows.drop_duplicates(
                ["Date", "Pair", "Event_Sleeve", "Action"]
            )
        )
    return {
        "etf_to_sgov": etf_to_sgov,
        "sgov_to_etf": sgov_to_etf,
        "earnings": earnings_exits + earnings_reentries,
        "dividends": dividend_events,
        "signal_changes": signal_changes,
    }


def consecutive_clean_days(
    existing: pd.DataFrame,
    current_date: str,
    clean: bool,
) -> int:
    prior = existing[existing["Date"].astype(str) < current_date].copy()
    if not clean:
        return 0
    if prior.empty:
        return 1
    count = 1
    for value in reversed(prior["Clean_Validation_Day"].tolist()):
        normalized = str(value).strip().lower() in {"true", "1", "1.0"}
        if not normalized:
            break
        count += 1
    return count


def generate_live_readiness(
    health_path: Path = HEALTH_PATH,
    log_path: Path = LOG_PATH,
    snapshot_path: Path = SNAPSHOT_PATH,
    output_path: Path = OUTPUT_PATH,
    report_path: Path = REPORT_PATH,
) -> tuple[pd.DataFrame, dict[str, object]]:
    for path in [health_path, log_path, snapshot_path]:
        if not path.exists():
            raise FileNotFoundError(f"Required readiness input not found: {path}")
    health = pd.read_csv(health_path)
    log = pd.read_csv(log_path)
    snapshots = pd.read_csv(snapshot_path)
    if health.empty or snapshots.empty:
        raise ValueError("Health and snapshot inputs must contain data")

    latest = health.iloc[-1]
    current_date = str(latest["As_Of_Date"])
    days = int(snapshots["Date"].astype(str).nunique())
    clean = int(latest["Alert_Count"]) == 0 and bool(latest["Within_Risk_Parameters"])
    existing = (
        pd.read_csv(output_path)
        if output_path.exists()
        else pd.DataFrame(columns=OUTPUT_COLUMNS)
    )
    consecutive = consecutive_clean_days(existing, current_date, clean)
    events = event_metrics(log)

    row = {
        "Date": current_date,
        "Paper_Trading_Days_Completed": days,
        "Days_Remaining_Until_Eligibility": max(30 - days, 0),
        "Consecutive_Clean_Validation_Days": consecutive,
        "Signal_Changes_Observed": events["signal_changes"],
        "Dividend_Events_Observed": events["dividends"],
        "Earnings_Events_Observed": events["earnings"],
        "Total_Dividends_Received": float(latest["Total_Dividends_Received"]),
        "Total_Dividends_Reinvested": float(latest["Total_Dividends_Reinvested"]),
        "Earnings_Exit_Count": int(latest["Earnings_Exit_Count"]),
        "Earnings_Reentry_Count": int(latest["Earnings_Reentry_Count"]),
        "ETF_to_SGOV_Transitions": events["etf_to_sgov"],
        "SGOV_to_ETF_Transitions": events["sgov_to_etf"],
        "Maximum_Drawdown": float(latest["Maximum_Drawdown"]),
        "Portfolio_Return_Pct": float(latest["Total_Return_Pct"]),
        "Clean_Validation_Day": clean,
    }
    for threshold in GATES:
        row[f"Gate_{threshold}_Status"] = gate_status(days, threshold)
        row[f"Gate_{threshold}_Progress_Pct"] = round(
            min(days / threshold * 100, 100.0), 6
        )
        row[f"Gate_{threshold}_Days_Remaining"] = max(threshold - days, 0)
    row["Overall_Live_Readiness_Pct"] = round(
        min(days / 90 * 100, 100.0), 6
    )

    updated = existing[existing["Date"].astype(str) != current_date].copy()
    updated = pd.concat([updated, pd.DataFrame([row])], ignore_index=True)
    updated = updated[OUTPUT_COLUMNS].sort_values("Date")
    updated.to_csv(output_path, index=False)

    gate_lines = []
    for threshold, eligibility in GATES.items():
        gate_lines.extend(
            [
                f"### Gate {threshold}",
                "",
                f"- Eligibility: {eligibility}",
                f"- Status: {row[f'Gate_{threshold}_Status']}",
                f"- Progress: {row[f'Gate_{threshold}_Progress_Pct']:.6f}%",
                f"- Days Remaining: {row[f'Gate_{threshold}_Days_Remaining']}",
                "",
            ]
        )

    report_lines = [
        "# Live Readiness Report",
        "",
        f"**{PAPER_LABEL}**",
        "",
        f"- Paper Trading Days Completed: {days}",
        f"- Days Remaining Until Operational Eligibility: {row['Days_Remaining_Until_Eligibility']}",
        f"- Consecutive Clean Validation Days: {consecutive}",
        f"- Signal Changes Observed: {events['signal_changes']}",
        f"- Dividend Events Observed: {events['dividends']}",
        f"- Earnings Events Observed: {events['earnings']}",
        f"- ETF -> SGOV Transitions: {events['etf_to_sgov']}",
        f"- SGOV -> ETF Transitions: {events['sgov_to_etf']}",
        f"- Maximum Drawdown: {float(latest['Maximum_Drawdown']):.6f}%",
        f"- Portfolio Return: {float(latest['Total_Return_Pct']):.6f}%",
        f"- Overall Live Readiness: {row['Overall_Live_Readiness_Pct']:.6f}%",
        "",
        "## Deployment Gates",
        "",
        *gate_lines,
        "## Final Answer",
        "",
        f"Based on {days} completed paper-market day, the strategy is "
        f"{row['Overall_Live_Readiness_Pct']:.6f}% complete toward the 90-day "
        "production-candidate gate.",
        "",
        "No broker connection exists. No real orders were submitted.",
        "",
    ]
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    return updated, row


def main() -> int:
    history, row = generate_live_readiness()
    print(pd.DataFrame([row]).to_string(index=False))
    print(f"\nReadiness history rows: {len(history)}")
    print(f"Report: {REPORT_PATH}")
    print(f"CSV: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
