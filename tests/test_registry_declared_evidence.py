from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.registry_declared_evidence import (
    MAX_INLINE_ARTIFACT_BYTES,
    load_registry_declared_evidence,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _registry(path: Path, *, required: bool = False) -> dict[str, object]:
    return {
        "registry_contract_version": "2.0",
        "strategy_plugins": [
            {
                "strategy_id": "DIVIDEND-001",
                "display_name": "Dividend Income Strategy",
                "plugin_contract_version": "2.0",
                "dashboard_artifacts": [],
            },
            {
                "strategy_id": "SWING-001",
                "display_name": "Trade Swing Bot",
                "plugin_contract_version": "2.0",
                "dashboard_artifacts": [
                    {
                        "artifact_id": "swing_opportunity_quality",
                        "artifact_type": "OPPORTUNITY_QUALITY",
                        "path": str(path),
                        "format": "JSON",
                        "scope": "STRATEGY",
                        "authoritative": True,
                        "required": required,
                    }
                ],
            },
        ],
    }


def test_reads_declared_json_without_importing_plugin_code(tmp_path: Path) -> None:
    artifact = tmp_path / "swing" / "results" / "opportunity_quality.json"
    _write_json(artifact, {"rows": [{"symbol": "AMD", "score": 91}]})

    strategies, warnings = load_registry_declared_evidence(_registry(artifact), root_dir=tmp_path)

    assert warnings == []
    assert [item["strategy_id"] for item in strategies] == ["DIVIDEND-001", "SWING-001"]
    swing = strategies[1]
    assert swing["evidence_status"] == "AVAILABLE"
    assert swing["available_artifact_count"] == 1
    assert swing["artifacts"][0]["payload"]["rows"][0]["symbol"] == "AMD"
    assert swing["artifacts"][0]["payload_policy"] == "INLINE"
    assert swing["artifacts"][0]["provenance"]["source_type"] == "PUBLISHED_ARTIFACT"
    assert swing["artifacts"][0]["provenance"]["authoritative"] is True


def test_optional_missing_artifact_warns_and_keeps_plugin_visible(tmp_path: Path) -> None:
    strategies, warnings = load_registry_declared_evidence(
        _registry(tmp_path / "missing.json"), root_dir=tmp_path
    )

    swing = strategies[1]
    assert swing["evidence_status"] == "REGISTRY_ONLY"
    assert swing["required_artifact_failure"] is False
    assert swing["declared_artifact_count"] == 1
    assert swing["available_artifact_count"] == 0
    assert len(warnings) == 1
    assert "declared artifact missing" in warnings[0]


def test_required_missing_artifact_isolated_to_declaring_strategy(tmp_path: Path) -> None:
    strategies, warnings = load_registry_declared_evidence(
        _registry(tmp_path / "missing.json", required=True), root_dir=tmp_path
    )

    dividend, swing = strategies
    assert dividend["evidence_status"] == "REGISTRY_ONLY"
    assert swing["evidence_status"] == "REQUIRED_EVIDENCE_MISSING"
    assert swing["required_artifact_failure"] is True
    assert len(warnings) == 1


def test_malformed_artifact_is_reported_without_crashing(tmp_path: Path) -> None:
    artifact = tmp_path / "bad.json"
    artifact.write_text("{bad", encoding="utf-8")

    strategies, warnings = load_registry_declared_evidence(_registry(artifact), root_dir=tmp_path)

    assert strategies[1]["evidence_status"] == "REGISTRY_ONLY"
    assert strategies[1]["artifacts"][0]["available"] is False
    assert "invalid declared artifact" in warnings[0]


def test_registry_level_artifact_index_is_supported(tmp_path: Path) -> None:
    artifact = tmp_path / "portfolio.json"
    _write_json(artifact, {"portfolio_value": 1000})
    registry = {
        "strategy_plugins": [
            {"strategy_id": "SWING-001", "display_name": "Trade Swing Bot"}
        ],
        "strategy_contracts": {
            "artifacts_by_strategy": {
                "SWING-001": [
                    {
                        "artifact_id": "portfolio",
                        "artifact_type": "PORTFOLIO",
                        "path": str(artifact),
                        "format": "JSON",
                        "scope": "STRATEGY",
                        "authoritative": True,
                        "required": False,
                    }
                ]
            }
        },
    }

    strategies, warnings = load_registry_declared_evidence(registry, root_dir=tmp_path)

    assert warnings == []
    assert strategies[0]["evidence_status"] == "AVAILABLE"
    assert strategies[0]["artifacts"][0]["payload"]["portfolio_value"] == 1000


def test_deterministic_strategy_and_artifact_order(tmp_path: Path) -> None:
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    _write_json(first, {"a": 1})
    _write_json(second, {"b": 2})
    registry = {
        "strategy_plugins": [
            {
                "strategy_id": "Z-STRATEGY",
                "dashboard_artifacts": [
                    {"artifact_id": "z", "artifact_type": "RISK", "path": str(second), "format": "JSON"},
                    {"artifact_id": "a", "artifact_type": "PORTFOLIO", "path": str(first), "format": "JSON"},
                ],
            },
            {"strategy_id": "A-STRATEGY", "dashboard_artifacts": []},
        ]
    }

    strategies, warnings = load_registry_declared_evidence(registry, root_dir=tmp_path)

    assert warnings == []
    assert [item["strategy_id"] for item in strategies] == ["A-STRATEGY", "Z-STRATEGY"]
    assert [item["artifact_id"] for item in strategies[1]["artifacts"]] == ["a", "z"]


def test_enterprise_scope_dashboard_is_metadata_only_to_prevent_recursive_growth(tmp_path: Path) -> None:
    artifact = tmp_path / "results" / "ai_cio_executive_dashboard.json"
    _write_json(artifact, {"strategy_kpis": [{"strategy_id": "DIVIDEND-001"}], "nested": {"large": "payload"}})
    registry = {
        "strategy_plugins": [
            {
                "strategy_id": "DIVIDEND-001",
                "dashboard_artifacts": [
                    {
                        "artifact_id": "ai_cio_executive_dashboard",
                        "artifact_type": "EXECUTIVE_DASHBOARD",
                        "path": str(artifact),
                        "format": "JSON",
                        "scope": "ENTERPRISE",
                        "authoritative": True,
                        "required": False,
                    }
                ],
            }
        ]
    }

    strategies, warnings = load_registry_declared_evidence(registry, root_dir=tmp_path)

    assert warnings == []
    record = strategies[0]["artifacts"][0]
    assert strategies[0]["evidence_status"] == "AVAILABLE"
    assert record["available"] is True
    assert record["payload"] is None
    assert record["payload_policy"] == "METADATA_ONLY_ENTERPRISE_SCOPE"
    assert record["size_bytes"] == artifact.stat().st_size


def test_oversized_strategy_artifact_is_metadata_only(tmp_path: Path) -> None:
    artifact = tmp_path / "large.json"
    artifact.write_bytes(b" " * (MAX_INLINE_ARTIFACT_BYTES + 1))
    registry = {
        "strategy_plugins": [
            {
                "strategy_id": "DIVIDEND-001",
                "dashboard_artifacts": [
                    {
                        "artifact_id": "large_strategy_report",
                        "artifact_type": "PORTFOLIO",
                        "path": str(artifact),
                        "format": "JSON",
                        "scope": "STRATEGY",
                        "authoritative": True,
                        "required": False,
                    }
                ],
            }
        ]
    }

    strategies, warnings = load_registry_declared_evidence(registry, root_dir=tmp_path)

    assert warnings == []
    record = strategies[0]["artifacts"][0]
    assert record["available"] is True
    assert record["payload"] is None
    assert record["payload_policy"] == "METADATA_ONLY_SIZE_LIMIT"
    assert record["size_bytes"] == MAX_INLINE_ARTIFACT_BYTES + 1
