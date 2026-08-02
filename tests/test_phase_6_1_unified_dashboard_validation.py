from __future__ import annotations

import json
from pathlib import Path

import validate_enterprise_unified_dashboard as launcher
from src.dividend_bot.enterprise_unified_dashboard_validation import (
    validate_and_write_unified_dashboard,
    validate_unified_dashboard_artifacts,
)


STRATEGIES = ("DIVIDEND-001", "SWING-001")


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _safety() -> dict:
    return {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "read_only": True,
    }


def _populate(results: Path, *, empty_swing_journal: bool = False) -> None:
    _write(
        results / "enterprise_dividend_service_registry.json",
        {
            "strategy_plugins": [
                {"strategy_id": strategy_id, "display_name": strategy_id}
                for strategy_id in STRATEGIES
            ]
        },
    )
    dashboard_rows = [
        {"strategy_id": strategy_id, "display_name": strategy_id}
        for strategy_id in STRATEGIES
    ]
    for filename in (
        "ai_cio_executive_dashboard.json",
        "enterprise_investor_dashboard.json",
    ):
        _write(
            results / filename,
            {
                **_safety(),
                "strategy_kpis": dashboard_rows,
            },
        )
    _write(
        results / "enterprise_strategy_kpis.json",
        {
            "strategies": [
                {
                    "strategy_id": "DIVIDEND-001",
                    "health_status": "HEALTHY",
                    "allocated_capital": 5000.0,
                    "evidence_status": "AVAILABLE",
                    "decision_journal_status": "AVAILABLE",
                },
                {
                    "strategy_id": "SWING-001",
                    "health_status": "HEALTHY",
                    "allocated_capital": 4500.0,
                    "evidence_status": "AVAILABLE",
                    "decision_journal_status": (
                        "EMPTY" if empty_swing_journal else "AVAILABLE"
                    ),
                },
            ]
        },
    )
    for strategy_id, filename in (
        ("DIVIDEND-001", "dividend_strategy_decision_journal.json"),
        ("SWING-001", "swing_strategy_decision_journal.json"),
    ):
        decisions = [] if empty_swing_journal and strategy_id == "SWING-001" else [
            {
                "strategy_id": strategy_id,
                "decision_id": f"{strategy_id}-DECISION",
            }
        ]
        _write(
            results / filename,
            {
                **_safety(),
                "strategy_id": strategy_id,
                "decision_count": len(decisions),
                "decisions": decisions,
            },
        )


def test_valid_two_strategy_artifact_set_passes(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _populate(results)

    report = validate_unified_dashboard_artifacts(results_dir=results)

    assert report["validation_status"] == "PASSED"
    assert report["errors"] == []
    assert report["registry_strategy_ids"] == list(STRATEGIES)
    assert report["kpi_strategy_ids"] == list(STRATEGIES)
    assert report["journal_strategy_ids"] == list(STRATEGIES)
    assert report["strategy_count"] == 2


def test_missing_required_artifact_fails_safely(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _populate(results)
    (results / "enterprise_investor_dashboard.json").unlink()

    report = validate_unified_dashboard_artifacts(results_dir=results)

    assert report["validation_status"] == "FAILED"
    assert any("artifact is missing" in item for item in report["errors"])


def test_missing_required_strategy_is_reported_per_consumer(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _populate(results)
    payload = json.loads(
        (results / "enterprise_strategy_kpis.json").read_text(encoding="utf-8")
    )
    payload["strategies"] = payload["strategies"][:1]
    _write(results / "enterprise_strategy_kpis.json", payload)

    report = validate_unified_dashboard_artifacts(results_dir=results)

    assert report["validation_status"] == "FAILED"
    assert "strategy_kpis: required strategy is missing: SWING-001" in report["errors"]


def test_duplicate_strategy_ids_are_rejected(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _populate(results)
    payload = json.loads(
        (results / "enterprise_dividend_service_registry.json").read_text(
            encoding="utf-8"
        )
    )
    payload["strategy_plugins"].append(
        {"strategy_id": "SWING-001", "display_name": "Duplicate Swing"}
    )
    _write(results / "enterprise_dividend_service_registry.json", payload)

    report = validate_unified_dashboard_artifacts(results_dir=results)

    assert "registry: duplicate strategy IDs are not allowed" in report["errors"]


def test_unsafe_dashboard_state_fails_validation(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _populate(results)
    payload = json.loads(
        (results / "ai_cio_executive_dashboard.json").read_text(encoding="utf-8")
    )
    payload["live_trading_enabled"] = True
    _write(results / "ai_cio_executive_dashboard.json", payload)

    report = validate_unified_dashboard_artifacts(results_dir=results)

    assert report["validation_status"] == "FAILED"
    assert "executive_dashboard: live_trading_enabled must be false" in report["errors"]


def test_cross_strategy_journal_entry_is_rejected(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _populate(results)
    payload = json.loads(
        (results / "dividend_strategy_decision_journal.json").read_text(
            encoding="utf-8"
        )
    )
    payload["decisions"][0]["strategy_id"] = "SWING-001"
    _write(results / "dividend_strategy_decision_journal.json", payload)

    report = validate_unified_dashboard_artifacts(results_dir=results)

    assert report["validation_status"] == "FAILED"
    assert any("cross-strategy decision rejected" in item for item in report["errors"])


def test_safe_empty_swing_journal_warns_without_failing(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _populate(results, empty_swing_journal=True)

    report = validate_unified_dashboard_artifacts(results_dir=results)

    assert report["validation_status"] == "PASSED"
    assert report["errors"] == []
    assert any("safe empty journal accepted" in item for item in report["warnings"])


def test_missing_health_and_invalid_allocation_fail(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _populate(results)
    payload = json.loads(
        (results / "enterprise_strategy_kpis.json").read_text(encoding="utf-8")
    )
    payload["strategies"][1]["health_status"] = ""
    payload["strategies"][1]["allocated_capital"] = "not-a-number"
    _write(results / "enterprise_strategy_kpis.json", payload)

    report = validate_unified_dashboard_artifacts(results_dir=results)

    assert "strategy_kpis: health_status is missing: SWING-001" in report["errors"]
    assert (
        "strategy_kpis: allocated_capital must be numeric: SWING-001"
        in report["errors"]
    )


def test_validation_writes_json_markdown_and_launcher_passes(
    tmp_path: Path,
    capsys,
) -> None:
    results = tmp_path / "results"
    _populate(results)

    report = validate_and_write_unified_dashboard(results_dir=results)
    code = launcher.main(["--results-dir", str(results)])
    output = capsys.readouterr().out

    assert report["validation_status"] == "PASSED"
    assert (results / "enterprise_unified_dashboard_validation.json").is_file()
    assert (results / "enterprise_unified_dashboard_validation.md").is_file()
    assert code == 0
    assert "Validation status: PASSED" in output
    markdown = (
        results / "enterprise_unified_dashboard_validation.md"
    ).read_text(encoding="utf-8")
    assert "# Enterprise Unified Dashboard Validation" in markdown
    assert "Live trading enabled: False" in markdown
