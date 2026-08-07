from __future__ import annotations

from pathlib import Path

import pandas as pd

from run_daily_paper_cycle import SNAPSHOT_COLUMNS, append_snapshot


def _row(portfolio_value: float, etf: float, sgov: float) -> dict[str, object]:
    return {
        "Date": "2026-08-06",
        "Portfolio_Value": portfolio_value,
        "ETF_Exposure": etf,
        "SGOV_Exposure": sgov,
        "Cash_Flow": 0.0,
        "Dividends_Received": 0.0,
        "Open_Buckets": 4,
        "SGOV_Buckets": 6,
    }


def test_same_date_snapshot_refreshes_latest_values_without_duplicate_row(tmp_path: Path) -> None:
    path = tmp_path / "portfolio_snapshot.csv"
    pd.DataFrame([_row(500.0, 300.0, 200.0)], columns=SNAPSHOT_COLUMNS).to_csv(path, index=False)

    appended = append_snapshot(path, _row(503.25, 303.25, 200.0))

    frame = pd.read_csv(path)
    assert appended is False
    assert len(frame) == 1
    assert float(frame.iloc[-1]["Portfolio_Value"]) == 503.25
    assert float(frame.iloc[-1]["ETF_Exposure"]) == 303.25
    assert float(frame.iloc[-1]["SGOV_Exposure"]) == 200.0
    assert abs(
        float(frame.iloc[-1]["Portfolio_Value"])
        - float(frame.iloc[-1]["ETF_Exposure"])
        - float(frame.iloc[-1]["SGOV_Exposure"])
    ) < 0.000001
