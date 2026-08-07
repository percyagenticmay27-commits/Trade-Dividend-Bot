from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.dividend_strategy_kpi_evidence import (
    build_dividend_strategy_kpi_evidence,
)


def test_cross_strategy_performance_uses_dividend_row_only(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    (results / "strategy_performance_analytics.json").write_text(
        json.dumps({
            "strategies": [
                {"strategy_id": "SWING-001", "win_rate_pct": 91.0},
                {"strategy_id": "DIVIDEND-001", "win_rate_pct": 64.0},
            ]
        }),
        encoding="utf-8",
    )

    report = build_dividend_strategy_kpi_evidence(tmp_path)

    assert report["win_rate_percent"] == 64.0
    assert report["calculation_methods"]["win_rate_percent"] == "DECLARED_DIVIDEND_WIN_RATE"
