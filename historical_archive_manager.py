"""Paper-only historical archive management for the AI CIO platform.

Maintains a rolling active-history policy, annual ZIP archives, manifests,
checksums, evidence indexing, read-only multi-year retrieval, access logs,
and archive health reporting. It contains no broker or order execution logic.
"""
from __future__ import annotations

import hashlib
import html
import json
import tempfile
import zipfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

MODULE_NAME = "historical_archive_manager"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True
ACTIVE_HISTORY_DAYS = 365
DEFAULT_ARCHIVE_RETENTION_YEARS = 5

DEFAULT_OUTPUT_FILES = {
    "json": "archive_manager.json",
    "markdown": "archive_manager.md",
    "html": "archive_manager.html",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


def _record_date(path: Path) -> Optional[date]:
    payload = _safe_json(path)
    candidates: list[Any] = []
    if isinstance(payload, Mapping):
        candidates.extend(payload.get(key) for key in ("date", "record_date", "generated_at_utc", "timestamp", "as_of_date"))
    candidates.append(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date().isoformat())
    for value in candidates:
        if not value:
            continue
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return date.fromisoformat(str(value)[:10])
            except ValueError:
                continue
    return None


def split_active_and_archivable(files: Iterable[str | Path], *, as_of_date: Optional[date] = None, active_days: int = ACTIVE_HISTORY_DAYS) -> dict[str, list[str]]:
    if active_days < 1:
        raise ValueError("active_days must be positive")
    cutoff = (as_of_date or date.today()) - timedelta(days=active_days)
    active: list[str] = []
    archivable: list[str] = []
    for item in files:
        path = Path(item)
        if not path.is_file():
            continue
        stamp = _record_date(path)
        (active if stamp is None or stamp > cutoff else archivable).append(str(path))
    return {"active": sorted(active), "archivable": sorted(archivable)}


def build_archive_manifest(files: Sequence[str | Path], *, archive_year: int, market_era: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
    rows = []
    symbols: set[str] = set()
    policy_versions: set[str] = set()
    for item in files:
        path = Path(item)
        if not path.is_file():
            continue
        payload = _safe_json(path)
        if isinstance(payload, Mapping):
            for key in ("symbol", "ticker", "underlying_stock", "underlying"):
                value = payload.get(key)
                if value:
                    symbols.add(str(value).upper())
            version = payload.get("policy_version")
            if version:
                policy_versions.add(str(version))
        rows.append({"name": path.name, "size_bytes": path.stat().st_size, "sha256": _sha256(path)})
    return {
        "schema_version": SCHEMA_VERSION,
        "archive_year": int(archive_year),
        "created_at_utc": _now(),
        "file_count": len(rows),
        "files": sorted(rows, key=lambda row: row["name"]),
        "symbols": sorted(symbols),
        "symbol_count": len(symbols),
        "policy_versions": sorted(policy_versions),
        "market_era": dict(market_era or {}),
    }


def create_annual_archive(files: Sequence[str | Path], archive_path: str | Path, *, archive_year: int, market_era: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
    destination = Path(archive_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    valid_files = [Path(item) for item in files if Path(item).is_file()]
    manifest = build_archive_manifest(valid_files, archive_year=archive_year, market_era=market_era)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in valid_files:
            archive.write(path, arcname=path.name)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {"archive_path": str(destination), "archive_year": int(archive_year), "archive_sha256": _sha256(destination), "manifest": manifest}


def verify_archive_integrity(archive_path: str | Path) -> dict[str, Any]:
    path = Path(archive_path)
    errors: list[str] = []
    manifest: Mapping[str, Any] = {}
    if not path.is_file():
        return {"archive_path": str(path), "healthy": False, "errors": ["Archive file is missing."], "manifest": {}}
    try:
        with zipfile.ZipFile(path, "r") as archive:
            bad = archive.testzip()
            if bad:
                errors.append(f"Corrupt member: {bad}")
            names = set(archive.namelist())
            if "manifest.json" not in names:
                errors.append("manifest.json is missing.")
            else:
                try:
                    loaded = json.loads(archive.read("manifest.json").decode("utf-8"))
                    manifest = loaded if isinstance(loaded, Mapping) else {}
                except (ValueError, UnicodeDecodeError, KeyError):
                    errors.append("manifest.json is invalid.")
                expected = {str(row.get("name")): str(row.get("sha256")) for row in manifest.get("files", []) if isinstance(row, Mapping)}
                for name, expected_hash in expected.items():
                    if name not in names:
                        errors.append(f"Manifest member missing: {name}")
                        continue
                    actual_hash = hashlib.sha256(archive.read(name)).hexdigest()
                    if actual_hash != expected_hash:
                        errors.append(f"Checksum mismatch: {name}")
    except (OSError, zipfile.BadZipFile):
        errors.append("Archive is unreadable or corrupt.")
    return {"archive_path": str(path), "healthy": not errors, "errors": errors, "manifest": dict(manifest), "archive_sha256": _sha256(path) if path.is_file() else None}


def build_historical_evidence_index(archive_paths: Sequence[str | Path]) -> dict[str, Any]:
    symbols: dict[str, list[int]] = {}
    market_eras: dict[str, list[int]] = {}
    archives = []
    for item in archive_paths:
        result = verify_archive_integrity(item)
        manifest = result.get("manifest", {})
        year = int(manifest.get("archive_year", 0) or 0)
        archives.append({"archive_path": str(item), "year": year, "healthy": bool(result.get("healthy"))})
        for symbol in manifest.get("symbols", []):
            symbols.setdefault(str(symbol).upper(), []).append(year)
        era = manifest.get("market_era", {})
        if isinstance(era, Mapping) and era.get("name"):
            market_eras.setdefault(str(era["name"]), []).append(year)
    return {
        "archives": sorted(archives, key=lambda row: row["year"]),
        "symbols": {key: sorted(set(value)) for key, value in sorted(symbols.items())},
        "market_eras": {key: sorted(set(value)) for key, value in sorted(market_eras.items())},
    }


def plan_retention(archive_paths: Sequence[str | Path], *, retention_years: int = DEFAULT_ARCHIVE_RETENTION_YEARS) -> dict[str, list[str]]:
    if retention_years < 1:
        raise ValueError("retention_years must be positive")
    dated = []
    for item in archive_paths:
        path = Path(item)
        try:
            year = int(path.stem[:4])
        except ValueError:
            result = verify_archive_integrity(path)
            year = int(result.get("manifest", {}).get("archive_year", 0) or 0)
        dated.append((year, str(path)))
    dated.sort(reverse=True)
    return {
        "keep": [path for _, path in dated[:retention_years]],
        "deletion_requires_investor_approval": [path for _, path in dated[retention_years:]],
    }


def retrieve_symbol_history(archive_paths: Sequence[str | Path], *, symbol: str, years: Sequence[int], requester: str, reason: str, access_log_path: Optional[str | Path] = None) -> dict[str, Any]:
    normalized = symbol.upper().strip()
    if not normalized:
        raise ValueError("symbol is required")
    requested_years = sorted({int(year) for year in years})
    if not 1 <= len(requested_years) <= 3:
        raise ValueError("retrieval must request between one and three years")
    before_hashes = {str(Path(item)): _sha256(Path(item)) for item in archive_paths if Path(item).is_file()}
    records: list[dict[str, Any]] = []
    accessed: list[str] = []
    with tempfile.TemporaryDirectory(prefix="ai_cio_archive_") as workspace:
        workspace_path = Path(workspace)
        for item in archive_paths:
            path = Path(item)
            check = verify_archive_integrity(path)
            manifest = check.get("manifest", {})
            year = int(manifest.get("archive_year", 0) or 0)
            if year not in requested_years or not check.get("healthy"):
                continue
            with zipfile.ZipFile(path, "r") as archive:
                matched = False
                for member in archive.namelist():
                    if member == "manifest.json" or member.endswith("/"):
                        continue
                    raw = archive.read(member)
                    if normalized not in member.upper() and normalized.encode("utf-8") not in raw.upper():
                        continue
                    target = workspace_path / f"{year}_{Path(member).name}"
                    target.write_bytes(raw)
                    payload = _safe_json(target)
                    records.append({"archive_year": year, "member": member, "data": payload if payload is not None else raw.decode("utf-8", errors="replace")})
                    matched = True
                if matched:
                    accessed.append(str(path))
    after_hashes = {str(Path(item)): _sha256(Path(item)) for item in archive_paths if Path(item).is_file()}
    unchanged = before_hashes == after_hashes
    log_entry = {
        "accessed_at_utc": _now(), "requester": requester, "reason": reason, "symbol": normalized,
        "years_requested": requested_years, "archives_accessed": accessed, "records_returned": len(records),
        "temporary_workspace_removed": True, "original_archives_modified": not unchanged,
        "integrity_verified": unchanged, "status": "COMPLETED" if unchanged else "INTEGRITY_WARNING",
    }
    if access_log_path:
        log_path = Path(access_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        existing = _safe_json(log_path)
        rows = existing if isinstance(existing, list) else []
        rows.append(log_entry)
        log_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"records": records, "access_log_entry": log_entry}


def build_archive_heat_map(access_log: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    accesses: Counter[str] = Counter()
    reasons: dict[str, Counter[str]] = {}
    for row in access_log:
        reason = str(row.get("reason", "Unspecified"))
        archives = row.get("archives_accessed", [])
        for archive in archives if isinstance(archives, Sequence) and not isinstance(archives, (str, bytes)) else []:
            name = Path(str(archive)).name
            accesses[name] += 1
            reasons.setdefault(name, Counter())[reason] += 1
    return [{"archive": name, "access_count": count, "primary_reason": reasons[name].most_common(1)[0][0] if reasons.get(name) else "Unspecified"} for name, count in accesses.most_common()]


def build_historical_archive_report(*, archive_paths: Optional[Sequence[str | Path]] = None, access_log: Optional[Sequence[Mapping[str, Any]]] = None, retention_years: int = DEFAULT_ARCHIVE_RETENTION_YEARS) -> dict[str, Any]:
    paths = list(archive_paths or [])
    health = [verify_archive_integrity(path) for path in paths]
    healthy_count = sum(1 for row in health if row.get("healthy"))
    return {
        "module_name": MODULE_NAME, "module_version": MODULE_VERSION, "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(), "paper_trade_mode": True, "live_trading_enabled": False,
        "broker_execution_enabled": False, "reporting_only": True, "active_history_days": ACTIVE_HISTORY_DAYS,
        "archive_retention_years": retention_years, "archive_count": len(paths), "healthy_archive_count": healthy_count,
        "archive_health_percent": round((healthy_count / len(paths) * 100.0) if paths else 100.0, 2),
        "archive_health": health, "evidence_index": build_historical_evidence_index(paths),
        "retention_plan": plan_retention(paths, retention_years=retention_years),
        "archive_heat_map": build_archive_heat_map(list(access_log or [])),
        "governance": {"one_year_active_history": True, "five_year_archive_default": retention_years == DEFAULT_ARCHIVE_RETENTION_YEARS, "deletion_requires_investor_approval": True, "read_only_retrieval_modifies_archives": False, "temporary_extractions_removed": True},
        "warnings": [] if paths else ["No archives were supplied; health is reported as ready but unpopulated."], "errors": [],
    }


def format_historical_archive_markdown(report: Mapping[str, Any]) -> str:
    lines = ["# Historical Archive Manager", "", "## Executive Summary", "",
        f"- **Archive Health:** {report.get('archive_health_percent', 0):.2f}%",
        f"- **Archives Reviewed:** {report.get('archive_count', 0)}",
        f"- **Healthy Archives:** {report.get('healthy_archive_count', 0)}",
        f"- **Active History:** {report.get('active_history_days', ACTIVE_HISTORY_DAYS)} days",
        f"- **Archive Retention:** {report.get('archive_retention_years', DEFAULT_ARCHIVE_RETENTION_YEARS)} years", "",
        "## Archive Health", "", "| Archive | Healthy | Errors |", "|---|:---:|---|"]
    for row in report.get("archive_health", []):
        lines.append(f"| {Path(str(row.get('archive_path', 'Unknown'))).name} | {'Yes' if row.get('healthy') else 'No'} | {'; '.join(row.get('errors', [])) or 'None'} |")
    lines.extend(["", "## Archive Heat Map", "", "| Archive | Accesses | Primary Reason |", "|---|---:|---|"])
    for row in report.get("archive_heat_map", []):
        lines.append(f"| {row.get('archive')} | {row.get('access_count', 0)} | {row.get('primary_reason')} |")
    lines.extend(["", "## Governance", "", "Read-only retrieval extracts temporary working copies only. Original ZIP archives remain unchanged, temporary files are removed after analysis, and archive deletion requires investor approval.", "", "## Paper-Only Safety", "", "This module manages historical files only. It does not place orders or communicate with a brokerage.", ""])
    return "\n".join(lines)


def format_historical_archive_html(report: Mapping[str, Any]) -> str:
    markdown = format_historical_archive_markdown(report)
    return "<!doctype html><html><head><meta charset='utf-8'><title>Historical Archive Manager</title><style>body{font-family:Arial,sans-serif;max-width:1100px;margin:0 auto;padding:32px;background:#f5f7fb;color:#172033}pre{white-space:pre-wrap;background:white;padding:30px;border-radius:14px;box-shadow:0 4px 18px rgba(0,0,0,.08);line-height:1.55}</style></head><body><pre>" + html.escape(markdown) + "</pre></body></html>"


def write_historical_archive_report(payload: Mapping[str, Any], root_path: str = ".", output_files: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    report = build_historical_archive_report(**dict(payload))
    root = Path(root_path)
    root.mkdir(parents=True, exist_ok=True)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    (root / files["json"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_historical_archive_markdown(report), encoding="utf-8")
    (root / files["html"]).write_text(format_historical_archive_html(report), encoding="utf-8")
    return report


def build_and_write_historical_archive_report(payload: Mapping[str, Any], root_path: str = ".", output_files: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    return write_historical_archive_report(payload, root_path, output_files)


if __name__ == "__main__":
    report = write_historical_archive_report({"archive_paths": [], "access_log": []})
    print(f"Historical Archive Manager: {report['archive_health_percent']:.2f}% healthy")
