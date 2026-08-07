import csv
import json
from pathlib import Path

from src.dividend_bot.dividend_dashboard_evidence import build_dividend_dashboard_evidence


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_dashboard_holdings_receive_position_analytics_and_market_identity(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "paper_state.json",
        {
            "pairs": {
                "AVGW / AVGX": {
                    "a_shares": 2,
                    "b_shares": 0,
                    "last_prices": {"A": 12, "B": 0},
                    "sgov_balance": 20,
                }
            }
        },
    )
    _write_json(
        tmp_path / "market_data_snapshot.json",
        {
            "market_data": [
                {
                    "symbol": "AVGW",
                    "longName": "Avantis U.S. Large Cap Value ETF",
                    "price": 12,
                    "previous_close": 10,
                }
            ]
        },
    )
    with (tmp_path / "paper_trade_log.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Date", "Action", "Ticker", "Shares", "Price", "Paper_Value"])
        writer.writeheader()
        writer.writerow({"Date": "2026-08-01", "Action": "PAPER_BUY_OPEN", "Ticker": "AVGW", "Shares": "2", "Price": "10", "Paper_Value": "20"})

    report = build_dividend_dashboard_evidence(tmp_path)
    holding = next(row for row in report["holdings"] if row["symbol"] == "AVGW")

    assert holding["name"] == "Avantis U.S. Large Cap Value ETF"
    assert holding["cost_basis"] == 20.0
    assert holding["average_cost"] == 10.0
    assert holding["unrealized_pnl"] == 4.0
    assert holding["total_return_percent"] == 20.0
    assert holding["daily_change_percent"] == 20.0
    assert holding["analytics_source"] == "paper_trade_log.csv"
    assert report["unrealized_gain"] == 4.0
    assert "market_data_snapshot.json" in report["evidence_sources"]


def test_dashboard_does_not_invent_position_analytics_without_trade_evidence(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "paper_state.json",
        {"pairs": {"AVGW / AVGX": {"a_shares": 1, "b_shares": 0, "last_prices": {"A": 12, "B": 0}}}},
    )

    report = build_dividend_dashboard_evidence(tmp_path)
    holding = report["holdings"][0]

    assert "cost_basis" not in holding
    assert "average_cost" not in holding
    assert "unrealized_pnl" not in holding
    assert "total_return_percent" not in holding
    assert report["unrealized_gain"] is None
