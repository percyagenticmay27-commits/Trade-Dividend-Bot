"""Long-duration stability evidence for the paper-only Enterprise AI CIO host."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping, Sequence

MODULE_NAME = "enterprise_stability_soak_validation"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True

DEFAULT_MINIMUM_SAMPLES = 7
DEFAULT_MINIMUM_DURATION_HOURS = 168.0
DEFAULT_MAXIMUM_GAP_HOURS = 36.0
SAMPLE_LOG_NAME = "enterprise_stability_soak_samples.jsonl"

EVIDENCE_REPORTS = {
    "evidence_package": "enterprise_unified_dashboard_evidence_package.json",
    "hardening": "enterprise_production_hardening_audit.json",
    "recovery": "enterprise_backup_recovery_validation.json",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _parse_utc(value: Any) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _read_mapping(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.is_file():
        return {}, f"Soak evidence report is missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, f"Soak evidence report is unreadable: {path}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"Soak evidence report root must be an object: {path}"
    return payload, None


def _safety_valid(payload: Mapping[str, Any]) -> bool:
    return (
        payload.get("paper_trade_mode") is True
        and payload.get("live_trading_enabled") is False
        and payload.get("broker_execution_enabled") is False
        and payload.get("capital_movement_enabled") is False
        and payload.get("reporting_only") is True
    )


def capture_stability_sample(
    *,
    results_dir: str | Path = "results",
    captured_at_utc: str | None = None,
) -> dict[str, Any]:
    """Capture statuses only; never copy credentials or execute production workflows."""
    directory = Path(results_dir)
    reports: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for name, filename in EVIDENCE_REPORTS.items():
        payload, error = _read_mapping(directory / filename)
        reports[name] = payload
        if error:
            errors.append(error)

    package = reports["evidence_package"]
    hardening = reports["hardening"]
    recovery = reports["recovery"]
    statuses = {
        "package_status": str(package.get("package_status") or "MISSING"),
        "acceptance_status": str(package.get("acceptance_status") or "MISSING"),
        "verification_status": str(package.get("verification_status") or "MISSING"),
        "hardening_status": str(hardening.get("hardening_status") or "MISSING"),
        "recovery_status": str(recovery.get("recovery_status") or "MISSING"),
        "restore_test_status": str(recovery.get("restore_test_status") or "MISSING"),
    }
    expected = {
        "package_status": {"PASSED"},
        "acceptance_status": {"PASSED"},
        "verification_status": {"PASSED"},
        "hardening_status": {"READY", "READY_WITH_WARNINGS"},
        "recovery_status": {"PASSED"},
        "restore_test_status": {"PASSED"},
    }
    for name, allowed in expected.items():
        if statuses[name] not in allowed:
            errors.append(f"Soak sample status is not acceptable: {name}={statuses[name]}")
    safety = {name: _safety_valid(payload) for name, payload in reports.items()}
    for name, valid in safety.items():
        if not valid:
            errors.append(f"Soak sample safety validation failed: {name}")
    return {
        "captured_at_utc": captured_at_utc or _utc_now(),
        "sample_status": "PASSED" if not errors else "FAILED",
        **statuses,
        "safety_validation": safety,
        "errors": sorted(set(errors)),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "environment_values_exposed": False,
    }


def read_stability_samples(path: str | Path) -> tuple[list[dict[str, Any]], list[str]]:
    source = Path(path)
    if not source.is_file():
        return [], []
    samples: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return [], [f"Soak sample log is unreadable: {source}: {exc}"]
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"Soak sample line {index} is invalid JSON: {exc}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"Soak sample line {index} must be an object")
            continue
        samples.append(payload)
    return samples, errors


def append_stability_sample(path: str | Path, sample: Mapping[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    content = existing
    if content and not content.endswith("\n"):
        content += "\n"
    content += json.dumps(dict(sample), sort_keys=True) + "\n"
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=target.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(target)
    return target


def validate_stability_samples(
    samples: Sequence[Mapping[str, Any]],
    *,
    minimum_samples: int = DEFAULT_MINIMUM_SAMPLES,
    minimum_duration_hours: float = DEFAULT_MINIMUM_DURATION_HOURS,
    maximum_gap_hours: float = DEFAULT_MAXIMUM_GAP_HOURS,
    input_errors: Sequence[str] = (),
) -> dict[str, Any]:
    errors = [str(item) for item in input_errors if str(item).strip()]
    warnings: list[str] = []
    parsed: list[tuple[datetime, Mapping[str, Any]]] = []
    for index, sample in enumerate(samples, start=1):
        try:
            timestamp = _parse_utc(sample.get("captured_at_utc"))
        except (ValueError, TypeError) as exc:
            errors.append(f"Soak sample {index} timestamp is invalid: {exc}")
            continue
        parsed.append((timestamp, sample))
        if sample.get("sample_status") != "PASSED":
            errors.append(f"Soak sample failed at {sample.get('captured_at_utc')}")
        if (
            sample.get("paper_trade_mode") is not True
            or sample.get("live_trading_enabled") is not False
            or sample.get("broker_execution_enabled") is not False
            or sample.get("capital_movement_enabled") is not False
            or sample.get("reporting_only") is not True
        ):
            errors.append(f"Soak sample safety fields failed at {sample.get('captured_at_utc')}")

    parsed.sort(key=lambda item: item[0])
    timestamps = [item[0] for item in parsed]
    duplicate_count = len(timestamps) - len(set(timestamps))
    if duplicate_count:
        errors.append("Soak sample timestamps must be unique")
    duration_hours = (
        (timestamps[-1] - timestamps[0]).total_seconds() / 3600.0
        if len(timestamps) >= 2
        else 0.0
    )
    gaps = [
        (right - left).total_seconds() / 3600.0
        for left, right in zip(timestamps, timestamps[1:])
    ]
    maximum_observed_gap = max(gaps, default=0.0)
    if len(timestamps) >= minimum_samples and maximum_observed_gap > maximum_gap_hours:
        errors.append(
            f"Soak sample gap exceeds {maximum_gap_hours:g} hours: "
            f"{maximum_observed_gap:.2f}"
        )
    if len(timestamps) < minimum_samples:
        warnings.append(
            f"Soak test requires {minimum_samples} samples; {len(timestamps)} recorded"
        )
    if duration_hours < minimum_duration_hours:
        warnings.append(
            f"Soak test requires {minimum_duration_hours:g} hours; "
            f"{duration_hours:.2f} recorded"
        )
    errors = sorted(set(errors))
    warnings = sorted(set(warnings))
    status = (
        "FAILED"
        if errors
        else "PASSED"
        if len(timestamps) >= minimum_samples
        and duration_hours >= minimum_duration_hours
        else "IN_PROGRESS"
    )
    return {
        "soak_status": status,
        "sample_count": len(timestamps),
        "passing_sample_count": sum(
            1 for _, sample in parsed if sample.get("sample_status") == "PASSED"
        ),
        "minimum_samples": minimum_samples,
        "duration_hours": round(duration_hours, 2),
        "minimum_duration_hours": float(minimum_duration_hours),
        "maximum_gap_hours": float(maximum_gap_hours),
        "maximum_observed_gap_hours": round(maximum_observed_gap, 2),
        "first_sample_at_utc": (
            timestamps[0].isoformat().replace("+00:00", "Z") if timestamps else None
        ),
        "last_sample_at_utc": (
            timestamps[-1].isoformat().replace("+00:00", "Z") if timestamps else None
        ),
        "warnings": warnings,
        "errors": errors,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
    }


def _atomic_write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)
    return path


def render_stability_soak_markdown(report: Mapping[str, Any]) -> str:
    errors = report.get("errors") if isinstance(report.get("errors"), list) else []
    warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
    lines = [
        "# Enterprise Stability Soak Validation",
        "",
        f"- Status: **{report.get('soak_status', 'UNKNOWN')}**",
        f"- Samples: {report.get('sample_count', 0)} / {report.get('minimum_samples', 0)}",
        f"- Duration: {report.get('duration_hours', 0)} / {report.get('minimum_duration_hours', 0)} hours",
        f"- Maximum observed gap: {report.get('maximum_observed_gap_hours', 0)} hours",
        f"- Paper trade mode: {report.get('paper_trade_mode')}",
        f"- Live trading enabled: {report.get('live_trading_enabled')}",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {item}" for item in errors)
    if not errors:
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {item}" for item in warnings)
    if not warnings:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def capture_and_validate_stability_soak(
    *,
    results_dir: str | Path = "results",
    capture: bool = True,
    captured_at_utc: str | None = None,
    minimum_samples: int = DEFAULT_MINIMUM_SAMPLES,
    minimum_duration_hours: float = DEFAULT_MINIMUM_DURATION_HOURS,
    maximum_gap_hours: float = DEFAULT_MAXIMUM_GAP_HOURS,
) -> dict[str, Any]:
    directory = Path(results_dir)
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / SAMPLE_LOG_NAME
    if capture:
        sample = capture_stability_sample(
            results_dir=directory, captured_at_utc=captured_at_utc
        )
        append_stability_sample(log_path, sample)
    samples, input_errors = read_stability_samples(log_path)
    report = validate_stability_samples(
        samples,
        minimum_samples=minimum_samples,
        minimum_duration_hours=minimum_duration_hours,
        maximum_gap_hours=maximum_gap_hours,
        input_errors=input_errors,
    )
    report.update(
        {
            "schema_version": SCHEMA_VERSION,
            "module_name": MODULE_NAME,
            "module_version": MODULE_VERSION,
            "generated_at_utc": _utc_now(),
            "sample_log_path": str(log_path),
            "environment_values_exposed": False,
        }
    )
    json_path = directory / "enterprise_stability_soak_validation.json"
    markdown_path = directory / "enterprise_stability_soak_validation.md"
    _atomic_write(json_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    _atomic_write(markdown_path, render_stability_soak_markdown(report))
    report["output_paths"] = {"json": str(json_path), "markdown": str(markdown_path)}
    return report
