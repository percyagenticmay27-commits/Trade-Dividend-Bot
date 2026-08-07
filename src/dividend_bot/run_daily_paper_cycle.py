"""Run the PAPER ONLY daily workflow and produce operational summaries."""

from __future__ import annotations

import csv
import json
from datetime import date
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from paper_portfolio_config import PAIR_MANAGED, PAPER_PAIRS
from paper_trading_engine import (
    LOG_PATH,
    PAPER_LABEL,
    REPORT_PATH,
    STATE_PATH,
    MarketDataProvider,
    PaperTradingEngine,
    YahooMarketDataProvider,
)
from generate_strategy_health_dashboard import generate_dashboard
from generate_live_readiness_tracker import generate_live_readiness
from generate_weekly_portfolio_review import generate_weekly_review


SNAPSHOT_PATH = Path("portfolio_snapshot.csv")
CHANGE_SUMMARY_PATH = Path("daily_change_summary.md")
SIGNAL_HISTORY_PATH = Path("paper_signal_history.csv")
SNAPSHOT_COLUMNS = [
    "Date",
    "Portfolio_Value",
    "ETF_Exposure",
    "SGOV_Exposure",
    "Cash_Flow",
    "Dividends_Received",
    "Open_Buckets",
    "SGOV_Buckets",
]


@dataclass
class DailyCyclePaths:
    state: Path = STATE_PATH
    log: Path = LOG_PATH
    report: Path = REPORT_PATH
    snapshot: Path = SNAPSHOT_PATH
    change_summary: Path = CHANGE_SUMMARY_PATH
    comparison: Path = Path("initialization_comparison.md")
    earnings_dir: Path = Path("earnings_data")
    health_report: Path = Path("strategy_health_report.md")
    health_csv: Path = Path("strategy_health.csv")
    pair_health_csv: Path = Path("pair_health.csv")
    readiness_report: Path = Path("live_readiness_report.md")
    readiness_csv: Path = Path("live_readiness.csv")
    signal_history: Path = SIGNAL_HISTORY_PATH
    weekly_review: Path = Path("weekly_portfolio_review.md")


