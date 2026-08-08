import csv
import json
from pathlib import Path

from src.dividend_bot.enterprise_strategy_kpi_adapter import build_strategy_kpis


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _plugin() -> dict:
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
        "capabilities": ["holdings", "performance"],
        "dashboard_artifacts": [],
    }


def test_enterprise_kpi_preserves_current_and_historical_lifecycle_evidence(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "paper_state.json",
        {"pairs": {"AMDW / AMDL": {"a_shares": 1, "b_shares": 0, "last_prices": {"A": 50, "B": 25}, "sgov_balance": 100}}},
    )
    with (tmp_path / "paper_trade_log.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Date", "Pair", "Sleeve", "Action", "Ticker"])
        writer.writeheader()
        writer.writerow({"Date": "2026-06-18", "Pair": "AMDW / AMDL", "Sleeve": "A", "Action": "PAPER_BUY_OPEN", "Ticker": "AMDW"})
        writer.writerow({"Date": "2026-06-18", "Pair": "PLTW / PLTU", "Sleeve": "A", "Action": "PAPER_BUY_OPEN", "Ticker": "PLTW"})
        writer.writerow({"Date": "2026-06-18", "Pair": "PLTW / PLTU", "Sleeve": "A", "Action": "PAPER_PARK_IN_SGOV", "Ticker": "PLTW"})

    rows, warnings = build_strategy_kpis(
        registry={"strategy_plugins": [_plugin()]},
        strategy_allocations={"DIVIDEND-001": 5000.0},
        root_dir=tmp_path,
    )

    assert warnings == []
    row = rows[0]
    current = {item["symbol"]: item for item in row["holdings"]}
    assert current["AMDW"]["lifecycle_status"] == "OPEN"
    assert current["SGOV"]["lifecycle_status"] == "RESERVE"

    lifecycle = row["performance_detail"]["position_lifecycle"]
    by_symbol = {item["symbol"]: item for item in lifecycle}
    assert by_symbol["AMDW"]["lifecycle_status"] == "OPEN"
    assert by_symbol["PLTW"]["lifecycle_status"] == "PARKED_IN_SGOV"
    assert by_symbol["PLTW"]["is_current_holding"] is False
    assert by_symbol["SGOV"]["lifecycle_status"] == "RESERVE"
