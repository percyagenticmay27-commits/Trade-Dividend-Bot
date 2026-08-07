import csv
import json
from pathlib import Path

from src.dividend_bot.dividend_dashboard_evidence import build_dividend_dashboard_evidence


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_builds_strategy_scoped_holdings_income_watchlist_and_performance(tmp_path: Path) -> None:
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
                {"symbol": "AVGW", "on_watchlist": True, "status": "WATCH", "currently_held": True, "market_data_stale": False, "sources": ["TEST"]},
                {"symbol": "SGOV", "on_watchlist": False, "status": "READY"},
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
        writer = csv.DictWriter(handle, fieldnames=["Date", "Pair", "Sleeve", "Action", "Ticker", "Paper_Value"])
        writer.writeheader()
        writer.writerow({"Date": "2026-08-01", "Pair": "AVGW / AVGX", "Sleeve": "A", "Action": "PAPER_DIVIDEND_RECEIVED", "Ticker": "AVGW", "Paper_Value": "2.50"})

    report = build_dividend_dashboard_evidence(tmp_path)

    assert report["strategy_id"] == "DIVIDEND-001"
    assert report["portfolio_value"] == 90.0
    assert report["position_count"] == 3
    assert {row["symbol"] for row in report["holdings"]} == {"AVGW", "AVGX", "SGOV"}
    assert report["watchlist_count"] == 1
    assert report["watchlist"][0]["symbol"] == "AVGW"
    assert report["income"] == 4.0
    assert report["income_events"][0]["amount"] == 2.5
    assert report["realized_gain"] == 5.5
    assert report["performance_detail"]["win_rate_percent"] == 100.0
    assert any(item["alert_type"] == "EARNINGS_LOCK" for item in report["alerts"])


def test_missing_optional_sources_do_not_fabricate_detail(tmp_path: Path) -> None:
    report = build_dividend_dashboard_evidence(tmp_path)

    assert report["portfolio_value"] is None
    assert report["holdings"] == []
    assert report["watchlist"] == []
    assert report["income_events"] == []
    assert report["unrealized_gain"] is None
    assert report["evidence_sources"] == []


def test_dashboard_evidence_preserves_governance_and_execution_locks(tmp_path: Path) -> None:
    report = build_dividend_dashboard_evidence(tmp_path)

    assert report["paper_trade_mode"] is True
    assert report["reporting_only"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["order_placement_enabled"] is False
    assert report["capital_movement_enabled"] is False
    assert report["automatic_activation_allowed"] is False
    assert report["investor_governance_required"] is True