def read_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def read_log(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def state_metrics(state: dict) -> dict[str, float | int]:
    etf = sgov = dividends = 0.0
    open_buckets = sgov_buckets = 0
    for entry in state["pairs"].values():
        etf_value = (
            entry["a_shares"] * entry["last_prices"]["A"]
            + entry["b_shares"] * entry["last_prices"]["B"]
        )
        sgov_value = float(entry["sgov_balance"])
        etf += etf_value
        sgov += sgov_value
        dividends += float(entry["total_dividends_received"])
        if etf_value > 0:
            open_buckets += 1
        if sgov_value > 0:
            sgov_buckets += 1
    return {
        "portfolio": etf + sgov,
        "etf": etf,
        "sgov": sgov,
        "dividends": dividends,
        "open_buckets": open_buckets,
        "sgov_buckets": sgov_buckets,
    }


def changed_signals(before: dict | None, after: dict, target: str) -> list[str]:
    changes = []
    for pair, entry in after["pairs"].items():
        previous = (
            before["pairs"][pair]["last_signal"]
            if before is not None and pair in before.get("pairs", {})
            else {"A": None, "B": None}
        )
        config = PAPER_PAIRS[pair]
        sides = ["A"] if config["architecture"] == PAIR_MANAGED else ["A", "B"]
        for side in sides:
            current_signal = entry["last_signal"][side]
            if current_signal == target and previous.get(side) != target:
                changes.append(f"{pair} {side}: {previous.get(side) or 'NEW'} -> {target}")
    return changes


def next_day_recommendations(state: dict) -> list[str]:
    recommendations = []
    for pair, entry in state["pairs"].items():
        config = PAPER_PAIRS[pair]
        if config["architecture"] == PAIR_MANAGED:
            signal = entry["last_signal"]["A"]
            if entry["a_earnings_lock"]:
                action = "remain in SGOV until post-earnings BUY"
            elif signal == "SELL" and not entry["a_in_sgov"]:
                action = "move A and B to SGOV"
            elif signal == "BUY" and entry["a_in_sgov"]:
                action = "re-enter A and B proportionally"
            else:
                action = "maintain ETF positions" if not entry["a_in_sgov"] else "remain in SGOV"
            recommendations.append(f"{pair}: {action} ({signal})")
        else:
            actions = []
            for side in ["A", "B"]:
                signal = entry["last_signal"][side]
                in_sgov = entry[f"{side.lower()}_in_sgov"]
                locked = entry[f"{side.lower()}_earnings_lock"]
                if locked:
                    action = "remain in SGOV until post-earnings BUY"
                elif signal == "SELL" and not in_sgov:
                    action = "move to SGOV"
                elif signal == "BUY" and in_sgov:
                    action = "re-enter ETF"
                else:
                    action = "remain in SGOV" if in_sgov else "maintain ETF"
                actions.append(f"{side} {action} ({signal})")
            recommendations.append(f"{pair}: " + "; ".join(actions))
    return recommendations


def append_snapshot(path: Path, row: dict[str, object]) -> bool:
    """Append a new market-date snapshot or refresh the existing latest date.

    Paper state can be repriced on a same-market-date rerun even though no new
    trade events are recorded. The health dashboard requires the latest
    snapshot to describe that same current state, so a duplicate date must be
    refreshed in place rather than left stale.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_csv(path)
        if not existing.empty and str(existing.iloc[-1]["Date"]) == str(row["Date"]):
            latest_index = existing.index[-1]
            for column in SNAPSHOT_COLUMNS:
                existing.loc[latest_index, column] = row[column]
            existing.to_csv(path, index=False)
            return False

    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SNAPSHOT_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)
    return True


def update_signal_history(path: Path, state: dict) -> pd.DataFrame:
    current_date = str(state["as_of_date"])
    rows = []
    for pair, entry in state["pairs"].items():
        config = PAPER_PAIRS[pair]
        sides = ["A"] if config["architecture"] == PAIR_MANAGED else ["A", "B"]
        for side in sides:
            rows.append(
                {
                    "Date": current_date,
                    "Pair": pair,
                    "Sleeve": side,
                    "Signal": entry["last_signal"][side],
                }
            )
    existing = (
        pd.read_csv(path)
        if path.exists()
        else pd.DataFrame(columns=["Date", "Pair", "Sleeve", "Signal"])
    )
    existing = existing[existing["Date"].astype(str) != current_date]
    updated = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
    updated = updated.sort_values(["Date", "Pair", "Sleeve"])
    updated.to_csv(path, index=False)
    return updated


def bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- None"]


def write_change_summary(
    path: Path,
    as_of: str,
    buy_signals: list[str],
    sell_signals: list[str],
    earnings_exits: list[str],
    dividend_events: list[str],
    new_actions: list[str],
    before_metrics: dict[str, float | int],
    after_metrics: dict[str, float | int],
    recommendations: list[str],
    duplicate_date: bool,
) -> None:
    value_change = float(after_metrics["portfolio"]) - float(before_metrics["portfolio"])
    lines = [
        f"# Daily Change Summary - {as_of}",
        "",
        f"**{PAPER_LABEL}**",
        "",
        f"- Portfolio Value Change: ${value_change:+.6f}",
        f"- ETF Exposure Change: ${float(after_metrics['etf']) - float(before_metrics['etf']):+.6f}",
        f"- SGOV Exposure Change: ${float(after_metrics['sgov']) - float(before_metrics['sgov']):+.6f}",
        f"- Same Market Date Already Processed: {'Yes' if duplicate_date else 'No'}",
        "",
        "## New BUY Signals",
        "",
        *bullet_lines(buy_signals),
        "",
        "## New SELL Signals",
        "",
        *bullet_lines(sell_signals),
        "",
        "## New Earnings Exits",
        "",
        *bullet_lines(earnings_exits),
        "",
        "## New Dividend Receipts",
        "",
        *bullet_lines(dividend_events),
        "",
        "## Changes From Previous Day",
        "",
        *bullet_lines(new_actions),
        "",
        "## Next Trading Day Recommendations",
        "",
        *bullet_lines(recommendations),
        "",
        "No broker connection exists. No real orders were submitted.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_daily_cycle(
    provider: MarketDataProvider | None = None,
    paths: DailyCyclePaths | None = None,
) -> dict:
    paths = paths or DailyCyclePaths()
    before_state = read_json(paths.state)
    before_log = read_log(paths.log)
    before_metrics = (
        state_metrics(before_state)
        if before_state is not None
        else {"portfolio": 500.0, "etf": 0.0, "sgov": 500.0, "dividends": 0.0, "open_buckets": 0, "sgov_buckets": 10}
    )

    engine = PaperTradingEngine(
        provider=provider or YahooMarketDataProvider(),
        state_path=paths.state,
        log_path=paths.log,
        report_path=paths.report,
        comparison_path=paths.comparison,
        earnings_dir=paths.earnings_dir,
    )
    after_state = engine.run()
    after_log = read_log(paths.log)
    after_metrics = state_metrics(after_state)
    new_log_rows = after_log[len(before_log):]
    as_of = after_state["as_of_date"]
    duplicate_date = (
        before_state is not None
        and before_state.get("last_processed_date") == after_state.get("last_processed_date")
    )

    dividends_today = float(after_metrics["dividends"]) - float(before_metrics["dividends"])
    snapshot = {
        "Date": as_of,
        "Portfolio_Value": round(float(after_metrics["portfolio"]), 6),
        "ETF_Exposure": round(float(after_metrics["etf"]), 6),
        "SGOV_Exposure": round(float(after_metrics["sgov"]), 6),
        "Cash_Flow": round(dividends_today, 6),
        "Dividends_Received": round(dividends_today, 6),
        "Open_Buckets": int(after_metrics["open_buckets"]),
        "SGOV_Buckets": int(after_metrics["sgov_buckets"]),
    }
    append_snapshot(paths.snapshot, snapshot)
    update_signal_history(paths.signal_history, after_state)

    new_actions = [
        f"{row['Pair']} {row['Sleeve']}: {row['Action']} ({row['Reason']})"
        for row in new_log_rows
    ]
    earnings_exits = [
        f"{row['Pair']} {row['Sleeve']}: {row['Action']}"
        for row in new_log_rows
        if "earnings" in row["Reason"].lower() and "SELL" in row["Action"]
    ]
    dividend_events = [
        f"{row['Pair']}: ${float(row['Paper_Value']):.6f}"
        for row in new_log_rows
        if row["Action"] == "PAPER_DIVIDEND_RECEIVED"
    ]
    write_change_summary(
        paths.change_summary,
        as_of,
        changed_signals(before_state, after_state, "BUY"),
        changed_signals(before_state, after_state, "SELL"),
        earnings_exits,
        dividend_events,
        new_actions,
        before_metrics,
        after_metrics,
        next_day_recommendations(after_state),
        duplicate_date,
    )
    generate_dashboard(
        state_path=paths.state,
        log_path=paths.log,
        snapshot_path=paths.snapshot,
        report_path=paths.health_report,
        health_path=paths.health_csv,
        pair_health_path=paths.pair_health_csv,
    )
    generate_live_readiness(
        health_path=paths.health_csv,
        log_path=paths.log,
        snapshot_path=paths.snapshot,
        output_path=paths.readiness_csv,
        report_path=paths.readiness_report,
    )
    if date.today().weekday() == 4:
        generate_weekly_review(
            health_path=paths.health_csv,
            pair_health_path=paths.pair_health_csv,
            readiness_path=paths.readiness_csv,
            snapshot_path=paths.snapshot,
            log_path=paths.log,
            signal_history_path=paths.signal_history,
            output_path=paths.weekly_review,
        )

    assert abs(float(after_metrics["portfolio"]) - float(after_metrics["etf"]) - float(after_metrics["sgov"])) < 0.000001
    return {
        "state": after_state,
        "snapshot": snapshot,
        "new_log_rows": new_log_rows,
        "duplicate_date": duplicate_date,
        "recommendations": next_day_recommendations(after_state),
    }


def main() -> int:
    print(PAPER_LABEL)
    result = run_daily_cycle()
    print(f"Daily cycle complete through: {result['state']['as_of_date']}")
    print(f"New log rows: {len(result['new_log_rows'])}")
    print(f"Same date already processed: {result['duplicate_date']}")
    print(f"Snapshot: {SNAPSHOT_PATH}")
    print(f"Change summary: {CHANGE_SUMMARY_PATH}")
    print("Strategy health dashboard refreshed")
    print("Live readiness tracker refreshed")

    try:
        from src.dividend_bot.dividend_daily_evidence_refresh import (
            refresh_dividend_daily_evidence,
        )

        evidence = refresh_dividend_daily_evidence(".")
        print(f"Dividend evidence refresh: {evidence['status']}")
        print(f"Dividend intelligence cycle: {evidence['daily_dividend_cycle_status']}")
        print(f"Candidate count: {evidence['candidate_count']}")
        print(f"Watchlist count: {evidence['watchlist_count']}")
        print(f"Dividend KPI evidence: {evidence['kpi_evidence_path']}")
        for warning in evidence["warnings"]:
            print(f"EVIDENCE WARNING: {warning}")
        for error in evidence["errors"]:
            print(f"EVIDENCE ERROR: {error}")
    except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
        # Preserve the operational paper cycle while making missing dashboard
        # evidence explicit. Email/report delivery can still proceed, but the
        # Enterprise dashboard will correctly remain partial until repaired.
        print(f"Dividend evidence refresh: PARTIAL ({exc})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
