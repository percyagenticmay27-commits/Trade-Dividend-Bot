from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import tarfile

import validate_enterprise_backup_recovery as launcher
from src.dividend_bot.enterprise_backup_recovery_validation import (
    MANIFEST_MEMBER,
    create_recovery_archive,
    run_backup_recovery_drill,
    snapshot_critical_files,
    validate_recovery_archive,
)


FILES = ("paper_state.json", "results/evidence.json", "paper_trade_log.csv")


def _populate(root: Path) -> None:
    for index, name in enumerate(FILES):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"critical-{index}\n", encoding="utf-8")


def test_isolated_recovery_drill_passes_and_preserves_source(tmp_path: Path) -> None:
    _populate(tmp_path)
    before = {name: (tmp_path / name).read_bytes() for name in FILES}
    report = run_backup_recovery_drill(
        root_dir=tmp_path, critical_files=FILES
    )
    assert report["recovery_status"] == "PASSED"
    assert report["restored_file_count"] == len(FILES)
    assert report["source_files_unchanged"] is True
    assert before == {name: (tmp_path / name).read_bytes() for name in FILES}


def test_snapshot_records_size_and_sha256(tmp_path: Path) -> None:
    _populate(tmp_path)
    manifest, errors = snapshot_critical_files(
        root_dir=tmp_path, critical_files=FILES
    )
    assert errors == []
    assert all(row["size_bytes"] > 0 for row in manifest.values())
    assert all(len(row["sha256"]) == 64 for row in manifest.values())


def test_missing_critical_file_fails_without_archive(tmp_path: Path) -> None:
    _populate(tmp_path)
    report = run_backup_recovery_drill(
        root_dir=tmp_path, critical_files=(*FILES, "missing.json")
    )
    assert report["recovery_status"] == "FAILED"
    assert report["archive_path"] is None
    assert any("file is missing" in item for item in report["errors"])


def test_archive_contains_manifest_and_snapshot_scope_only(tmp_path: Path) -> None:
    _populate(tmp_path)
    manifest, _ = snapshot_critical_files(root_dir=tmp_path, critical_files=FILES)
    archive_path = tmp_path / "backup.tar.gz"
    create_recovery_archive(
        root_dir=tmp_path, archive_path=archive_path, manifest=manifest
    )
    with tarfile.open(archive_path, "r:gz") as archive:
        names = archive.getnames()
    assert MANIFEST_MEMBER in names
    assert all(name == MANIFEST_MEMBER or name.startswith("snapshot/") for name in names)


def test_archive_path_traversal_is_rejected(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.tar.gz"
    manifest = json.dumps({"files": {}}).encode()
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo(MANIFEST_MEMBER)
        info.size = len(manifest)
        archive.addfile(info, BytesIO(manifest))
        content = b"unsafe"
        info = tarfile.TarInfo("snapshot/../../unsafe.txt")
        info.size = len(content)
        archive.addfile(info, BytesIO(content))
    _, errors = validate_recovery_archive(archive_path=archive_path)
    assert any("path is unsafe" in item for item in errors)


def test_archive_links_are_rejected(tmp_path: Path) -> None:
    archive_path = tmp_path / "link.tar.gz"
    manifest = json.dumps({"files": {}}).encode()
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo(MANIFEST_MEMBER)
        info.size = len(manifest)
        archive.addfile(info, BytesIO(manifest))
        link = tarfile.TarInfo("snapshot/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../target"
        archive.addfile(link)
    _, errors = validate_recovery_archive(archive_path=archive_path)
    assert any("not a regular file" in item for item in errors)


def test_tampered_restored_content_is_detected(tmp_path: Path) -> None:
    _populate(tmp_path)
    manifest, _ = snapshot_critical_files(root_dir=tmp_path, critical_files=FILES)
    archive_path = tmp_path / "tampered.tar.gz"
    manifest_document = json.dumps({"files": manifest}).encode()
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo(MANIFEST_MEMBER)
        info.size = len(manifest_document)
        archive.addfile(info, BytesIO(manifest_document))
        for name in FILES:
            content = b"tampered"
            info = tarfile.TarInfo("snapshot/" + name)
            info.size = len(content)
            archive.addfile(info, BytesIO(content))
    _, errors = validate_recovery_archive(archive_path=archive_path)
    assert any("mismatch" in item for item in errors)


def test_unsafe_requested_source_path_is_rejected(tmp_path: Path) -> None:
    _, errors = snapshot_critical_files(
        root_dir=tmp_path, critical_files=("../secret",)
    )
    assert any("path is unsafe" in item for item in errors)


def test_drill_writes_reports_and_paper_only_flags(tmp_path: Path) -> None:
    _populate(tmp_path)
    report = run_backup_recovery_drill(
        root_dir=tmp_path, critical_files=FILES
    )
    assert Path(report["output_paths"]["json"]).is_file()
    assert Path(report["output_paths"]["markdown"]).is_file()
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["capital_movement_enabled"] is False
    assert report["isolated_restore_only"] is True


def test_launcher_exit_codes(monkeypatch, capsys) -> None:
    base = {
        "restore_test_status": "PASSED",
        "critical_file_count": 3,
        "restored_file_count": 3,
        "source_files_unchanged": True,
        "errors": [],
    }
    monkeypatch.setattr(
        launcher,
        "run_backup_recovery_drill",
        lambda **kwargs: {**base, "recovery_status": "PASSED"},
    )
    assert launcher.main([]) == 0
    assert "Recovery status: PASSED" in capsys.readouterr().out
    monkeypatch.setattr(
        launcher,
        "run_backup_recovery_drill",
        lambda **kwargs: {**base, "recovery_status": "FAILED", "errors": ["failed"]},
    )
    assert launcher.main([]) == 1
