from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.enterprise_strategy_assignments_ui import (
    load_strategy_assignment_report,
)
from src.dividend_bot.enterprise_strategy_kpi_adapter import build_strategy_kpis


def _registry(root: Path) -> dict:
    return {
        "strategy_plugins": [
            {
                "strategy_id": "SWING-001",
                "display_name": "Trade Swing Bot",
                "strategy_type": "SWING",
                "lifecycle_status": "PRODUCTION",
                "runtime_status": "AVAILABLE",
                "health_status": "HEALTHY",
                "readiness": "READY",
                "paper_trade_mode": True,
                "paper_compatible": True,
                "advisory_only": True,
                "reporting_only": True,
                "enabled": True,
                "repository_root": str(root),
                "capabilities": ["manual_strategy", "strategy_assignments"],
                "dashboard_artifacts": [
                    {
                        "artifact_id": "strategy_assignments",
                        "artifact_type": "strategy_assignments",
                        "path": "results/enterprise_strategy_assignments.json",
                        "format": "JSON",
                        "scope": "STRATEGY",
                        "authoritative": True,
                        "required": False,
                    }
                ],
            }
        ]
    }


def _payload() -> dict:
    return {
        "schema_version": "1.1",
        "strategy_id": "SWING-001",
        "paper_trade_mode": True,
        "symbols": [
            {
                "symbol": "SOXL",
                "primary_strategy_id": "SOXL_PRIMARY",
                "shadow_strategy_ids": ["SOXL_SHADOW_1", "SOXL_SHADOW_2"],
            }
        ],
        "strategies": [
            {
                "strategy_id": "SOXL_PRIMARY",
                "name": "SOXL Primary",
                "signal_symbol": "SOXL",
                "vehicle_symbol": "SOXL",
                "timeframe": "1H",
                "engine_id": "BIGBELUGA_RANGE",
                "assignment_mode": "DIRECT",
                "frozen_checkpoint": {"backtest_period": "2023_to_2026"},
            },
            {
                "strategy_id": "SOXL_SHADOW_1",
                "name": "SOXL Shadow 1",
                "signal_symbol": "SOXL",
                "vehicle_symbol": "SOXL",
                "timeframe": "1H",
                "engine_id": "ZERO_LAG",
                "assignment_mode": "SHADOW",
                "frozen_checkpoint": {"backtest_period": "2023_to_2026"},
            },
            {
                "strategy_id": "SOXL_SHADOW_2",
                "name": "SOXL Shadow 2",
                "signal_symbol": "SOXL",
                "vehicle_symbol": "SOXL",
                "timeframe": "4H",
                "engine_id": "ZERO_LAG",
                "assignment_mode": "SHADOW",
                "frozen_checkpoint": {"backtest_period": "2023_to_2026"},
            },
        ],
    }


def test_registry_v2_ingestion_preserves_single_strategy_assignments_declaration(tmp_path: Path) -> None:
    artifact = tmp_path / "results/enterprise_strategy_assignments.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps(_payload()), encoding="utf-8")

    rows, warnings = build_strategy_kpis(
        registry=_registry(tmp_path),
        strategy_allocations={"SWING-001": 0.0},
        root_dir=tmp_path,
    )

    assert warnings == []
    assert len(rows) == 1
    row = rows[0]
    matches = [
        item
        for item in row["published_artifacts"]
        if item["artifact_id"] == "strategy_assignments"
        and item["artifact_type"].lower() == "strategy_assignments"
    ]
    assert len(matches) == 1
    assert matches[0]["path"] == "results/enterprise_strategy_assignments.json"
    assert row["evidence_root"] == str(tmp_path.resolve())
    assert str(artifact.resolve()) in row["evidence_paths"]
    assert row["allocated_capital"] == 0.0
    assert row["holdings"] == []

    report, status = load_strategy_assignment_report(row)
    assert status == "AVAILABLE"
    assert report is not None
    assert report["symbols"][0]["symbol"] == "SOXL"
    assert report["symbols"][0]["primary_strategy_id"] == "SOXL_PRIMARY"
    assert report["symbols"][0]["shadow_strategy_ids"] == ["SOXL_SHADOW_1", "SOXL_SHADOW_2"]


def test_missing_registered_assignment_file_remains_visible_but_unavailable(tmp_path: Path) -> None:
    rows, warnings = build_strategy_kpis(
        registry=_registry(tmp_path),
        strategy_allocations={"SWING-001": 0.0},
        root_dir=tmp_path,
    )

    assert len(rows) == 1
    assert any("declared evidence is missing" in warning for warning in warnings)
    report, status = load_strategy_assignment_report(rows[0])
    assert report is None
    assert status == "ASSIGNMENT_ARTIFACT_MISSING"
