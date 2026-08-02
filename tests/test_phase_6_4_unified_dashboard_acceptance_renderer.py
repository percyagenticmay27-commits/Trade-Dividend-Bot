from __future__ import annotations

import json
from pathlib import Path

import generate_enterprise_unified_dashboard_acceptance_preview as launcher
from src.dividend_bot.enterprise_unified_dashboard_acceptance_renderer import (
    build_acceptance_view_model,
    generate_acceptance_evidence_preview,
    load_acceptance_evidence,
    render_acceptance_evidence_document,
)


def _documents():
    safety = {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
    }
    acceptance = {
        **safety,
        "acceptance_status": "PASSED",
        "generated_at_utc": "2026-08-02T12:00:00Z",
        "protected_state_unchanged": True,
        "protected_state_file_count": 2,
        "required_strategy_ids": ["DIVIDEND-001", "SWING-001"],
        "artifact_manifest": {
            "ai_cio_executive_dashboard.json": {
                "exists": True,
                "size_bytes": 100,
                "sha256": "a" * 64,
            }
        },
        "warnings": [],
        "errors": [],
    }
    cycle = {**safety, "cycle_status": "PASSED", "warnings": [], "errors": []}
    validation = {
        "validation_status": "PASSED",
        "strategy_kpi_summary": {
            "DIVIDEND-001": {
                "health_status": "HEALTHY",
                "allocated_capital": 5000,
                "evidence_status": "AVAILABLE",
                "decision_journal_status": "AVAILABLE",
            },
            "SWING-001": {
                "health_status": "HEALTHY",
                "allocated_capital": 4500,
                "evidence_status": "AVAILABLE",
                "decision_journal_status": "EMPTY",
            },
        },
        "warnings": ["safe empty Swing journal"],
        "errors": [],
    }
    return acceptance, cycle, validation


def _write_documents(results: Path) -> None:
    acceptance, cycle, validation = _documents()
    results.mkdir(parents=True, exist_ok=True)
    for name, payload in (
        ("enterprise_unified_dashboard_cycle_acceptance.json", acceptance),
        ("enterprise_unified_dashboard_cycle.json", cycle),
        ("enterprise_unified_dashboard_validation.json", validation),
    ):
        (results / name).write_text(json.dumps(payload), encoding="utf-8")


def test_passing_evidence_builds_passing_view_model() -> None:
    acceptance, cycle, validation = _documents()
    model = build_acceptance_view_model(
        acceptance=acceptance, cycle=cycle, validation=validation
    )
    assert model["verification_status"] == "PASSED"
    assert model["protected_state_unchanged"] is True


def test_dividend_and_swing_rows_render_independently() -> None:
    acceptance, cycle, validation = _documents()
    html = render_acceptance_evidence_document(
        build_acceptance_view_model(
            acceptance=acceptance, cycle=cycle, validation=validation
        )
    )
    assert "DIVIDEND-001" in html
    assert "SWING-001" in html
    assert "EMPTY" in html


def test_failed_or_unsafe_evidence_is_visibly_rejected() -> None:
    acceptance, cycle, validation = _documents()
    cycle["live_trading_enabled"] = True
    model = build_acceptance_view_model(
        acceptance=acceptance, cycle=cycle, validation=validation
    )
    html = render_acceptance_evidence_document(model)
    assert model["verification_status"] == "FAILED"
    assert "cycle safety field live_trading_enabled must be False" in html


def test_artifact_links_are_restricted_to_local_filenames() -> None:
    acceptance, cycle, validation = _documents()
    acceptance["artifact_manifest"] = {
        "../../unsafe.json": {"exists": True, "size_bytes": 1, "sha256": "b" * 64}
    }
    html = render_acceptance_evidence_document(
        build_acceptance_view_model(
            acceptance=acceptance, cycle=cycle, validation=validation
        )
    )
    assert 'href="unsafe.json"' in html
    assert 'href="../../unsafe.json"' not in html


def test_untrusted_content_is_html_escaped() -> None:
    acceptance, cycle, validation = _documents()
    validation["warnings"] = ["<img src=x onerror=alert(1)>"]
    html = render_acceptance_evidence_document(
        build_acceptance_view_model(
            acceptance=acceptance, cycle=cycle, validation=validation
        )
    )
    assert "<img src=x" not in html
    assert "&lt;img src=x" in html


def test_standalone_document_contains_no_script() -> None:
    acceptance, cycle, validation = _documents()
    html = render_acceptance_evidence_document(
        build_acceptance_view_model(
            acceptance=acceptance, cycle=cycle, validation=validation
        )
    )
    assert "<script" not in html.lower()
    assert "PAPER ONLY" in html
    assert "NO BROKER EXECUTION" in html


def test_loader_and_generator_write_real_preview(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write_documents(results)
    evidence = load_acceptance_evidence(results)
    generated = generate_acceptance_evidence_preview(results_dir=results)
    assert evidence["acceptance"]["acceptance_status"] == "PASSED"
    assert generated["verification_status"] == "PASSED"
    assert Path(generated["path"]).is_file()


def test_missing_or_non_object_evidence_is_rejected(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write_documents(results)
    (results / "enterprise_unified_dashboard_validation.json").write_text(
        "[]", encoding="utf-8"
    )
    try:
        load_acceptance_evidence(results)
    except ValueError as exc:
        assert "root must be an object" in str(exc)
    else:
        raise AssertionError("non-object evidence should be rejected")


def test_launcher_returns_pass_and_failure_codes(tmp_path: Path, capsys) -> None:
    results = tmp_path / "results"
    _write_documents(results)
    assert launcher.main(["--results-dir", str(results)]) == 0
    assert "Verification status: PASSED" in capsys.readouterr().out
    (results / "enterprise_unified_dashboard_validation.json").unlink()
    assert launcher.main(["--results-dir", str(results)]) == 1
