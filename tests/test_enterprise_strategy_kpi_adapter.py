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
        "paper_trade_mode": True,
        "paper_compatible": True,
        "advisory_only": True,
        "reporting_only": True,
        "enabled": True,
        "capabilities": ["portfolio", "watchlist", "portfolio"],
        "dashboard_artifacts": artifacts,
    }


def test_builds_one_row_per_registered_strategy(tmp_path: Path) -> None:
    dividend = tmp_path / "dividend.json"
    swing = tmp_path / "swing.json"
    dividend.write_text(
        json.dumps({"portfolio_value": 5100, "holdings": [{"symbol": "A"}]}),
        encoding="utf-8",
    )
    swing.write_text(
        json.dumps(
            {
                "portfolio_value": 4700,
                "watchlist": [{"symbol": "B"}],
                "opportunity_quality_score": 88,
            }
        ),
        encoding="utf-8",
    )
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
    registry = {
        "strategy_plugins": [
            _plugin("SWING-001", "Trade Swing Bot", str(artifact))
        ]
    }

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
    registry = {
        "strategy_plugins": [
            _plugin("SWING-001", "Trade Swing Bot", str(missing))
        ]
    }

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


def test_discovery_safety_fields_are_preserved_in_kpi_record(tmp_path: Path) -> None:
    registry = {
        "strategy_plugins": [
            _plugin("SWING-001", "Trade Swing Bot")
        ]
    }

    rows, warnings = build_strategy_kpis(registry=registry, root_dir=tmp_path)

    assert warnings == []
    row = rows[0]
    assert row["enabled"] is True
    assert row["paper_trade_mode"] is True
    assert row["paper_compatible"] is True
    assert row["advisory_only"] is True
    assert row["reporting_only"] is True


def test_duplicate_strategy_id_is_filtered_by_discovery_layer(tmp_path: Path) -> None:
    registry = {
        "strategy_plugins": [
            _plugin("SWING-001", "Trade Swing Bot"),
            _plugin("SWING-001", "Duplicate Swing Bot"),
        ]
    }

    rows, warnings = build_strategy_kpis(registry=registry, root_dir=tmp_path)

    assert len(rows) == 1
    assert rows[0]["display_name"] == "Trade Swing Bot"
    assert warnings == ["Duplicate strategy ID ignored: SWING-001"]


def test_malformed_plugin_is_filtered_without_hiding_valid_strategy(tmp_path: Path) -> None:
    registry = {
        "strategy_plugins": [
            "bad-plugin-record",
            _plugin("DIVIDEND-001", "Dividend Income Strategy"),
        ]
    }

    rows, warnings = build_strategy_kpis(registry=registry, root_dir=tmp_path)

    assert [row["strategy_id"] for row in rows] == ["DIVIDEND-001"]
    assert warnings == ["strategy_plugins[0] is not an object and was ignored."]


def test_no_strategy_plugins_returns_warning() -> None:
    rows, warnings = build_strategy_kpis(registry={})

    assert rows == []
    assert warnings == ["Enterprise registry does not contain strategy_plugins."]


def test_adapter_is_read_only(tmp_path: Path) -> None:
    artifact = tmp_path / "portfolio.json"
    original = json.dumps({"portfolio_value": 1234})
    artifact.write_text(original, encoding="utf-8")
    registry = {
        "strategy_plugins": [
            _plugin("DIVIDEND-001", "Dividend Income Strategy", str(artifact))
        ]
    }

    build_strategy_kpis(registry=registry, root_dir=tmp_path)

    assert artifact.read_text(encoding="utf-8") == original


