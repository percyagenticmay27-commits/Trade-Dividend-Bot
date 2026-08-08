import csv
import json
from pathlib import Path

from src.dividend_bot.dividend_dashboard_evidence import build_dividend_dashboard_evidence


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_dashboard_preserves_current_holdings_and_historical_lifecycle(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "paper_state.json",
        {
            "pairs": {
                "AMDW / AMDL": {
                    "a_shares": 1,
                    "b_shares": 1,
                    "last_prices": {"A": 50, "B": 25},
                    "sgov_balance": 100,
                }
            }
        },
    )
    with (tmp_path / "paper_trade_log.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Date", "Pair", "Sleeve", "Action", "Ticker"])
        writer.writeheader()
        writer.writerow({"Date": "2026-06-18", "Pair": "AMDW / AMDL", "Sleeve": "A", "Action": "PAPER_BUY_OPEN", "Ticker": "AMDW"})
        writer.writerow({"Date": "2026-06-18", "Pair": "AMDW / AMDL", "Sleeve": "B", "Action": "PAPER_BUY_OPEN", "Ticker": "AMDL"})
        writer.writerow({"Date": "2026-06-18", "Pair": "PLTW / PLTU", "Sleeve": "A", "Action": "PAPER_BUY_OPEN", "Ticker": "PLTW"})
        writer.writerow({"Date": "2026-06-18", "Pair": "PLTW / PLTU", "Sleeve": "A", "Action": "PAPER_PARK_IN_SGOV", "Ticker": "PLTW"})
        writer.writerow({"Date": "2026-06-18", "Pair": "PLTW / PLTU", "Sleeve": "B", "Action": "PAPER_BUY_OPEN", "Ticker": "PLTU"})
        writer.writerow({"Date": "2026-06-18", "Pair": "PLTW / PLTU", "Sleeve": "B", "Action": "PAPER_PARK_IN_SGOV", "Ticker": "PLTU"})

    report = build_dividend_dashboard_evidence(tmp_path)

    assert {item["symbol"] for item in report["active_holdings"]} == {"AMDW", "AMDL"}
    assert {item["symbol"] for item in report["reserve_holdings"]} == {"SGOV"}
    assert report["active_position_count"] == 2
    assert report["reserve_position_count"] == 1
    assert {item["symbol"] for item in report["historical_positions"]} == {"PLTW", "PLTU"}
    statuses = {item["symbol"]: item["lifecycle_status"] for item in report["position_lifecycle"]}
    assert statuses["AMDW"] == "OPEN"
    assert statuses["AMDL"] == "OPEN"
    assert statuses["PLTW"] == "PARKED_IN_SGOV"
    assert statuses["PLTU"] == "PARKED_IN_SGOV"
    assert statuses["SGOV"] == "RESERVE"
    assert report["performance_detail"]["position_lifecycle"] == report["position_lifecycle"]


def test_current_holding_rows_receive_lifecycle_traceability(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "paper_state.json",
        {"pairs": {"AMDW / AMDL": {"a_shares": 1, "b_shares": 0, "last_prices": {"A": 50, "B": 25}, "sgov_balance": 0}}},
    )
    with (tmp_path / "paper_trade_log.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Date", "Pair", "Sleeve", "Action", "Ticker"])
        writer.writeheader()
        writer.writerow({"Date": "2026-06-18", "Pair": "AMDW / AMDL", "Sleeve": "A", "Action": "PAPER_BUY_OPEN", "Ticker": "AMDW"})

    report = build_dividend_dashboard_evidence(tmp_path)
    holding = report["active_holdings"][0]

    assert holding["symbol"] == "AMDW"
    assert holding["lifecycle_status"] == "OPEN"
    assert holding["lifecycle_first_purchase_date"] == "2026-06-18"
    assert holding["lifecycle_current_open_date"] == "2026-06-18"
    assert holding["lifecycle_evidence_source"] == "paper_trade_log.csv"
