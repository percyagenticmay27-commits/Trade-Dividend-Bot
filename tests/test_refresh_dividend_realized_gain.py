from __future__ import annotations

import csv
import json
from pathlib import Path

import refresh_enterprise_dashboards as launcher


def _write_log(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "Date",
                "Pair",
                "Sleeve",
                "Signal",
                "Action",
                "Ticker",
                "Shares",
                "Price",
                "Paper_Value",
                "Reason",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "Date": "2026-08-01",
                "Pair": "TEST / TESTX",
                "Sleeve": "A",
                "Signal": "BUY",
                "Action": "PAPER_BUY_OPEN",
                "Ticker": "TEST",
                "Shares": "10",
                "Price": "10",
                "Paper_Value": "100",
                "Reason": "test open",
            }
        )
        writer.writerow(
            {
                "Date": "2026-08-02",
                "Pair": "TEST / TESTX",
                "Sleeve": "A",
                "Signal": "SELL",
                "Action": "PAPER_SELL_TO_SGOV",
                "Ticker": "TEST",
                "Shares": "10",
                "Price": "12.5",
                "Paper_Value": "125",
                "Reason": "test close",
            }
        )


def test_dashboard_refresh_rebuilds_realized_gain_before_kpi_read(
    tmp_path: Path,
    monkeypatch,
) -> None:
    results = tmp_path / "results"
    state = tmp_path / "state"
    _write_log(tmp_path / "paper_trade_log.csv")

    results.mkdir(parents=True, exist_ok=True)
    stale = {
        "strategy_id": "DIVIDEND-001",
        "closed_trade_count": 1,
        "closed_trades": [{"symbol": "STALE", "pnl": -999.0}],
        "paper_trade_mode": True,
    }
    (results / "dividend_paper_trade_performance.json").write_text(
        json.dumps(stale), encoding="utf-8"
    )

    observed: dict[str, float] = {}

    def fake_build_strategy_kpis(*, registry, strategy_allocations, root_dir):
        payload = json.loads(
            (Path(root_dir) / "results" / "dividend_paper_trade_performance.json").read_text(
                encoding="utf-8"
            )
        )
        observed["realized_gain"] = round(
            sum(float(row.get("pnl") or 0.0) for row in payload.get("closed_trades", [])),
            2,
        )
        return [], []

    monkeypatch.setattr(launcher, "build_strategy_kpis", fake_build_strategy_kpis)

    launcher.refresh_enterprise_dashboards(
        root_dir=tmp_path,
        results_dir=results,
        state_dir=state,
    )

    refreshed = json.loads(
        (results / "dividend_paper_trade_performance.json").read_text(encoding="utf-8")
    )
    assert refreshed["paper_trade_mode"] is True
    assert refreshed["live_trading_enabled"] is False
    assert refreshed["broker_execution_enabled"] is False
    assert refreshed["order_placement_enabled"] is False
    assert refreshed["capital_movement_enabled"] is False
    assert refreshed["closed_trade_count"] == 1
    assert refreshed["closed_trades"][0]["pnl"] == 25.0
    assert observed["realized_gain"] == 25.0
