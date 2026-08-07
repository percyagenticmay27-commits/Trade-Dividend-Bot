from __future__ import annotations

import csv
import json
from pathlib import Path

from src.dividend_bot.enterprise_strategy_kpi_adapter import build_strategy_kpis


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _dividend_plugin() -> dict:
    return {
        "strategy_id": "DIVIDEND-001",
        "display_name": "Dividend Income Strategy",
        "strategy_type": "DIVIDEND",
        "lifecycle_status": "PRODUCTION",
        "runtime_status": "ONLINE",
        "health_status": "HEALTHY",
        "readiness": "READY",
        "paper_trade_mode": True,
        "paper_compatible": True,
        "advisory_only": True,
        "reporting_only": True,
        "enabled": True,
        "capabilities": ["portfolio", "watchlist", "holdings", "income", "performance", "alerts"],
        "dashboard_artifacts": [],
    }


def test_dividend_detail_evidence_is_attached_to_enterprise_kpi_row(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "paper_state.json",
        {
            "pairs": {
                "AVGW / AVGX": {
                    "a_shares": 2,
                    "b_shares": 1,
                    "last_prices": {"A": 10, "B": 20},
                    "sgov_balance": 30,
                    "total_dividends_received": 4,
                    "a_earnings_lock": False,
                    "b_earnings_lock": True,
                }
            }
        },
    )
    _write_json(
        tmp_path / "candidate_discovery.json",
        {
            "candidates": [
                {
                    "symbol": "AVGW",
                    "on_watchlist": True,
                    "status": "WATCH",
                    "currently_held": True,
                    "market_data_stale": False,
                    "sources": ["TEST"],
                }
            ],
            "warnings": [],
        },
    )
    _write_json(
        tmp_path / "results" / "dividend_paper_trade_performance.json",
        {
            "trade_count": 2,
            "closed_trade_count": 1,
            "open_trade_count": 1,
            "win_count": 1,
            "loss_count": 0,
            "flat_count": 0,
            "win_rate_percent": 100.0,
            "closed_trades": [{"symbol": "AVGW", "pnl": 5.5}],
            "open_trades": [{"symbol": "AVGX"}],
            "warnings": [],
        },
    )
    with (tmp_path / "paper_trade_log.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Date", "Pair", "Sleeve", "Action", "Ticker", "Paper_Value"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "Date": "2026-08-01",
                "Pair": "AVGW / AVGX",
                "Sleeve": "A",
                "Action": "PAPER_DIVIDEND_RECEIVED",
                "Ticker": "AVGW",
                "Paper_Value": "2.50",
            }
        )

    rows, warnings = build_strategy_kpis(
        registry={"strategy_plugins": [_dividend_plugin()]},
        strategy_allocations={"DIVIDEND-001": 5000.0},
        root_dir=tmp_path,
    )

    assert warnings == []
    assert len(rows) == 1
    row = rows[0]
    assert row["strategy_id"] == "DIVIDEND-001"
    assert row["allocated_capital"] == 5000.0
    # 2*10 AVGW + 1*20 AVGX + 30 SGOV reserve = 70.
    assert row["portfolio_value"] == 70.0
    assert row["position_count"] == 3
    assert {item["symbol"] for item in row["holdings"]} == {"AVGW", "AVGX", "SGOV"}
    assert row["positions"] == row["holdings"]
    assert row["watchlist_count"] == 1
    assert row["watchlist"][0]["symbol"] == "AVGW"
    assert row["income"] == 4.0
    assert row["income_events"][0]["amount"] == 2.5
    assert row["realized_gain"] == 5.5
    assert row["performance_detail"]["win_rate_percent"] == 100.0
    assert any(item["alert_type"] == "EARNINGS_LOCK" for item in row["alerts"])
    assert row["risk_flags"] == row["alerts"]
    assert row["paper_trade_mode"] is True
    assert row["reporting_only"] is True


def test_swing_row_does_not_receive_dividend_detail_evidence(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "paper_state.json",
        {
            "pairs": {
                "AVGW / AVGX": {
                    "a_shares": 1,
                    "b_shares": 0,
                    "last_prices": {"A": 10, "B": 20},
                    "sgov_balance": 0,
                }
            }
        },
    )
    swing = {
        "strategy_id": "SWING-001",
        "display_name": "Trade Swing Bot",
        "strategy_type": "SWING",
        "lifecycle_status": "REGISTERED",
        "runtime_status": "REGISTERED",
        "health_status": "HEALTHY",
        "readiness": "AVAILABLE",
        "paper_trade_mode": True,
        "paper_compatible": True,
        "advisory_only": True,
        "reporting_only": True,
        "enabled": True,
        "capabilities": [],
        "dashboard_artifacts": [],
    }

    rows, warnings = build_strategy_kpis(
        registry={"strategy_plugins": [swing]},
        strategy_allocations={"SWING-001": 4500.0},
        root_dir=tmp_path,
    )

    assert warnings == []
    row = rows[0]
    assert row["strategy_id"] == "SWING-001"
    assert row["holdings"] == []
    assert row["watchlist"] == []
    assert row["income_events"] == []
    assert row["performance_detail"] == {}
    assert row["alerts"] == []
    assert row["risk_flags"] == []
