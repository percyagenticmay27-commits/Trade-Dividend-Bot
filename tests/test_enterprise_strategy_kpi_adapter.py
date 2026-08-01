from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.enterprise_strategy_kpi_adapter import build_strategy_kpis


def _plugin(strategy_id: str, name: str, artifact_path: str | None = None) -> dict:
    artifacts = []
    if artifact_path:
        artifacts.append(
            {
                "artifact_id": f"{strategy_id.lower()}-portfolio",
                "artifact_type": "portfolio",
                "path": artifact_path,
                "format": "JSON",
                "authoritative": True,
                "required": False,
            }
        )
    return {
        "strategy_id": strategy_id,
        "display_name": name,
        "strategy_type": "SWING" if strategy_id.startswith("SWING") else "DIVIDEND",
        "lifecycle_status": "PRODUCTION",
        "runtime_status": "ONLINE",
        "health_status": "HEALTHY",
        "readiness": "READY",
        "capabilities": ["portfolio", "watchlist", "portfolio"],
        "dashboard_artifacts": artifacts,
    }


def test_builds_one_row_per_registered_strategy(tmp_path: Path) -> None:
    dividend = tmp_path / "dividend.json"
    swing = tmp_path / "swing.json"
    dividend.write_text(json.dumps({"portfolio_value": 5100, "holdings": [{"symbol": "A"}]}), encoding="utf-8")
    swing.write_text(json.dumps({"portfolio_value": 4700, "watchlist": [{"symbol": "B"}], "opportunity_quality_score": 88}), encoding="utf-8")
    registry = {
        "strategy_plugins": [
            _plugin("SWING-001", "Trade Swing Bot", str(swing)),
            _plugin("DIVIDEND-001", "Dividend Income Strategy", str(dividend)),
        ]
    }

    rows, warnings = build_strategy_kpis(
        registry=registry,
        strategy_allocations={"DIVIDEND-001": 5000, "SWING-001": 4500},
        root_dir=tmp_path,
    )

    assert warnings == []
    assert [row["strategy_id"] for row in rows] == ["DIVIDEND-001", "SWING-001"]
    assert rows[0]["allocated_capital"] == 5000.0
    assert rows[0]["portfolio_value"] == 5100.0
    assert rows[0]["position_count"] == 1
    assert rows[1]["allocated_capital"] == 4500.0
    assert rows[1]["portfolio_value"] == 4700.0
    assert rows[1]["watchlist_count"] == 1
    assert rows[1]["opportunity_quality"] == 88.0


def test_capabilities_and_artifacts_are_normalized_deterministically(tmp_path: Path) -> None:
    artifact = tmp_path / "portfolio.json"
    artifact.write_text("{}", encoding="utf-8")
    registry = {"strategy_plugins": [_plugin("SWING-001", "Trade Swing Bot", str(artifact))]}

    rows, warnings = build_strategy_kpis(registry=registry, root_dir=tmp_path)

    assert warnings == []
    row = rows[0]
    assert row["capabilities"] == ["portfolio", "watchlist"]
    assert row["capability_count"] == 2
    assert row["published_artifact_count"] == 1
    assert row["published_artifacts"][0]["artifact_type"] == "portfolio"
    assert row["published_artifacts"][0]["authoritative"] is True
    assert row["published_artifacts"][0]["required"] is False


def test_missing_optional_artifact_keeps_registry_only_strategy_visible(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    registry = {"strategy_plugins": [_plugin("SWING-001", "Trade Swing Bot", str(missing))]}

    rows, warnings = build_strategy_kpis(registry=registry, root_dir=tmp_path)

    assert len(rows) == 1
    assert rows[0]["strategy_id"] == "SWING-001"
    assert rows[0]["evidence_status"] == "REGISTRY_ONLY"
    assert rows[0]["evidence_paths"] == []
    assert any("declared evidence is missing" in warning for warning in warnings)


def test_registry_status_fields_are_preserved(tmp_path: Path) -> None:
    plugin = _plugin("DIVIDEND-001", "Dividend Income Strategy")
    registry = {"strategy_plugins": [plugin]}

    rows, _ = build_strategy_kpis(registry=registry, root_dir=tmp_path)

    row = rows[0]
    assert row["lifecycle_status"] == "PRODUCTION"
    assert row["runtime_status"] == "ONLINE"
    assert row["health_status"] == "HEALTHY"
    assert row["readiness"] == "READY"


def test_no_strategy_plugins_returns_warning() -> None:
    rows, warnings = build_strategy_kpis(registry={})

    assert rows == []
    assert warnings == ["Enterprise registry does not contain strategy_plugins."]


def test_adapter_is_read_only(tmp_path: Path) -> None:
    artifact = tmp_path / "portfolio.json"
    original = json.dumps({"portfolio_value": 1234})
    artifact.write_text(original, encoding="utf-8")
    registry = {"strategy_plugins": [_plugin("DIVIDEND-001", "Dividend Income Strategy", str(artifact))]}

    build_strategy_kpis(registry=registry, root_dir=tmp_path)

    assert artifact.read_text(encoding="utf-8") == original
