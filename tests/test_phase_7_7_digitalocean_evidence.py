from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.generate_phase_7_7_digitalocean_evidence import (
    build_evidence,
    write_evidence_bundle,
)


def _write_artifacts(root: Path) -> None:
    for relative in (
        "results/dividend_strategy_kpi_evidence.json",
        "results/dividend_strategy_shadow_performance.json",
        "state/dividend_pair_strategy_assignments.json",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "paper_trade_mode": True,
            "live_trading_enabled": False,
            "broker_execution_enabled": False,
            "order_placement_enabled": False,
            "capital_movement_enabled": False,
        }), encoding="utf-8")


def test_build_evidence_hashes_required_artifacts_without_mutating_them(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_artifacts(tmp_path)
    state = tmp_path / "paper_state.json"
    state.write_text('{"cash": 500}', encoding="utf-8")
    before = state.read_bytes()
    monkeypatch.setattr(
        "scripts.generate_phase_7_7_digitalocean_evidence._process_evidence",
        lambda: {"dashboard_process_running": True, "matching_processes": ["server"]},
    )
    monkeypatch.setattr(
        "scripts.generate_phase_7_7_digitalocean_evidence._endpoint_evidence",
        lambda *_: {"reachable": True, "http_status": 200, "strategy_review_visible": True},
    )

    report = build_evidence(tmp_path, generated_at_utc="2026-08-12T12:00:00Z")

    assert report["overall_status"] == "PASS"
    assert report["required_artifacts_present"] is True
    assert all(row["sha256"] for row in report["artifacts"] if row["required"])
    assert state.read_bytes() == before


def test_missing_required_artifact_is_partial_and_not_fabricated(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "scripts.generate_phase_7_7_digitalocean_evidence._process_evidence",
        lambda: {"dashboard_process_running": True, "matching_processes": []},
    )
    monkeypatch.setattr(
        "scripts.generate_phase_7_7_digitalocean_evidence._endpoint_evidence",
        lambda *_: {"reachable": True, "http_status": 200, "strategy_review_visible": True},
    )

    report = build_evidence(tmp_path)

    assert report["overall_status"] == "PARTIAL"
    assert report["required_artifacts_present"] is False
    assert any("required deployment artifacts" in warning for warning in report["warnings"])


def test_conflicting_broker_flag_fails_closed(monkeypatch, tmp_path: Path) -> None:
    _write_artifacts(tmp_path)
    target = tmp_path / "results/dividend_strategy_kpi_evidence.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["broker_execution_enabled"] = True
    target.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        "scripts.generate_phase_7_7_digitalocean_evidence._process_evidence",
        lambda: {"dashboard_process_running": True, "matching_processes": []},
    )
    monkeypatch.setattr(
        "scripts.generate_phase_7_7_digitalocean_evidence._endpoint_evidence",
        lambda *_: {"reachable": True, "http_status": 200, "strategy_review_visible": True},
    )

    report = build_evidence(tmp_path)

    assert report["overall_status"] == "FAIL"
    assert report["safety_failures"]


def test_writer_creates_json_markdown_and_verifiable_sha256(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_artifacts(tmp_path)
    monkeypatch.setattr(
        "scripts.generate_phase_7_7_digitalocean_evidence._process_evidence",
        lambda: {"dashboard_process_running": True, "matching_processes": ["server"]},
    )
    monkeypatch.setattr(
        "scripts.generate_phase_7_7_digitalocean_evidence._endpoint_evidence",
        lambda *_: {"reachable": True, "http_status": 200, "strategy_review_visible": True},
    )

    json_path, markdown_path, checksum_path = write_evidence_bundle(
        tmp_path,
        generated_at_utc="2026-08-12T12:34:56Z",
    )

    assert json_path.name == "phase_7_7_digitalocean_evidence_20260812_123456Z.json"
    assert markdown_path.is_file()
    checksums = checksum_path.read_text(encoding="utf-8").splitlines()
    expected_json = hashlib.sha256(json_path.read_bytes()).hexdigest()
    expected_markdown = hashlib.sha256(markdown_path.read_bytes()).hexdigest()
    assert checksums == [
        f"{expected_json}  {json_path.name}",
        f"{expected_markdown}  {markdown_path.name}",
    ]
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["runtime_exclusions"]["paths"] == [
        "paper_state.json",
        "state/",
        "results/",
        "backups/",
        ".git/",
    ]
