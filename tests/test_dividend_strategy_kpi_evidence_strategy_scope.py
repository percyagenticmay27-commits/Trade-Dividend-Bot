from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.dividend_strategy_kpi_evidence import (
    build_dividend_strategy_kpi_evidence,
)


def test_canonical_dividend_performance_precedes_stale_cross_strategy_file(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"
    results.mkdir()

    # Authoritative DIVIDEND-001 performance.
    (results / "dividend_paper_trade_performance.json").write_text(
        json.dumps({
            "strategy_id": "DIVIDEND-001",
            "closed_trade_count": 6,
            "open_trade_count": 0,
            "win_count": 0,
            "loss_count": 6,
            "win_rate_percent": 0.0,
        }),
        encoding="utf-8",
    )

    # Deliberately stale legacy/cross-strategy evidence.
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

    assert report["win_rate_percent"] == 0.0
    assert report["metric_sources"]["win_rate_percent"].endswith(
        "results/dividend_paper_trade_performance.json"
    )
    assert (
        report["calculation_methods"]["win_rate_percent"]
        == "DECLARED_DIVIDEND_WIN_RATE"
    )
