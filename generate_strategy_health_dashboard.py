"""Generate strategy-health reports from the PAPER ONLY operational ledger."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from paper_portfolio_config import PAIR_MANAGED, PAPER_PAIRS, TOTAL_PAPER_CAPITAL
from paper_trading_engine import PAPER_LABEL


STATE_PATH = Path("paper_state.json")
LOG_PATH = Path("paper_trade_log.csv")
SNAPSHOT_PATH = Path("portfolio_snapshot.csv")
REPORT_PATH = Path("strategy_health_report.md")
HEALTH_PATH = Path("strategy_health.csv")
PAIR_HEALTH_PATH = Path("pair_health.csv")

BACKTEST_MAX_DRAWDOWN = -11.372222
MIN_PAPER_DAYS_FOR_ELIGIBILITY = 60

HEALTH_COLUMNS = [
    "As_Of_Date", "Days_Running", "Starting_Portfolio_Value",
    "Current_Portfolio_Value", "Total_Return_Pct", "Annualized_Return_Estimate",
    "Current_ETF_Exposure", "Current_SGOV_Exposure", "BUY_Signals",
    "SELL_Signals", "HOLD_Signals", "ETF_to_SGOV_Count",
    "SGOV_to_ETF_Count", "Earnings_Exit_Count", "Earnings_Reentry_Count",
    "Total_Dividends_Received", "Total_Dividends_Reinvested",
    "Dividend_Yield_Contribution_Pct", "Current_Drawdown", "Maximum_Drawdown",
    "Average_Drawdown", "Alert_Count", "Within_Risk_Parameters",
    "Live_Deployment_Eligible",
]

PAIR_COLUMNS = [
    "Pair", "Current_State", "Current_Value", "Total_Return_Pct",
    "Days_Invested", "Days_In_SGOV", "Dividends_Received",
]


def load_inputs(
    state_path: Path = STATE_PATH,
    log_path: Path = LOG_PATH,
    snapshot_path: Path = SNAPSHOT_PATH,
) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    for path in [state_path, log_path, snapshot_path]:
        if not path.exists():
            raise FileNotFoundError(f"Required paper input not found: {path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    log = pd.read_csv(log_path)
    snapshots = pd.read_csv(snapshot_path, parse_dates=["Date"])
    if snapshots.empty:
        raise ValueError("portfolio_snapshot.csv has no rows")
    snapshots = snapshots.sort_values("Date").drop_duplicates("Date", keep="last")
    return state, log, snapshots


def pair_value(entry: dict) -> tuple[float, float, float]:
    etf = (
        float(entry["a_shares"]) * float(entry["last_prices"]["A"])
        + float(entry["b_shares"]) * float(entry["last_prices"]["B"])
    )
    sgov = float(entry["sgov_balance"])
    return etf + sgov, etf, sgov


def normalized_event_count(log: pd.DataFrame, action: str, reason=None) -> int:
    rows = log[log["Action"] == action].copy()
    if reason is not None:
        rows = rows[rows["Reason"].str.contains(reason, case=False, na=False)]
    if rows.empty:
        return 0
    rows["Event_Sleeve"] = rows.apply(
        lambda row: "PAIR"
        if PAPER_PAIRS[row["Pair"]]["architecture"] == PAIR_MANAGED
        else row["Sleeve"],
        axis=1,
    )
    return len(rows.drop_duplicates(["Date", "Pair", "Event_Sleeve", "Action"]))


def current_signal_counts(state: dict) -> dict[str, int]:
    counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
    for pair, entry in state["pairs"].items():
        config = PAPER_PAIRS[pair]
        sides = ["A"] if config["architecture"] == PAIR_MANAGED else ["A", "B"]
        for side in sides:
            signal = entry["last_signal"][side]
            if signal not in counts:
                raise ValueError(f"Unsupported signal in state: {pair} {side} {signal}")
            counts[signal] += 1
    return counts


def drawdown_metrics(snapshots: pd.DataFrame) -> tuple[float, float, float]:
    values = snapshots["Portfolio_Value"].astype(float)
    drawdowns = (values / values.cummax() - 1) * 100
    return float(drawdowns.iloc[-1]), float(drawdowns.min()), float(drawdowns.mean())


def sleeve_states_by_date(log: pd.DataFrame, snapshot_dates: pd.Series) -> dict:
    rows = log.copy()
    rows["Date"] = pd.to_datetime(rows["Date"])
    states = {
        pair: {"A": None, "B": None}
        for pair in PAPER_PAIRS
    }
    daily = {}
    for snapshot_date in pd.DatetimeIndex(snapshot_dates).sort_values():
        eligible = rows[rows["Date"] <= snapshot_date]
        states = {pair: {"A": None, "B": None} for pair in PAPER_PAIRS}
        for row in eligible.itertuples(index=False):
            if row.Action in {"PAPER_BUY_OPEN", "PAPER_BUY_FROM_SGOV"}:
                states[row.Pair][row.Sleeve] = "ETF"
            elif row.Action in {"PAPER_PARK_IN_SGOV", "PAPER_SELL_TO_SGOV"}:
                states[row.Pair][row.Sleeve] = "SGOV"
        daily[pd.Timestamp(snapshot_date)] = {
            pair: sides.copy() for pair, sides in states.items()
        }
    return daily


def build_pair_health(
    state: dict,
    log: pd.DataFrame,
    snapshots: pd.DataFrame,
) -> pd.DataFrame:
    daily_states = sleeve_states_by_date(log, snapshots["Date"])
    rows = []
    for pair, entry in state["pairs"].items():
        a_state = "SGOV" if entry["a_in_sgov"] else "ETF"
        b_state = "SGOV" if entry["b_in_sgov"] else "ETF"
        current_state = a_state if a_state == b_state else f"A={a_state}; B={b_state}"
        days_invested = days_sgov = 0
        for states in daily_states.values():
            pair_states = states[pair]
            if "ETF" in pair_states.values():
                days_invested += 1
            if "SGOV" in pair_states.values():
                days_sgov += 1
        value, _, _ = pair_value(entry)
        starting = float(entry["capital_bucket"])
        rows.append(
            {
                "Pair": pair,
                "Current_State": current_state,
                "Current_Value": round(value, 6),
                "Total_Return_Pct": round((value / starting - 1) * 100, 6),
                "Days_Invested": days_invested,
                "Days_In_SGOV": days_sgov,
                "Dividends_Received": round(float(entry["total_dividends_received"]), 6),
            }
        )
    return pd.DataFrame(rows)[PAIR_COLUMNS]


def build_alerts(
    state: dict,
    snapshots: pd.DataFrame,
    current_value: float,
    etf: float,
    sgov: float,
    max_drawdown: float,
) -> list[str]:
    alerts = []
    if max_drawdown < BACKTEST_MAX_DRAWDOWN:
        alerts.append(
            f"DRAWDOWN: {max_drawdown:.6f}% exceeds Strength Weighted backtest expectation "
            f"of {BACKTEST_MAX_DRAWDOWN:.6f}%."
        )
    latest_snapshot = float(snapshots.iloc[-1]["Portfolio_Value"])
    if abs(current_value - etf - sgov) > 0.000001 or abs(current_value - latest_snapshot) > 0.000001:
        alerts.append("CAPITAL_RECONCILIATION: state exposure does not reconcile to latest snapshot.")

    for pair, entry in state["pairs"].items():
        config = PAPER_PAIRS[pair]
        if config["architecture"] == PAIR_MANAGED:
            if abs(float(entry["a_sgov_balance"])) > 0.000001 or abs(float(entry["b_sgov_balance"])) > 0.000001:
                alerts.append(f"SGOV_MISMATCH: {pair} pair-managed sub-balances must be zero.")
        else:
            sleeve_total = float(entry["a_sgov_balance"]) + float(entry["b_sgov_balance"])
            if abs(sleeve_total - float(entry["sgov_balance"])) > 0.000001:
                alerts.append(f"SGOV_MISMATCH: {pair} independent sleeve balances do not reconcile.")
        if entry["a_earnings_lock"] and not entry["a_in_sgov"]:
            alerts.append(f"EARNINGS_EXIT_FAILURE: {pair} A is locked but not in SGOV.")
        if entry["b_earnings_lock"] and not entry["b_in_sgov"]:
            alerts.append(f"EARNINGS_EXIT_FAILURE: {pair} B is locked but not in SGOV.")

    as_of = pd.Timestamp(state["as_of_date"]).date()
    stale_market_days = int(np.busday_count(as_of.isoformat(), date.today().isoformat()))
    if stale_market_days >= 30:
        alerts.append(f"SIGNAL_STALENESS: no refreshed paper signal state for {stale_market_days} market days.")
    return alerts


def markdown_table(frame: pd.DataFrame) -> str:
    display = frame.copy()
    for column in display.select_dtypes(include="number").columns:
        display[column] = display[column].map(lambda value: f"{value:.6f}")
    headers = list(display.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend(
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in display.itertuples(index=False, name=None)
    )
    return "\n".join(lines)


def generate_dashboard(
    state_path: Path = STATE_PATH,
    log_path: Path = LOG_PATH,
    snapshot_path: Path = SNAPSHOT_PATH,
    report_path: Path = REPORT_PATH,
    health_path: Path = HEALTH_PATH,
    pair_health_path: Path = PAIR_HEALTH_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    state, log, snapshots = load_inputs(state_path, log_path, snapshot_path)
    pair_health = build_pair_health(state, log, snapshots)
    current_value = etf = sgov = dividends = pending = 0.0
    for entry in state["pairs"].values():
        pair_total, pair_etf, pair_sgov = pair_value(entry)
        current_value += pair_total
        etf += pair_etf
        sgov += pair_sgov
        dividends += float(entry["total_dividends_received"])
        pending += float(entry["pending_dividend_a"]) + float(entry["pending_dividend_b"])
    reinvested = dividends - pending
    days_running = len(snapshots)
    total_return = (current_value / TOTAL_PAPER_CAPITAL - 1) * 100
    annualized = (
        ((current_value / TOTAL_PAPER_CAPITAL) ** (252 / days_running) - 1) * 100
        if days_running > 1 and current_value > 0
        else 0.0
    )
    current_dd, max_dd, average_dd = drawdown_metrics(snapshots)
    signals = current_signal_counts(state)
    alerts = build_alerts(state, snapshots, current_value, etf, sgov, max_dd)
    within_risk = max_dd >= BACKTEST_MAX_DRAWDOWN and not any(
        alert.startswith(("CAPITAL_", "SGOV_", "EARNINGS_")) for alert in alerts
    )
    eligible = (
        days_running >= MIN_PAPER_DAYS_FOR_ELIGIBILITY
        and within_risk
        and not alerts
    )

    health = pd.DataFrame(
        [
            {
                "As_Of_Date": state["as_of_date"],
                "Days_Running": days_running,
                "Starting_Portfolio_Value": TOTAL_PAPER_CAPITAL,
                "Current_Portfolio_Value": round(current_value, 6),
                "Total_Return_Pct": round(total_return, 6),
                "Annualized_Return_Estimate": round(annualized, 6),
                "Current_ETF_Exposure": round(etf, 6),
                "Current_SGOV_Exposure": round(sgov, 6),
                "BUY_Signals": signals["BUY"],
                "SELL_Signals": signals["SELL"],
                "HOLD_Signals": signals["HOLD"],
                "ETF_to_SGOV_Count": normalized_event_count(log, "PAPER_SELL_TO_SGOV"),
                "SGOV_to_ETF_Count": normalized_event_count(log, "PAPER_BUY_FROM_SGOV"),
                "Earnings_Exit_Count": normalized_event_count(log, "PAPER_SELL_TO_SGOV", "earnings"),
                "Earnings_Reentry_Count": normalized_event_count(log, "PAPER_BUY_FROM_SGOV", "earnings"),
                "Total_Dividends_Received": round(dividends, 6),
                "Total_Dividends_Reinvested": round(reinvested, 6),
                "Dividend_Yield_Contribution_Pct": round(dividends / TOTAL_PAPER_CAPITAL * 100, 6),
                "Current_Drawdown": round(current_dd, 6),
                "Maximum_Drawdown": round(max_dd, 6),
                "Average_Drawdown": round(average_dd, 6),
                "Alert_Count": len(alerts),
                "Within_Risk_Parameters": within_risk,
                "Live_Deployment_Eligible": eligible,
            }
        ]
    )[HEALTH_COLUMNS]

    assumptions_consistent = not any(
        alert.startswith(("CAPITAL_", "SGOV_", "EARNINGS_")) for alert in alerts
    )
    abnormal_pairs = sorted(
        {
            alert.split(":", 1)[1].strip().split(" ")[0]
            for alert in alerts
            if alert.startswith(("SGOV_MISMATCH", "EARNINGS_EXIT_FAILURE"))
        }
    )
    report_lines = [
        "# Strategy Health Report",
        "",
        f"**{PAPER_LABEL}**",
        "",
        "## Portfolio Health",
        "",
        markdown_table(health),
        "",
        "Annualized return is reported as 0 until at least two unique market snapshots exist.",
        "Signal counts represent the 13 currently active decision streams: seven pair signals and six independent sleeve signals.",
        "",
        "## Pair Health",
        "",
        markdown_table(pair_health),
        "",
        "## Alerts",
        "",
        *([f"- {alert}" for alert in alerts] if alerts else ["- None"]),
        "",
        "## Final Questions",
        "",
        f"1. Paper trading is {'operationally consistent' if assumptions_consistent else 'not consistent'} with accounting, SGOV, signal, dividend, and earnings assumptions; performance consistency needs more history.",
        f"2. Abnormal pairs: {', '.join(abnormal_pairs) if abnormal_pairs else 'None detected'}.",
        f"3. The portfolio is {'within' if within_risk else 'outside'} expected risk parameters; observed max drawdown is {max_dd:.6f}% versus the -11.372222% backtest expectation.",
        f"4. Future live deployment eligibility: {'YES' if eligible else 'NO'}. At least {MIN_PAPER_DAYS_FOR_ELIGIBILITY} unique paper-market days and clean validations are required.",
        "",
        "No broker connection exists. No real orders were submitted.",
        "",
    ]

    assert abs(current_value - etf - sgov) < 0.000001
    assert abs(
        round(current_value, 6)
        - round(float(snapshots.iloc[-1]["Portfolio_Value"]), 6)
    ) < 0.000001
    health.to_csv(health_path, index=False)
    pair_health.to_csv(pair_health_path, index=False)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    return health, pair_health, alerts


def main() -> int:
    health, pair_health, alerts = generate_dashboard()
    print(health.to_string(index=False))
    print(f"\nPairs: {len(pair_health)}")
    print(f"Alerts: {len(alerts)}")
    print(f"Report: {REPORT_PATH}")
    print(f"Health CSV: {HEALTH_PATH}")
    print(f"Pair CSV: {PAIR_HEALTH_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