def test_dividend_snapshot_csv_maps_legacy_headers_to_enterprise_kpis(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "portfolio_snapshot.csv"
    snapshot.write_text(
        "Date,Portfolio_Value,Open_Buckets,Cash\n"
        "2026-08-02,5125.50,3,125.50\n",
        encoding="utf-8",
    )
    registry = {
        "strategy_plugins": [
            _plugin("DIVIDEND-001", "Dividend Income Strategy", str(snapshot))
        ]
    }

    rows, warnings = build_strategy_kpis(
        registry=registry,
        strategy_allocations={"DIVIDEND-001": 5000},
        root_dir=tmp_path,
    )

    assert warnings == []
    assert rows[0]["allocated_capital"] == 5000.0
    assert rows[0]["portfolio_value"] == 5125.5
    assert rows[0]["position_count"] == 3
    assert rows[0]["evidence_status"] == "AVAILABLE"


def test_dividend_alias_uses_canonical_allocation_and_blocks_cross_strategy_kpi_leakage(
    tmp_path: Path,
) -> None:
    dashboard = tmp_path / "enterprise_dashboard.json"
    dashboard.write_text(
        json.dumps(
            {
                "enterprise_summary": {"allocated_capital": 9500.0},
                "strategy_kpis": [
                    {
                        "strategy_id": "SWING-001",
                        "allocated_capital": 4500.0,
                        "opportunity_quality": 91.0,
                        "watchlist_count": 3,
                        "win_rate_percent": 45.0,
                    },
                    {
                        "strategy_id": "dividend",
                        "allocated_capital": 9500.0,
                        "opportunity_quality": 88.0,
                        "watchlist_count": 9,
                        "win_rate_percent": 67.0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    registry = {
        "strategy_plugins": [
            _plugin("dividend", "Dividend Income Strategy", str(dashboard)),
        ]
    }

    rows, warnings = build_strategy_kpis(
        registry=registry,
        strategy_allocations={"DIVIDEND-001": 5000.0, "SWING-001": 4500.0},
        root_dir=tmp_path,
    )

    assert warnings == []
    assert len(rows) == 1
    row = rows[0]
    assert row["strategy_id"] == "DIVIDEND-001"
    assert row["allocated_capital"] == 5000.0
    assert row["opportunity_quality"] is None
    assert row["watchlist_count"] is None
    assert row["win_rate_percent"] is None


def test_dividend_decision_journal_reaches_enterprise_kpi_row(tmp_path: Path) -> None:
    (tmp_path / "paper_state.json").write_text(json.dumps({
        "pairs": {
            "AMDW / AMDL": {
                "a_shares": 2.0,
                "b_shares": 1.0,
                "last_prices": {"A": 20.0, "B": 30.0},
                "strategy_owner": "STRATEGY_A",
                "a_strategy_owner": "STRATEGY_A",
            }
        }
    }), encoding="utf-8")
    registry = {
        "strategy_plugins": [
            _plugin("DIVIDEND-001", "Dividend Income Strategy")
        ]
    }

    rows, warnings = build_strategy_kpis(registry=registry, root_dir=tmp_path)

    assert warnings == []
    row = rows[0]
    assert row["decision_journal_status"] == "AVAILABLE"
    assert row["decision_count"] == 2
    assert row["decision_journal"]["strategy_id"] == "DIVIDEND-001"
    assert all(
        item["decision_type"] == "HOLD"
        for item in row["decision_journal"]["decisions"]
    )

def test_external_swing_kpi_resolves_relative_to_declared_repository_root(tmp_path: Path) -> None:
    host_root = tmp_path / "dividend-host"
    swing_root = tmp_path / "swing-repo"
    host_root.mkdir()
    (swing_root / "results").mkdir(parents=True)
    external_kpi = swing_root / "results/enterprise_strategy_kpis.json"
    external_kpi.write_text(json.dumps({
        "strategy_id": "SWING-001",
        "portfolio_value": 4725.0,
        "watchlist_count": 6,
        "opportunity_quality": 91.5,
        "win_rate_percent": 62.0,
    }), encoding="utf-8")
    plugin = _plugin("SWING-001", "Trade Swing Bot", "results/enterprise_strategy_kpis.json")
    plugin["repository_root"] = str(swing_root)

    rows, warnings = build_strategy_kpis(
        registry={"strategy_plugins": [plugin]},
        strategy_allocations={"SWING-001": 4500.0},
        root_dir=host_root,
    )

    assert warnings == []
    row = rows[0]
    assert row["portfolio_value"] == 4725.0
    assert row["watchlist_count"] == 6
    assert row["opportunity_quality"] == 91.5
    assert row["win_rate_percent"] == 62.0
    assert row["evidence_paths"] == [str(external_kpi.resolve())]
    assert row["evidence_root"] == str(swing_root.resolve())
    assert row["external_evidence"] is True


def test_missing_external_swing_kpi_keeps_registered_fallback_visible(tmp_path: Path) -> None:
    host_root = tmp_path / "dividend-host"
    swing_root = tmp_path / "swing-repo"
    host_root.mkdir()
    swing_root.mkdir()
    plugin = _plugin("SWING-001", "Trade Swing Bot", "results/enterprise_strategy_kpis.json")
    plugin["repository_root"] = str(swing_root)

    rows, warnings = build_strategy_kpis(
        registry={"strategy_plugins": [plugin]},
        strategy_allocations={"SWING-001": 4500.0},
        root_dir=host_root,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["strategy_id"] == "SWING-001"
    assert row["allocated_capital"] == 4500.0
    assert row["evidence_status"] == "REGISTRY_ONLY"
    assert row["portfolio_value"] is None
    assert row["evidence_paths"] == []
    assert any(str(swing_root.resolve()) in warning for warning in warnings)



def test_dividend_strategy_health_markdown_is_accepted_evidence(tmp_path: Path) -> None:
    health = tmp_path / "strategy_health_report.md"
    health.write_text("# Strategy Health\n\nStatus: HEALTHY\n", encoding="utf-8")
    registry = {
        "strategy_plugins": [
            {
                "strategy_id": "dividend",
                "display_name": "Dividend Income Strategy",
                "enabled": True,
                "paper_trade_mode": True,
                "paper_compatible": True,
                "advisory_only": True,
                "reporting_only": True,
                "live_trading_enabled": False,
                "broker_execution_enabled": False,
                "capital_movement_enabled": False,
                "automatic_activation_allowed": False,
                "direct_database_writes": False,
                "dashboard_artifacts": [
                    {
                        "artifact_id": "strategy_health_report",
                        "artifact_type": "STRATEGY_HEALTH",
                        "path": "strategy_health_report.md",
                        "format": "MARKDOWN",
                    }
                ],
            }
        ]
    }

    rows, warnings = build_strategy_kpis(
        registry=registry,
        strategy_allocations={"dividend": 5000.0},
        root_dir=tmp_path,
    )

    assert not any("unsupported evidence path strategy_health_report.md" in item for item in warnings)
    assert "strategy_health_report.md" in rows[0]["evidence_paths"][0]


def test_swing_watchlist_rows_use_authoritative_candidate_pipeline_evidence(
    tmp_path: Path,
) -> None:
    swing_root = tmp_path / "swing"
    (swing_root / "results").mkdir(parents=True)
    artifact = swing_root / "results/enterprise_strategy_kpis.json"
    artifact.write_text(json.dumps({
        "strategy_id": "SWING-001",
        "dashboard_sections": {
            "watchlist": {
                "count": 3,
                "evidence": {
                    "rows": [
                        {
                            "underlying_symbol": "NBIS",
                            "leveraged_symbol": "NEBX",
                            "lifecycle_status": "WATCHLIST",
                            "capacity_status": "ACTIVE",
                            "watchlist_rank": 1,
                        },
                        {
                            "underlying_symbol": "IREN",
                            "leveraged_symbol": "IREL",
                            "lifecycle_status": "DISCOVERY",
                            "capacity_status": "ACTIVE",
                            "watchlist_rank": 2,
                        },
                        {
                            "underlying_symbol": "BE",
                            "leveraged_symbol": None,
                            "lifecycle_status": "REMOVED",
                            "capacity_status": "REMOVED",
                            "watchlist_rank": 3,
                        },
                    ]
                },
            }
        },
        "strategy_intelligence": {
            "watchlist_evidence": {
                "rows": [{
                    "underlying_symbol": "FALLBACK",
                    "lifecycle_status": "WATCHLIST",
                }]
            }
        },
    }), encoding="utf-8")
    plugin = _plugin(
        "SWING-001",
        "Trade Swing Bot",
        "results/enterprise_strategy_kpis.json",
    )
    plugin["repository_root"] = str(swing_root)

    rows, warnings = build_strategy_kpis(
        registry={"strategy_plugins": [plugin]},
        root_dir=tmp_path,
    )

    assert warnings == []
    row = rows[0]
    assert row["watchlist_count"] == 3
    assert [item["underlying_symbol"] for item in row["watchlist"]] == [
        "NBIS", "IREN", "BE",
    ]
    assert [item["lifecycle_status"] for item in row["watchlist"]] == [
        "WATCHLIST", "DISCOVERY", "REMOVED",
    ]
    assert "FALLBACK" not in {
        item["underlying_symbol"] for item in row["watchlist"]
    }


def test_swing_watchlist_rejects_explicit_dividend_owned_rows(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "wrong-owner.json"
    artifact.write_text(json.dumps({
        "strategy_id": "DIVIDEND-001",
        "dashboard_sections": {
            "watchlist": {
                "count": 1,
                "evidence": {
                    "rows": [{
                        "underlying_symbol": "DIVIDEND-ONLY",
                        "lifecycle_status": "WATCHLIST",
                    }]
                },
            }
        },
    }), encoding="utf-8")
    registry = {
        "strategy_plugins": [
            _plugin("SWING-001", "Trade Swing Bot", str(artifact))
        ]
    }

    rows, _ = build_strategy_kpis(registry=registry, root_dir=tmp_path)

    assert rows[0]["strategy_id"] == "SWING-001"
    assert rows[0]["watchlist"] == []

def test_swing_watchlist_skips_empty_declared_artifact_before_populated_kpi(
    tmp_path: Path,
) -> None:
    swing_root = tmp_path / "swing"
    results = swing_root / "results"
    results.mkdir(parents=True)
    empty_artifact = results / "00_empty_dashboard.json"
    populated_artifact = results / "01_enterprise_strategy_kpis.json"

    empty_artifact.write_text(json.dumps({
        "strategy_id": "SWING-001",
        "dashboard_sections": {
            "watchlist": {"count": 0, "evidence": {"rows": []}}
        },
    }), encoding="utf-8")
    populated_artifact.write_text(json.dumps({
        "strategy_id": "SWING-001",
        "dashboard_sections": {
            "watchlist": {
                "count": 3,
                "evidence": {
                    "rows": [
                        {
                            "underlying_symbol": "NBIS",
                            "leveraged_symbol": "NEBX",
                            "watchlist_status": "WATCHLIST",
                        },
                        {
                            "underlying_symbol": "IREN",
                            "leveraged_symbol": "IREL",
                            "watchlist_status": "DISCOVERY",
                        },
                        {
                            "underlying_symbol": "BE",
                            "leveraged_symbol": "",
                            "watchlist_status": "REMOVED",
                        },
                    ]
                },
            }
        },
    }), encoding="utf-8")

    plugin = _plugin(
        "SWING-001",
        "Trade Swing Bot",
        "results/00_empty_dashboard.json",
    )
    plugin["repository_root"] = str(swing_root)
    plugin["dashboard_artifacts"].append({
        "artifact_id": "swing-enterprise-kpis",
        "artifact_type": "ENTERPRISE_STRATEGY_KPIS",
        "path": "results/01_enterprise_strategy_kpis.json",
        "format": "JSON",
        "authoritative": True,
        "required": True,
    })

    rows, warnings = build_strategy_kpis(
        registry={"strategy_plugins": [plugin]},
        root_dir=tmp_path,
    )

    assert warnings == []
    assert rows[0]["watchlist_count"] == 3
    assert [
        item["underlying_symbol"] for item in rows[0]["watchlist"]
    ] == ["NBIS", "IREN", "BE"]
    assert [
        item["watchlist_status"] for item in rows[0]["watchlist"]
    ] == ["WATCHLIST", "DISCOVERY", "REMOVED"]

def test_swing_holdings_and_reconciliation_use_strategy_owned_kpi_evidence(
    tmp_path: Path,
) -> None:
    swing_root = tmp_path / "swing"
    (swing_root / "results").mkdir(parents=True)
    artifact = swing_root / "results/enterprise_strategy_kpis.json"
    positions = [
        {
            "symbol": "SOXL",
            "shares": 8.04145854,
            "entry_price": 139.899993896484,
            "current_price": 143.264297485352,
            "market_value": 1152.05,
            "unrealized_pnl": 27.05,
            "unrealized_pnl_percent": 2.404444,
            "active_strategy": "Strategy A",
        },
        {
            "symbol": "TQQQ",
            "shares": 9.021652,
            "entry_price": 74.819999694824,
            "current_price": 74.650001525879,
            "market_value": 673.47,
            "unrealized_pnl": -1.53,
            "unrealized_pnl_percent": -0.226667,
            "active_strategy": "Strategy A",
        },
    ]
    artifact.write_text(json.dumps({
        "strategy_id": "SWING-001",
        "allocated_capital": 4500.0,
        "portfolio_value": 4525.52,
        "cash_balance": 2700.0,
        "invested_capital": 1800.0,
        "positions_market_value": 1825.52,
        "position_count": 2,
        "unrealized_pnl": 25.52,
        "dashboard_sections": {
            "holdings": {"open_positions": positions}
        },
        "holdings": {
            "open_positions": [{"symbol": "STALE"}]
        },
    }), encoding="utf-8")
    plugin = _plugin(
        "SWING-001",
        "Trade Swing Bot",
        "results/enterprise_strategy_kpis.json",
    )
    plugin["repository_root"] = str(swing_root)

    rows, warnings = build_strategy_kpis(
        registry={"strategy_plugins": [plugin]},
        strategy_allocations={"SWING-001": 4500.0},
        root_dir=tmp_path,
    )

    assert warnings == []
    row = rows[0]
    assert row["allocated_capital"] == 4500.0
    assert row["portfolio_value"] == 4525.52
    assert row["cash_balance"] == 2700.0
    assert row["invested_capital"] == 1800.0
    assert row["positions_market_value"] == 1825.52
    assert row["position_count"] == 2
    assert row["unrealized_pnl"] == 25.52
    assert row["unrealized_gain"] == 25.52
    assert [item["symbol"] for item in row["holdings"]] == ["SOXL", "TQQQ"]
    assert row["positions"] == row["holdings"]


def test_swing_explicit_empty_authoritative_holdings_blocks_stale_fallback(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "swing.json"
    artifact.write_text(json.dumps({
        "strategy_id": "SWING-001",
        "position_count": 0,
        "dashboard_sections": {
            "holdings": {"open_positions": []}
        },
        "holdings": {
            "open_positions": [{"symbol": "STALE"}]
        },
    }), encoding="utf-8")

    rows, warnings = build_strategy_kpis(
        registry={
            "strategy_plugins": [
                _plugin("SWING-001", "Trade Swing Bot", str(artifact))
            ]
        },
        root_dir=tmp_path,
    )

    assert warnings == []
    assert rows[0]["position_count"] == 0
    assert rows[0]["holdings"] == []
    assert rows[0]["positions"] == []

