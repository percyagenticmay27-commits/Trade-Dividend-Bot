"""Isolated backup-and-restore drill for paper-only Enterprise runtime evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile, TemporaryDirectory
import tarfile
from typing import Any, Mapping, Sequence

MODULE_NAME = "enterprise_backup_recovery_validation"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True
ISOLATED_RESTORE_ONLY = True

DEFAULT_CRITICAL_FILES = (
    "paper_state.json",
    "paper_trade_log.csv",
    "portfolio_snapshot.csv",
    "email_delivery_log.csv",
    "results/enterprise-unified-dashboard-evidence-package.zip",
    "results/enterprise_unified_dashboard_evidence_package.json",
    "results/enterprise_production_hardening_audit.json",
)
MANIFEST_MEMBER = "recovery_manifest.json"
SNAPSHOT_PREFIX = "snapshot/"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _safe_relative_name(value: str) -> str | None:
    normalized = value.replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    if (
        not normalized
        or path.is_absolute()
        or ".." in path.parts
        or normalized.startswith("/")
    ):
        return None
    return path.as_posix()


def snapshot_critical_files(
    *, root_dir: str | Path, critical_files: Sequence[str] = DEFAULT_CRITICAL_FILES
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    root = Path(root_dir).resolve()
    manifest: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for requested in critical_files:
        name = _safe_relative_name(str(requested))
        if name is None:
            errors.append(f"Critical file path is unsafe: {requested}")
            continue
        path = root / Path(name)
        if not path.is_file():
            errors.append(f"Critical recovery file is missing: {name}")
            continue
        try:
            content = path.read_bytes()
        except OSError as exc:
            errors.append(f"Critical recovery file is unreadable: {name}: {exc}")
            continue
        manifest[name] = {
            "size_bytes": len(content),
            "sha256": _sha256_bytes(content),
        }
    return manifest, errors


def _tar_info(name: str, size: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mtime = 0
    info.mode = 0o600
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def create_recovery_archive(
    *,
    root_dir: str | Path,
    archive_path: str | Path,
    manifest: Mapping[str, Mapping[str, Any]],
) -> Path:
    root = Path(root_dir).resolve()
    output = Path(archive_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_document = {
        "schema_version": SCHEMA_VERSION,
        "files": {str(name): dict(row) for name, row in sorted(manifest.items())},
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "isolated_restore_only": True,
    }
    manifest_bytes = (
        json.dumps(manifest_document, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    with NamedTemporaryFile("wb", dir=output.parent, delete=False, suffix=".tmp") as handle:
        temporary = Path(handle.name)
    try:
        with tarfile.open(temporary, "w:gz") as archive:
            archive.addfile(
                _tar_info(MANIFEST_MEMBER, len(manifest_bytes)),
                BytesIO(manifest_bytes),
            )
            for name, expected in sorted(manifest.items()):
                safe_name = _safe_relative_name(str(name))
                if safe_name is None:
                    raise ValueError(f"Recovery manifest path is unsafe: {name}")
                content = (root / Path(safe_name)).read_bytes()
                if _sha256_bytes(content) != str(expected.get("sha256") or ""):
                    raise ValueError(f"Critical file changed before backup: {safe_name}")
                archive.addfile(
                    _tar_info(SNAPSHOT_PREFIX + safe_name, len(content)),
                    BytesIO(content),
                )
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return output


def validate_recovery_archive(
    *, archive_path: str | Path
) -> tuple[dict[str, Any], list[str]]:
    """Restore to an isolated temporary directory and validate every file hash."""
    archive_file = Path(archive_path)
    errors: list[str] = []
    restored: dict[str, dict[str, Any]] = {}
    if not archive_file.is_file():
        return {}, [f"Recovery archive is missing: {archive_file}"]
    try:
        with tarfile.open(archive_file, "r:gz") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if len(names) != len(set(names)):
                errors.append("Recovery archive contains duplicate member names")
            for member in members:
                if not member.isfile():
                    errors.append(f"Recovery archive member is not a regular file: {member.name}")
                if member.name != MANIFEST_MEMBER and not member.name.startswith(SNAPSHOT_PREFIX):
                    errors.append(f"Recovery archive member is outside snapshot scope: {member.name}")
                relative = (
                    member.name[len(SNAPSHOT_PREFIX):]
                    if member.name.startswith(SNAPSHOT_PREFIX)
                    else member.name
                )
                if _safe_relative_name(relative) is None:
                    errors.append(f"Recovery archive member path is unsafe: {member.name}")
            manifest_member = archive.getmember(MANIFEST_MEMBER)
            manifest_handle = archive.extractfile(manifest_member)
            if manifest_handle is None:
                raise ValueError("Recovery manifest could not be read")
            manifest_document = json.loads(manifest_handle.read().decode("utf-8"))
            if not isinstance(manifest_document, dict):
                raise ValueError("Recovery manifest root must be an object")
            expected_files = manifest_document.get("files")
            if not isinstance(expected_files, dict):
                raise ValueError("Recovery manifest files must be an object")
            expected_members = {SNAPSHOT_PREFIX + name for name in expected_files}
            actual_members = {name for name in names if name.startswith(SNAPSHOT_PREFIX)}
            if actual_members != expected_members:
                errors.append("Recovery archive contents do not match embedded manifest")

            with TemporaryDirectory(prefix="enterprise-recovery-") as temporary_name:
                temporary_root = Path(temporary_name)
                for name, expected_raw in sorted(expected_files.items()):
                    safe_name = _safe_relative_name(str(name))
                    expected = expected_raw if isinstance(expected_raw, Mapping) else {}
                    if safe_name is None:
                        errors.append(f"Recovery manifest path is unsafe: {name}")
                        continue
                    try:
                        member = archive.getmember(SNAPSHOT_PREFIX + safe_name)
                    except KeyError:
                        continue
                    handle = archive.extractfile(member)
                    if handle is None:
                        errors.append(f"Recovery archive file could not be read: {safe_name}")
                        continue
                    content = handle.read()
                    restored_path = temporary_root / Path(safe_name)
                    restored_path.parent.mkdir(parents=True, exist_ok=True)
                    restored_path.write_bytes(content)
                    actual_size = restored_path.stat().st_size
                    actual_hash = _sha256_bytes(restored_path.read_bytes())
                    if actual_size != expected.get("size_bytes"):
                        errors.append(f"Restored file size mismatch: {safe_name}")
                    if actual_hash != expected.get("sha256"):
                        errors.append(f"Restored file SHA-256 mismatch: {safe_name}")
                    restored[safe_name] = {
                        "size_bytes": actual_size,
                        "sha256": actual_hash,
                    }
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError, ValueError, KeyError) as exc:
        errors.append(f"Recovery archive validation failed: {exc}")
    return {
        "archive_path": str(archive_file),
        "archive_sha256": _sha256_bytes(archive_file.read_bytes()) if archive_file.is_file() else None,
        "restored_files": restored,
        "restored_file_count": len(restored),
        "isolated_restore_directory_removed": True,
    }, sorted(set(errors))


def _atomic_write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)
    return path


def render_recovery_validation_markdown(report: Mapping[str, Any]) -> str:
    errors = report.get("errors") if isinstance(report.get("errors"), list) else []
    lines = [
        "# Enterprise Backup Recovery Validation",
        "",
        f"- Status: **{report.get('recovery_status', 'UNKNOWN')}**",
        f"- Restore test: {report.get('restore_test_status', 'UNKNOWN')}",
        f"- Critical files: {report.get('critical_file_count', 0)}",
        f"- Restored files: {report.get('restored_file_count', 0)}",
        f"- Source unchanged: {report.get('source_files_unchanged')}",
        f"- Isolated restore removed: {report.get('isolated_restore_directory_removed')}",
        f"- Live trading enabled: {report.get('live_trading_enabled')}",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {item}" for item in errors)
    if not errors:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def run_backup_recovery_drill(
    *,
    root_dir: str | Path = ".",
    results_dir: str | Path = "results",
    critical_files: Sequence[str] = DEFAULT_CRITICAL_FILES,
) -> dict[str, Any]:
    root = Path(root_dir).resolve()
    results = Path(results_dir)
    results = results if results.is_absolute() else root / results
    results.mkdir(parents=True, exist_ok=True)
    before, errors = snapshot_critical_files(root_dir=root, critical_files=critical_files)
    archive_path = results / "enterprise-recovery-drill.tar.gz"
    validation: dict[str, Any] = {}
    if not errors:
        try:
            create_recovery_archive(
                root_dir=root, archive_path=archive_path, manifest=before
            )
            validation, validation_errors = validate_recovery_archive(
                archive_path=archive_path
            )
            errors.extend(validation_errors)
        except (OSError, ValueError, tarfile.TarError) as exc:
            errors.append(f"Recovery drill failed: {exc}")
    after, after_errors = snapshot_critical_files(
        root_dir=root, critical_files=critical_files
    )
    errors.extend(after_errors)
    unchanged = before == after
    if not unchanged:
        errors.append("Critical source files changed during recovery drill")
    errors = sorted(set(errors))
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "generated_at_utc": _utc_now(),
        "recovery_status": "PASSED" if not errors else "FAILED",
        "restore_test_status": "PASSED" if not errors else "FAILED",
        "critical_file_count": len(before),
        "restored_file_count": int(validation.get("restored_file_count", 0) or 0),
        "source_files_unchanged": unchanged,
        "isolated_restore_directory_removed": validation.get(
            "isolated_restore_directory_removed", True
        ),
        "archive_path": str(archive_path) if archive_path.is_file() else None,
        "archive_sha256": validation.get("archive_sha256"),
        "source_manifest": before,
        "restored_manifest": validation.get("restored_files", {}),
        "errors": errors,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "isolated_restore_only": True,
    }
    json_path = results / "enterprise_backup_recovery_validation.json"
    markdown_path = results / "enterprise_backup_recovery_validation.md"
    _atomic_write(json_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    _atomic_write(markdown_path, render_recovery_validation_markdown(report))
    report["output_paths"] = {"json": str(json_path), "markdown": str(markdown_path)}
    return report
