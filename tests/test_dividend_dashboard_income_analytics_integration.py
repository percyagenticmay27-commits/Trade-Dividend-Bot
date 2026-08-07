from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.dividend_dashboard_evidence import build_dividend_dashboard_evidence


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_dashboard_evidence_attaches_income_metrics_to_current_holding(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "paper_state.json",
        {
            "pairs": {
                "AVGW / AVGX": {
                    "a_shares": 2,
                    "b_shares": 0,
                    "last_prices": {"A": 50, "B": 0},
                    "sgov_balance": 0,
                    "total_dividends_received": 3.5,
                }
            }
        },
    )
    _write_json(
        tmp_path / "market_data_snapshot.json",
        {
            "AVGW": {
                "name": "Avantis U.S. Large Cap Value ETF",
                "dividend_yield_percent": 2.4,
                "annual_dividend_rate": 1.20,
                "next_ex_dividend_date": "2026-09-15",
            }
        },
    )

    report = build_dividend_dashboard_evidence(tmp_path)

    assert report["strategy_id"] == "DIVIDEND-001"
    assert report["income"] == 3.5
    assert report["projected_annual_income"] == 2.4
    row = report["holdings"][0]
    assert row["symbol"] == "AVGW"
    assert row["name"] == "Avantis U.S. Large Cap Value ETF"
    assert row["dividend_yield_percent"] == 2.4
    assert row["annual_income"] == 2.4
    assert row["next_ex_dividend_date"] == "2026-09-15"


def test_dashboard_income_metrics_remain_missing_without_authoritative_source(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "paper_state.json",
        {
            "pairs": {
                "AVGW / AVGX": {
                    "a_shares": 1,
                    "b_shares": 0,
                    "last_prices": {"A": 50, "B": 0},
                    "sgov_balance": 0,
                    "total_dividends_received": 0,
                }
            }
        },
    )

    report = build_dividend_dashboard_evidence(tmp_path)
    row = report["holdings"][0]

    assert report["projected_annual_income"] is None
    assert "dividend_yield_percent" not in row
    assert "annual_income" not in row
    assert "next_ex_dividend_date" not in row
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
