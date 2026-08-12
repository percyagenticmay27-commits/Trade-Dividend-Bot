#!/usr/bin/env python3
"""Generate an auditable, read-only DigitalOcean deployment proof bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCHEMA_VERSION = "1.0"
DEFAULT_ENDPOINT = "http://127.0.0.1:8091/strategy-review"
DEFAULT_OUTPUT_DIR = Path("artifacts/deployment")
RUNTIME_EXCLUSIONS = (
    "paper_state.json",
    "state/",
    "results/",
    "backups/",
    ".git/",
)
REQUIRED_ARTIFACTS = (
    "results/dividend_strategy_kpi_evidence.json",
    "results/dividend_strategy_shadow_performance.json",
    "state/dividend_pair_strategy_assignments.json",
)
OPTIONAL_ARTIFACTS = (
    "results/enterprise_dividend_service_registry.json",
    "results/dividend_dashboard_evidence.json",
    "results/dividend_strategy_history_alerts.json",
    "state/strategy_promotion_review_requests.json",
    "state/strategy_promotion_history.json",
)
SAFETY_EXPECTATIONS = {
    "paper_trade_mode": True,
    "live_trading_enabled": False,
    "broker_execution_enabled": False,
    "order_placement_enabled": False,
    "capital_movement_enabled": False,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _timestamp(value: str) -> str:
    return value.replace("-", "").replace(":", "").replace("T", "_").replace("Z", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, str(exc)


def _walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _safety_evidence(payload: Any) -> dict[str, Any]:
    observed: dict[str, list[Any]] = {key: [] for key in SAFETY_EXPECTATIONS}
    for mapping in _walk(payload):
        for key in observed:
            if key in mapping and mapping[key] not in observed[key]:
                observed[key].append(mapping[key])
    checks = {
        key: {
            "expected": expected,
            "observed": observed[key],
            "status": (
                "PASS" if observed[key] and all(value is expected for value in observed[key])
                else "NOT_REPORTED" if not observed[key]
                else "FAIL"
            ),
        }
        for key, expected in SAFETY_EXPECTATIONS.items()
    }
    return {"checks": checks, "passed": all(row["status"] == "PASS" for row in checks.values())}


def _artifact_record(root: Path, relative: str, required: bool) -> dict[str, Any]:
    path = root / relative
    record: dict[str, Any] = {
        "path": relative,
        "required": required,
        "present": path.is_file(),
        "size_bytes": path.stat().st_size if path.is_file() else None,
        "modified_at_utc": (
            datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
            if path.is_file() else None
        ),
        "sha256": _sha256(path) if path.is_file() else None,
    }
    if path.suffix.lower() == ".json" and path.is_file():
        payload, error = _read_json(path)
        record["json_valid"] = error is None
        record["json_error"] = error
        record["safety"] = _safety_evidence(payload) if error is None else None
    return record


def _read_git_metadata(root: Path) -> dict[str, Any]:
    git = root / ".git"
    head = git / "HEAD"
    if not head.is_file():
        return {"available": False, "branch": None, "commit": None}
    head_value = head.read_text(encoding="utf-8").strip()
    branch = head_value.removeprefix("ref: refs/heads/") if head_value.startswith("ref: ") else None
    if head_value.startswith("ref: "):
        ref_path = git / head_value[5:]
        commit = ref_path.read_text(encoding="utf-8").strip() if ref_path.is_file() else None
        if commit is None:
            packed = git / "packed-refs"
            if packed.is_file():
                suffix = " " + head_value[5:]
                commit = next(
                    (line.split(" ", 1)[0] for line in packed.read_text(encoding="utf-8").splitlines()
                     if not line.startswith("#") and line.endswith(suffix)),
                    None,
                )
    else:
        commit = head_value
    return {"available": True, "branch": branch, "commit": commit}


def _process_evidence() -> dict[str, Any]:
    names: list[str] = []
    proc = Path("/proc")
    if proc.is_dir():
        for entry in proc.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                cmdline = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8").strip()
            except (OSError, UnicodeError):
                continue
            if "paper_capital_allocation_server.py" in cmdline:
                names.append(cmdline)
    return {"dashboard_process_running": bool(names), "matching_processes": names}


def _endpoint_evidence(url: str, timeout: float) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "DividendBotDeploymentEvidence/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(512 * 1024)
            text = body.decode(response.headers.get_content_charset() or "utf-8", errors="replace")
            return {
                "url": url,
                "reachable": True,
                "http_status": response.status,
                "content_type": response.headers.get("Content-Type"),
                "body_sha256": hashlib.sha256(body).hexdigest(),
                "strategy_review_visible": "Strategy" in text and ("Review" in text or "Decision" in text),
                "error": None,
            }
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return {
            "url": url,
            "reachable": False,
            "http_status": getattr(exc, "code", None),
            "content_type": None,
            "body_sha256": None,
            "strategy_review_visible": False,
            "error": str(exc),
        }


def build_evidence(
    root_dir: str | Path = ".",
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    generated_at_utc: str | None = None,
    endpoint_timeout: float = 3.0,
) -> dict[str, Any]:
    root = Path(root_dir).resolve()
    generated_at = generated_at_utc or _utc_now()
    artifacts = [
        _artifact_record(root, path, True) for path in REQUIRED_ARTIFACTS
    ] + [
        _artifact_record(root, path, False) for path in OPTIONAL_ARTIFACTS
    ]
    required_present = all(row["present"] for row in artifacts if row["required"])
    invalid_json = [row["path"] for row in artifacts if row.get("json_valid") is False]
    safety_failures = [
        {"path": row["path"], "checks": row["safety"]["checks"]}
        for row in artifacts
        if row.get("safety") and any(
            check["status"] == "FAIL" for check in row["safety"]["checks"].values()
        )
    ]
    warnings = [
        f"Optional artifact missing: {row['path']}"
        for row in artifacts if not row["required"] and not row["present"]
    ]
    if not required_present:
        warnings.append("One or more required deployment artifacts are missing.")
    if invalid_json:
        warnings.append("Invalid JSON artifacts: " + ", ".join(invalid_json))
    if safety_failures:
        warnings.append("A reported execution-safety value conflicts with paper-only policy.")

    report = {
        "schema_version": SCHEMA_VERSION,
        "evidence_type": "PHASE_7_7_DIGITALOCEAN_DEPLOYMENT_PROOF",
        "generated_at_utc": generated_at,
        "root": str(root),
        "paper_only_policy": {
            "paper_trade_mode": True,
            "live_trading_enabled": False,
            "broker_execution_enabled": False,
            "order_placement_enabled": False,
            "capital_movement_enabled": False,
        },
        "git": _read_git_metadata(root),
        "service": _process_evidence(),
        "endpoint": _endpoint_evidence(endpoint, endpoint_timeout),
        "artifacts": artifacts,
        "runtime_exclusions": {
            "paths": list(RUNTIME_EXCLUSIONS),
            "statement": "Runtime state, generated results, backups, and Git metadata are inspected only and never copied into the proof bundle.",
        },
        "required_artifacts_present": required_present,
        "invalid_json_artifacts": invalid_json,
        "safety_failures": safety_failures,
        "warnings": warnings,
    }
    report["overall_status"] = (
        "PASS"
        if required_present
        and not invalid_json
        and not safety_failures
        and report["service"]["dashboard_process_running"]
        and report["endpoint"]["reachable"]
        else "PARTIAL" if not safety_failures else "FAIL"
    )
    return report


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Phase 7.7 DigitalOcean Deployment Evidence",
        "",
        f"- Generated: {report['generated_at_utc']}",
        f"- Overall status: **{report['overall_status']}**",
        f"- Branch: {report['git'].get('branch') or 'Not reported'}",
        f"- Commit: {report['git'].get('commit') or 'Not reported'}",
        f"- Dashboard process: {'RUNNING' if report['service']['dashboard_process_running'] else 'NOT DETECTED'}",
        f"- Endpoint: {'REACHABLE' if report['endpoint']['reachable'] else 'UNREACHABLE'} ({report['endpoint'].get('http_status') or 'no status'})",
        "",
        "## Paper-only safety",
        "",
        "- Paper trade mode: locked true",
        "- Live trading: locked false",
        "- Broker execution: locked false",
        "- Order placement: locked false",
        "- Capital movement: locked false",
        "",
        "## Artifact manifest",
        "",
        "| Artifact | Required | Present | JSON valid | SHA-256 |",
        "|---|---:|---:|---:|---|",
    ]
    for row in report["artifacts"]:
        lines.append(
            f"| `{row['path']}` | {'Yes' if row['required'] else 'No'} | "
            f"{'Yes' if row['present'] else 'No'} | "
            f"{'Yes' if row.get('json_valid') is True else 'No' if row.get('json_valid') is False else 'N/A'} | "
            f"`{row.get('sha256') or 'Not reported'}` |"
        )
    lines.extend([
        "",
        "## Runtime exclusions",
        "",
        report["runtime_exclusions"]["statement"],
        "",
    ])
    for path in report["runtime_exclusions"]["paths"]:
        lines.append(f"- `{path}`")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in report["warnings"])
    if not report["warnings"]:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def write_evidence_bundle(
    root_dir: str | Path = ".",
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    endpoint: str = DEFAULT_ENDPOINT,
    generated_at_utc: str | None = None,
    endpoint_timeout: float = 3.0,
) -> tuple[Path, Path, Path]:
    root = Path(root_dir).resolve()
    report = build_evidence(
        root,
        endpoint=endpoint,
        generated_at_utc=generated_at_utc,
        endpoint_timeout=endpoint_timeout,
    )
    target_dir = Path(output_dir)
    if not target_dir.is_absolute():
        target_dir = root / target_dir
    stem = f"phase_7_7_digitalocean_evidence_{_timestamp(report['generated_at_utc'])}"
    json_path = target_dir / f"{stem}.json"
    markdown_path = target_dir / f"{stem}.md"
    checksum_path = target_dir / f"{stem}.sha256"
    json_bytes = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    markdown_bytes = _markdown(report).encode("utf-8")
    _atomic_write(json_path, json_bytes)
    _atomic_write(markdown_path, markdown_bytes)
    checksum = (
        f"{hashlib.sha256(json_bytes).hexdigest()}  {json_path.name}\n"
        f"{hashlib.sha256(markdown_bytes).hexdigest()}  {markdown_path.name}\n"
    ).encode("utf-8")
    _atomic_write(checksum_path, checksum)
    return json_path, markdown_path, checksum_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--endpoint-timeout", type=float, default=3.0)
    args = parser.parse_args()
    paths = write_evidence_bundle(
        args.root,
        output_dir=args.output_dir,
        endpoint=args.endpoint,
        endpoint_timeout=args.endpoint_timeout,
    )
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
